"""HA Supervisor ingress only; read-only archives plus isolated, bounded diagnostic jobs."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from aiohttp import web

from .decision_store import DecisionStore, canonical
from .explanations import decision_view

KINDS = {"forbid_ev", "continuous_ev", "no_grid_import", "forbid_ess_charge", "forbid_ess_discharge"}


class ExplanationAPI:
    def __init__(self, store, *, live_busy=lambda: False, trusted_peer="172.30.32.2", timeout=65, cooldown=30):
        self.store, self.live_busy, self.trusted_peer = store, live_busy, trusted_peer
        self.timeout, self.cooldown = timeout, cooldown
        self.jobs = {}
        self.task = None
        self.last_started = -float("inf")
        self.request_lock = asyncio.Lock()
        self.reading = 0

    @web.middleware
    async def guard(self, request, handler):
        # Ignore forwarded addresses: only the Supervisor ingress proxy may reach this service.
        if request.remote != self.trusted_peer or not re.fullmatch(
            r"/api/hassio_ingress/[A-Za-z0-9_-]+/?", request.headers.get("X-Ingress-Path", "")
        ):
            raise web.HTTPUnauthorized(text="Home Assistant ingress authentication required")
        if request.method == "POST" and request.headers.get("X-EnergyManager-Request") != "1":
            raise web.HTTPForbidden(text="Same-origin diagnostic request required")
        try:
            response = await handler(request)
        except FileNotFoundError:
            raise web.HTTPNotFound(text="Decision was removed by retention or does not exist") from None
        except (ValueError, TypeError, KeyError) as exc:
            raise web.HTTPBadRequest(text=str(exc)[:200]) from None
        except OSError:
            raise web.HTTPServiceUnavailable(text="Decision archive unavailable") from None
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def app(self):
        app = web.Application(middlewares=[self.guard], client_max_size=2048)
        app.router.add_get("/", self.index)
        app.router.add_get("/api/decisions", self.history)
        app.router.add_get("/api/decisions/{identity}", self.decision)
        app.router.add_post("/api/counterfactuals", self.submit)
        app.router.add_get("/api/counterfactuals/{identity}", self.poll)
        app.on_cleanup.append(self.close)
        return app

    async def read(self, operation):
        if self.reading >= 2:
            raise web.HTTPTooManyRequests(text="Archive readers busy; retry shortly")
        self.reading += 1
        work = asyncio.create_task(asyncio.to_thread(operation))
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            # A disconnected browser cannot release the reader slot while its thread still runs.
            await work
            raise
        finally:
            self.reading -= 1

    async def index(self, request):
        return web.Response(text="EnergyManager explanations are in the Overview and Planning dashboard cards.")

    async def history(self, request):
        offset = int(request.query.get("offset", "0"))
        if not 0 <= offset <= 10000:
            raise ValueError("invalid history offset")

        def read():
            identities = self.store.list_ids()
            records = []
            for identity in identities[offset:offset + 20]:
                try:
                    snapshot, doc = self.store.read(identity)
                    records.append({"snapshot_id": identity,
                                    "generated_at": snapshot.inputs()["frame"].generated_at_utc,
                                    "disposition": doc["disposition"], "status": doc["evaluation"].get("status")})
                except (OSError, ValueError, KeyError):
                    records.append({"snapshot_id": identity, "status": "unavailable_or_corrupt"})
            return {"decisions": records, "next_offset": offset + 20 if len(identities) > offset + 20 else None}
        return web.Response(text=canonical(await self.read(read)), content_type="application/json")

    async def decision(self, request):
        identity = request.match_info["identity"]
        view = await self.read(lambda: decision_view(*self.store.read(identity)))
        return web.Response(text=canonical(view), content_type="application/json")

    async def submit(self, request):
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        body = await request.json()
        if set(body) != {"snapshot_id", "kind", "start_index", "end_index"}:
            raise ValueError("expected snapshot_id, kind, start_index and end_index")
        if body["kind"] not in KINDS:
            raise ValueError("unsupported intervention")
        start, end = body["start_index"], body["end_index"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= 672:
            raise ValueError("invalid interval window")
        # Reject excess requests immediately, including concurrent archive reads before a job starts.
        if self.request_lock.locked():
            raise web.HTTPTooManyRequests(text="Another diagnostic request is being prepared")
        async with self.request_lock:
            if (self.task and not self.task.done()) or self.live_busy():
                raise web.HTTPConflict(text="Planner or diagnostic solver busy; retry after it completes")
            if time.monotonic() - self.last_started < self.cooldown:
                raise web.HTTPTooManyRequests(text="Wait 30 seconds between diagnostic requests")
            snapshot, _ = await self.read(lambda: self.store.read(body["snapshot_id"]))
            if end > len(snapshot.inputs()["frame"].intervals):
                raise ValueError("window outside archived horizon")
            identity = uuid.uuid4().hex
            self.jobs = {k: v for k, v in self.jobs.items() if time.monotonic() - v["created"] < 900}
            while len(self.jobs) >= 8:
                self.jobs.pop(next(iter(self.jobs)))
            self.jobs[identity] = {"status": "running", "created": time.monotonic()}
            self.last_started = time.monotonic()
            intervention = {k: v for k, v in body.items() if k != "snapshot_id"}
            self.task = asyncio.create_task(self.run(identity, snapshot, intervention))
            return web.json_response({"job_id": identity, "status": "running"}, status=202)

    async def run(self, identity, snapshot, intervention):
        process = None
        try:
            # Strip HA/database/proxy credentials. The child has no client or live-plan reference.
            environment = {k: v for k, v in os.environ.items()
                           if k in {"PATH", "PYTHONPATH", "VIRTUAL_ENV", "LANG", "TZ"}}
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "energymanager.explanation_worker", stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=environment,
            )
            payload = canonical({"snapshot_id": snapshot.snapshot_id, "payload": snapshot.payload,
                                 "intervention": intervention}).encode()
            stdout, _ = await asyncio.wait_for(process.communicate(payload), self.timeout)
            if process.returncode or len(stdout) > 4 * 1024 * 1024:
                raise ValueError("Diagnostic solver failed or result exceeded size limit")
            self.jobs[identity].update(status="completed", result=json.loads(stdout))
        except TimeoutError:
            self.jobs[identity].update(status="timeout", error="Diagnostic time limit exceeded; live plan unchanged")
        except (OSError, ValueError) as exc:
            self.jobs[identity].update(status="failed", error=str(exc)[:200])
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                # Drain stdout after a cancelled communicate; wait alone can block on a full pipe.
                await process.communicate()

    async def poll(self, request):
        job = self.jobs.get(request.match_info["identity"])
        if not job or time.monotonic() - job["created"] >= 900:
            raise web.HTTPNotFound(text="Diagnostic job expired or not found")
        return web.json_response({k: v for k, v in job.items() if k != "created"})

    async def close(self, app):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


@asynccontextmanager
async def explanation_server(settings, planner_service):
    store = DecisionStore(Path("/data/planner-v3"), max_bytes=settings.archive_max_mb * 1024 * 1024,
                          keep=settings.archive_keep, days=settings.archive_days)
    api = ExplanationAPI(store, live_busy=lambda: planner_service.solve_in_progress)
    runner = web.AppRunner(api.app())
    await runner.setup()
    try:
        await web.TCPSite(runner, "0.0.0.0", 8099).start()
        yield
    finally:
        await runner.cleanup()
