"""One-shot, isolated comparison of MILP secondary optimization time limits."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
from datetime import UTC, datetime
from queue import Empty
from time import perf_counter
from typing import Any

from .milp_planner import evaluate_plan_milp

_LOGGER = logging.getLogger(__name__)
_BENCHMARK_LIMITS_SECONDS = (10, 30, 60, 120)
_BENCHMARK_ENTITY = "sensor.energy_manager_milp_benchmark"


def _benchmark_worker(queue: Any, frame: Any, profile: Any, capacity_state: Any) -> None:
    """Compute four independent solutions of exactly the same frame; never access HA."""
    try:
        # Give the real-time HA controller priority under CPU contention.
        try:
            os.nice(10)
        except OSError:
            pass
        for limit in _BENCHMARK_LIMITS_SECONDS:
            started = perf_counter()
            result = evaluate_plan_milp(
                frame, profile, capacity_state, tie_break_max_time_seconds=float(limit)
            )
            if result.plan is None or result.economic_stage_status is None:
                raise RuntimeError(f"No valid economic solution at {limit}s: {result.status}: {result.reason}")
            stage1 = result.economic_stage_summary or {}
            selected = result.selected_stage_summary or {}
            queue.put({
                "limit_seconds": limit,
                "elapsed_seconds": round(perf_counter() - started, 3),
                "economic_solve_seconds": _rounded(result.economic_solve_time_seconds),
                "tie_break_solve_seconds": _rounded(result.tie_break_solve_time_seconds),
                "economic_status": result.economic_stage_status,
                "tie_break_status": result.tie_break_status,
                "selected_solution_stage": result.selected_solution_stage,
                "mip_gap": _rounded(result.mip_gap, 5),
                "validation_status": result.validation_status,
                "economic_objective_eur": _rounded(result.first_stage_objective_eur, 5),
                "selected_objective_eur": _rounded(result.milp_objective_eur, 5),
                "delta_cost_eur": _rounded(
                    result.milp_objective_eur - result.first_stage_objective_eur, 5
                ) if result.milp_objective_eur is not None and result.first_stage_objective_eur is not None else None,
                "economic_ev_sessions": stage1.get("ev_session_count"),
                "selected_ev_sessions": selected.get("ev_session_count"),
                "economic_ev_delay_score": stage1.get("ev_charge_delay_score_kwh_days"),
                "selected_ev_delay_score": selected.get("ev_charge_delay_score_kwh_days"),
                "economic_charge_before_departure_kwh": stage1.get("ev_charge_before_first_departure_kwh"),
                "selected_charge_before_departure_kwh": selected.get("ev_charge_before_first_departure_kwh"),
                "economic_grid_import_24h_kwh": stage1.get("grid_import_next_24h_kwh"),
                "selected_grid_import_24h_kwh": selected.get("grid_import_next_24h_kwh"),
                "economic_ess_min_soc_24h": stage1.get("ess_min_soc_next_24h_percent"),
                "selected_ess_min_soc_24h": selected.get("ess_min_soc_next_24h_percent"),
            })
    except Exception as exc:
        queue.put({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        queue.put({"complete": True})


def _rounded(value: float | None, digits: int = 3) -> float | None:
    return round(value, digits) if value is not None else None


async def run_milp_benchmark(ha_client: Any, frame: Any, profile: Any, capacity_state: Any) -> None:
    """Run opt-in benchmarking in a killable child; keep live control unaffected."""
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_benchmark_worker, args=(queue, frame, profile, capacity_state),
        daemon=True, name="energy-milp-benchmark",
    )
    results: list[dict[str, Any]] = []
    generated_at = datetime.now(UTC).isoformat()
    started = perf_counter()
    completed = False
    try:
        process.start()
        _LOGGER.info("MILP benchmarking started (10, 30, 60, 120s); frozen %s-interval forecast", len(frame.intervals))
        await _publish(ha_client, "running", generated_at, results)
        while not completed:
            try:
                item = queue.get_nowait()
            except Empty:
                if not process.is_alive():
                    # Allow a short interval for the child queue to flush after process exit.
                    await asyncio.sleep(1)
                    try:
                        item = queue.get_nowait()
                    except Empty:
                        break
                else:
                    await asyncio.sleep(1)
                    continue
            if item.get("complete"):
                completed = True
            elif "error" in item:
                _LOGGER.error("MILP benchmark worker failed: %s", item["error"])
                results.append(item)
            else:
                results.append(item)
                _LOGGER.info(
                    "MILP benchmark limit=%ss, elapsed=%.1fs, sessions=%s->%s, "
                    "cost_delta=%s EUR, gap=%s, status=%s",
                    item["limit_seconds"], item["elapsed_seconds"],
                    item["economic_ev_sessions"], item["selected_ev_sessions"],
                    item["delta_cost_eur"], item["mip_gap"], item["tie_break_status"],
                )
            await _publish(ha_client, "running", generated_at, results)
        state = "complete" if completed and len(results) == len(_BENCHMARK_LIMITS_SECONDS) else "error"
        _LOGGER.info("MILP benchmark %s: %.1fs, %d/%d completed", state, perf_counter() - started,
                     len(results), len(_BENCHMARK_LIMITS_SECONDS))
        await _publish(ha_client, state, generated_at, results)
    except asyncio.CancelledError:
        _LOGGER.info("MILP benchmark cancelled during add-on shutdown")
        raise
    except Exception:
        _LOGGER.exception("MILP benchmark coordinator failed; live control unaffected")
    finally:
        if process.is_alive():
            process.terminate()
        if process.pid is not None:
            await asyncio.to_thread(process.join, 3.0)
        queue.close()


async def _publish(ha_client: Any, status: str, generated_at: str, results: list[dict[str, Any]]) -> None:
    try:
        await ha_client.set_state(_BENCHMARK_ENTITY, status, {
            "friendly_name": "Energy Manager MILP Benchmark",
            "snapshot_utc": generated_at,
            "limits_seconds": list(_BENCHMARK_LIMITS_SECONDS),
            "results": list(results),
            "completed_runs": len(results),
            "expected_runs": len(_BENCHMARK_LIMITS_SECONDS),
            "read_only": True,
        })
    except Exception as exc:
        _LOGGER.warning("MILP benchmark status publishing failed: %s", exc)
