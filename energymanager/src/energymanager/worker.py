"""One cancellable planning process, with no actuator or database authority."""

from __future__ import annotations

import os
import asyncio
from collections.abc import Callable
from multiprocessing import parent_process, get_context
from multiprocessing.process import BaseProcess
from threading import Thread
from time import sleep
from traceback import format_exc
from typing import Any, Protocol

from .planner import plan_snapshot

Calculation = Callable[[dict[str, Any], Callable[[str], None]], dict[str, Any]]


class WorkerExited(RuntimeError):
    """The isolated process died before returning a result."""


class WorkerPipe(Protocol):
    """The shared interface of Windows named pipes and POSIX pipe connections."""

    def send(self, value: Any) -> None: ...
    def recv(self) -> Any: ...
    def close(self) -> None: ...


def calculate_in_process(data: dict[str, Any], sender: WorkerPipe, calculate: Calculation) -> None:
    """Send real stage changes and the result over the private parent pipe."""
    watch_parent()
    try:
        result = calculate(data, lambda stage: sender.send(("stage", stage)))
        sender.send(("result", result))
    except Exception:
        sender.send(("error", format_exc()[-8000:]))
    finally:
        sender.close()


def stop_process(process: BaseProcess, receiver: WorkerPipe) -> None:
    """Reap this worker before another can start; never wait under the control lock."""
    try:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(2)
            if process.is_alive():
                process.kill()
                process.join(2)
            if process.is_alive():
                raise RuntimeError("The cancelled planning worker could not be stopped")
        process.close()
    finally:
        receiver.close()


class PlanningWorker:
    """Own a fresh spawn process per solve, including cancellation and pipe cleanup."""

    def __init__(self, calculate: Calculation = plan_snapshot) -> None:
        self.calculate = calculate
        self.process: BaseProcess | None = None
        self.receiver: WorkerPipe | None = None
        self.cleanup: asyncio.Task[None] | None = None

    async def run(self, data: dict[str, Any], progress: Callable[[str], None]) -> dict[str, Any]:
        if self.process is not None:
            raise RuntimeError("A planning worker is already active")
        context = get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=calculate_in_process, args=(data, sender, self.calculate), daemon=True)
        self.process, self.receiver = process, receiver
        launch = asyncio.create_task(asyncio.to_thread(process.start))
        try:
            await asyncio.shield(launch)
            sender.close()
            while True:
                try:
                    kind, body = await asyncio.to_thread(receiver.recv)
                except EOFError as exc:
                    raise WorkerExited("The planning worker exited without a result") from exc
                if kind == "stage":
                    progress(body)
                elif kind == "result":
                    return body
                else:
                    raise RuntimeError("Planning worker failed:\n" + body)
        finally:
            # Cancellation during spawn must still wait for and reap that exact child.
            try:
                await asyncio.shield(launch)
            finally:
                sender.close()
                await self.close()

    async def close(self) -> None:
        if self.cleanup is None and self.process is not None and self.receiver is not None:
            self.cleanup = asyncio.create_task(asyncio.to_thread(stop_process, self.process, self.receiver))
        if self.cleanup is not None:
            await asyncio.shield(self.cleanup)
        self.process = self.receiver = self.cleanup = None


def watch_parent() -> None:
    parent = parent_process()
    if parent is None:
        return

    def monitor() -> None:
        while parent.is_alive():
            sleep(1)
        os._exit(0)  # Only this isolated worker; no actuator or database exists here.

    Thread(target=monitor, daemon=True, name="solver-parent-watch").start()
