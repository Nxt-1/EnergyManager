"""V3 acceptance coverage using actual HiGHS and frozen, synthetic inputs."""

from __future__ import annotations

import asyncio
import gzip
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from test_milp_planner import _capacity, _ess, _ev, _profile, _reference_plan, _task

from energymanager.config import EvSettings, EvWeeklyScheduleEntry, PlannerSettings, Settings
from energymanager.counterfactual import CounterfactualRequest, compare
from energymanager.decision_store import DecisionStore, PlanningSnapshot, canonical, decode, encode
from energymanager.hierarchy import HierarchyPolicy
from energymanager.milp_planner import evaluate_plan_milp
from energymanager.requirements import FlexibleJob, Provenance, StorageResource, explain_ev_tasks
from energymanager.tasks import TaskRegistry, _available_hours, _combine_local

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)
POLICY = HierarchyPolicy(total_seconds=4, economic_seconds=2)


def frame():
    return _reference_plan(NOW, tasks=(_task(NOW),))


def snapshot(plan=None, **kwargs):
    plan = plan or frame()
    return PlanningSnapshot.create(plan, _profile(), _capacity(NOW), POLICY, **kwargs)


def test_actual_highs_hierarchy_locks_every_priority_and_reconciles_cost():
    result = snapshot().solve()
    assert result.adoption_ready, result.reason
    assert result.validation_status == "passed"
    assert [s.name for s in result.stages] == ["economics", "robustness", "operations", "stability", "deterministic"]
    economic, robust, *_ = result.stages
    assert result.milp_objective_eur <= economic.objective + economic.tolerance + 1e-5
    assert result.time_weighted_grid_import_score <= robust.objective + robust.tolerance + 1e-5
    accounting = result.selected_stage_accounting
    assert accounting["incremental_objective_eur"] == pytest.approx(result.milp_objective_eur, abs=3e-5)
    cost = result.milp_cost
    assert cost.objective_eur == pytest.approx(
        cost.net_energy_cost_eur
        + cost.incremental_capacity_cost_eur
        - cost.terminal_ess_value_eur
        + result.preferred_ev_shortfall_penalty_eur
    )
    assert accounting["sunk_capacity_baseline_eur"] > 0
    assert all(s.plan is not None for s in result.stages if s.accepted)


def test_snapshot_roundtrip_retains_inputs_and_material_result(tmp_path):
    frozen = snapshot()
    first = frozen.solve()
    store = DecisionStore(tmp_path)
    store.save(frozen, first, disposition="accepted")
    loaded, document = store.read(frozen.snapshot_id)
    assert loaded.payload == frozen.payload
    assert loaded.inputs()["frame"] == frame()
    second = loaded.solve()
    assert second.adoption_ready
    assert second.milp_objective_eur == pytest.approx(first.milp_objective_eur, abs=1e-6)
    assert second.ev_session_count == first.ev_session_count
    assert [i.scheduled_load_w for i in second.plan.intervals] == pytest.approx(
        [i.scheduled_load_w for i in first.plan.intervals], abs=1e-4
    )
    assert "indeterminate" in document["attribution"]


def test_counterfactual_is_quantitative_and_cannot_mutate_live_or_frozen_plan():
    frozen = snapshot()
    before = frozen.payload
    result = compare(frozen, CounterfactualRequest("forbid_ev", 0, 4))
    assert result["baseline"].adoption_ready
    assert result["alternative"].adoption_ready
    assert result["delta"]["objective_eur"] is not None
    assert result["delta"]["ev_sessions"] is not None
    assert all(i.scheduled_load_w < 1e-6 for i in result["alternative"].plan.intervals[:4])
    assert frozen.payload == before


def test_counterfactual_joint_infeasibility_does_not_claim_a_minimal_cause():
    result = compare(snapshot(), CounterfactualRequest("forbid_ev", 0, 8))
    assert result["alternative"].status == "infeasible"
    assert not result["alternative"].adoption_ready
    assert result["delta"] is None
    assert "no minimal" in result["infeasibility"]


def test_continuous_counterfactual_has_no_quarter_hour_gaps():
    result = compare(snapshot(), CounterfactualRequest("continuous_ev", 0, 4))
    assert result["alternative"].adoption_ready
    assert all(i.scheduled_load_w >= 1380 - 1e-4 for i in result["alternative"].plan.intervals[:4])


@pytest.mark.parametrize("intervention", [("forbid_ev", -1, 3), ("forbid_ev", 0, 900), ("source_attribution", 0, 1)])
def test_unrepresentable_counterfactuals_reject_safely(intervention):
    result = snapshot().solve(restrictions=(intervention,))
    assert not result.adoption_ready
    assert result.reason


def test_weekly_ev_provenance_trip_carryover_and_independent_soft_target():
    settings = EvSettings(
        battery_capacity_kwh=46.8,
        minimum_soc_percent=50,
        target_soc_percent=80,
        weekly_schedule=(EvWeeklyScheduleEntry((3, 4), "17:00", "19:00", 50, 10),),
    )
    actuators = (_ess(), _ev())
    tasks = TaskRegistry(settings).snapshots(actuators, now_utc=NOW, local_tz=UTC)
    requirements = explain_ev_tasks(tasks, actuators, NOW)
    hard = [r for r in requirements if r.hard]
    assert hard[0].amount == 50
    assert dict(hard[0].provenance.parameters)["mandatory_ac_kwh"] == 0
    assert dict(hard[1].provenance.parameters)["mandatory_ac_kwh"] == pytest.approx(10 / 0.9)
    assert dict(hard[1].provenance.parameters)["trip_energy_before_kwh"] == 10
    assert requirements[-1].hard is False
    assert requirements[-1].amount == 80
    assert "charge_efficiency" in hard[1].provenance.formula
    assert requirements == explain_ev_tasks(tasks, actuators, NOW)


def test_generator_replay_uses_frozen_settings_and_timezone():
    settings = EvSettings(
        battery_capacity_kwh=46.8, minimum_soc_percent=50, target_soc_percent=80, departure_time_local="13:00"
    )
    base = frame()
    tasks = TaskRegistry(settings).snapshots(base.actuator_snapshots, now_utc=NOW, local_tz=UTC)
    frozen = snapshot(replace(base, tasks=tasks), ev_settings=settings)
    assert frozen.regenerate() == tasks


def test_missing_connection_and_soc_are_not_measured_zero():
    ev = replace(_ev(), connected=None, soc_percent=None)
    tasks = TaskRegistry(EvSettings(battery_capacity_kwh=46.8)).snapshots((ev,), now_utc=NOW, local_tz=UTC)
    assert not tasks[0].planning_available
    assert tasks[0].required_energy_kwh is None
    assert tasks[0].current_soc_percent is None


def test_infeasible_departure_is_not_softened():
    task = replace(_task(NOW), minimum_soc_percent=100, latest_end_local=NOW + timedelta(minutes=15))
    result = snapshot(replace(frame(), tasks=(task,))).solve()
    assert result.status == "infeasible"
    assert not result.adoption_ready
    assert result.stages[0].accepted is False


def test_preference_is_neither_tomorrow_minimum_nor_physical_cap():
    settings = EvSettings(
        battery_capacity_kwh=46.8, minimum_soc_percent=50, target_soc_percent=80, departure_time_local="13:00"
    )
    ev = replace(_ev(), soc_percent=90)
    task = TaskRegistry(settings).snapshots((ev,), now_utc=NOW, local_tz=UTC)[0]
    assert task.minimum_soc_percent == 50
    assert task.required_energy_kwh == 0
    assert task.current_soc_percent == 90


def test_mixed_interruptible_and_cycle_jobs_use_shared_grid_and_energy_balance():
    provenance = Provenance("synthetic", "1", NOW, ("test_policy",), "valid", "sum(power)*0.25", ())
    jobs = (
        FlexibleJob("water", "dhw", NOW, NOW + timedelta(hours=2), 1, 2, provenance),
        FlexibleJob("wash", "washer", NOW, NOW + timedelta(hours=2), 0.75, 2, provenance, cycle_kw=(2, 1)),
    )
    result = snapshot(replace(frame(), jobs=jobs)).solve()
    assert result.adoption_ready, result.reason
    powers = {job.job_id: [dict(i.job_power_w)[job.job_id] for i in result.plan.intervals] for job in jobs}
    assert sum(powers["water"]) * 0.25 / 1000 == pytest.approx(1)
    assert sum(powers["wash"]) * 0.25 / 1000 == pytest.approx(0.75)
    first = next(i for i, power in enumerate(powers["wash"]) if power > 1)
    assert powers["wash"][first : first + 2] == pytest.approx([2000, 1000])
    for interval in result.plan.intervals:
        assert interval.grid_power_after_ess_w == pytest.approx(
            interval.total_load_w - interval.pv_ac_power_w - interval.ess_ac_power_w
        )


def test_generic_storage_contract_distinguishes_resource_from_job():
    assert StorageResource("thermal", 10, 5, 2, 0.9).reserve_kwh == 2
    with pytest.raises(ValueError):
        StorageResource("bad", 10, 5, 6, 0.9)


def test_snapshot_corruption_and_unsupported_schema_are_explicit(tmp_path):
    frozen = snapshot()
    store = DecisionStore(tmp_path)
    store.save(frozen, frozen.solve(), disposition="accepted")
    path = tmp_path / (frozen.snapshot_id + ".json.gz")
    data = json.loads(gzip.decompress(path.read_bytes()))
    data["snapshot"]["frame"]["intervals"][0]["background_load_w"] = 987
    path.write_bytes(gzip.compress(json.dumps(data).encode()))
    with pytest.raises(ValueError, match="checksum"):
        store.read(frozen.snapshot_id)
    with pytest.raises(ValueError, match="invalid snapshot ID"):
        store.read("../options")
    with pytest.raises(ValueError, match="unknown archive type"):
        decode({"$type": "Popen", "args": "bad"})


def test_retention_is_bounded_and_failed_write_preserves_existing(tmp_path):
    store = DecisionStore(tmp_path, keep=1)
    first = snapshot()
    result = first.solve()
    store.save(first, result, disposition="accepted")
    later = snapshot(replace(frame(), generated_at_utc=NOW + timedelta(seconds=1)))
    store.save(later, result, disposition="rejected")
    assert store.list_ids() == (later.snapshot_id,)
    limited = DecisionStore(tmp_path, max_bytes=1024)
    with pytest.raises(ValueError, match="byte limit"):
        limited.save(first, result, disposition="rejected")
    assert store.read(later.snapshot_id)[0] == later


def test_dst_physical_elapsed_hours_and_nonexistent_deadline_policy():
    zone = ZoneInfo("Europe/Brussels")
    spring = _combine_local(datetime(2026, 3, 29).date(), "02:30", zone)
    assert spring.hour == 3  # explicit forward normalization
    autumn = _combine_local(datetime(2026, 10, 25).date(), "02:30", zone)
    assert autumn.fold == 0
    start = datetime(2026, 10, 25, 1, tzinfo=zone)
    end = datetime(2026, 10, 25, 4, tzinfo=zone)
    assert _available_hours(start, end, ()) == 4
    assert decode(encode(autumn)) == autumn


def test_v3_config_roundtrip_preserves_explicit_device_permissions(tmp_path):
    path = tmp_path / "options.json"
    path.write_text(
        json.dumps(
            {
                "ess": {"control_enabled": True, "setpoint_entity": "number.ess"},
                "ev": {
                    "control_enabled": True,
                    "current_entity": "number.ev",
                    "phase_mode_entity": "select.phase",
                    "force_state_entity": "select.force",
                },
            }
        )
    )
    settings = Settings.load(path)
    assert settings.ess.control_enabled and settings.ev.control_enabled
    path.write_text(json.dumps(settings.as_options()))
    assert Settings.load(path) == settings
    assert PlannerSettings().hierarchy_policy().economic_tolerance_eur == 0.01


@pytest.mark.parametrize(
    "kwargs",
    [
        {"economic_tolerance_eur": -1},
        {"robustness_tolerance_kwh": 100},
        {"total_seconds": float("nan")},
        {"grid_import_limit_kw": 0},
    ],
)
def test_invalid_hierarchy_tolerances_rejected(kwargs):
    with pytest.raises(ValueError):
        HierarchyPolicy(**kwargs)


def test_disabled_devices_block_startup_fallback_private_writes_reset_and_shutdown():
    from energymanager.config import EssSettings
    from energymanager.ess_control import EssHardwareController
    from energymanager.ev_control import EvHardwareController

    class Client:
        writes = []

        async def call_service(self, *args):
            self.writes.append(args)

        async def set_state(self, *args):
            pass

    client = Client()
    ess = EssHardwareController(
        client, EssSettings(control_enabled=False, setpoint_entity="number.test")
    )
    ev = EvHardwareController(
        client,
        EvSettings(
            control_enabled=False,
            current_entity="number.test",
            phase_mode_entity="select.phase",
            force_state_entity="select.force",
            automatic_fault_reset=True,
            reset_button_entity="button.reset",
        ),
    )

    async def run():
        await ess.initialize()
        await ev.initialize()
        await ess.safe_zero("test", force=True)
        await ev.safe_stop("test")
        await ev._write_number("number.test", 6, "test")
        await ev._write_select("select.force", "off", "test")
        await ev._client.call_service("button", "press", {"entity_id": "button.reset"})
        await ess.shutdown()
        await ev.shutdown()

    asyncio.run(run())
    assert not ess.enabled and not ev.enabled
    assert client.writes == []


def test_snapshot_identity_is_content_based_and_immutable():
    frozen = snapshot()
    assert frozen.snapshot_id == snapshot().snapshot_id
    assert "SUPERVISOR_TOKEN" not in frozen.payload
    assert json.loads(canonical(frozen.inputs()))["schema_version"] == 1


def test_grid_limit_is_hard_and_unknown_peak_is_not_zero():
    result = evaluate_plan_milp(frame(), _profile(), _capacity(NOW), policy=replace(POLICY, grid_import_limit_kw=0.1))
    assert result.adoption_ready or result.status == "infeasible"
    if result.plan:
        assert max(i.grid_power_after_ess_w for i in result.plan.intervals) <= 100.001
    unavailable = evaluate_plan_milp(frame(), _profile(), replace(_capacity(NOW), observed_peak_kw=None))
    assert not unavailable.adoption_ready
    assert unavailable.reason == "capacity_history_incomplete"


def test_stale_solve_is_archived_as_superseded_and_latest_context_is_solved(monkeypatch, tmp_path):
    import threading

    from test_planner_service import (
        FakeEconomicsService,
        FakeHomeAssistantClient,
        FakeLoadService,
        FakePvService,
        _forecasts,
        _house_state,
        _settings,
        _solved_evaluation,
    )

    from energymanager.actuators import ActuatorRegistry
    from energymanager.planner_service import PlannerService

    load, pv = _forecasts(NOW)
    load_service = FakeLoadService(load)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def slow(frame, *args, **kwargs):
        calls.append(frame)
        if len(calls) == 1:
            entered.set()
            assert release.wait(2)
        return _solved_evaluation(frame)

    monkeypatch.setattr("energymanager.planner_service.evaluate_plan_milp", slow)
    store = DecisionStore(tmp_path)
    service = PlannerService(
        FakeHomeAssistantClient(),
        load_service,
        FakePvService(pv),
        actuator_registry=ActuatorRegistry(_settings()),
        task_registry=TaskRegistry(Settings().ev),
        economics_service=FakeEconomicsService(NOW),
        decision_store=store,
    )

    async def run():
        state = _house_state(NOW)
        await service.update_from_house_state(state, now_utc=NOW)
        assert await asyncio.to_thread(entered.wait, 2)
        load_service.forecast = replace(load, generated_at_utc=NOW + timedelta(seconds=1))
        await service.update_from_house_state(state, now_utc=NOW + timedelta(seconds=1))
        release.set()
        while service.solve_in_progress:
            await service._solve_task
        assert service.plan.generated_at_utc == NOW + timedelta(seconds=1)
        await service.shutdown()

    asyncio.run(run())
    assert len(calls) == 2
    dispositions = {store.read(i)[1]["disposition"] for i in store.list_ids()}
    assert dispositions == {"superseded", "accepted"}


def test_archive_failure_does_not_remove_validated_plan(monkeypatch):
    from test_planner_service import (
        FakeEconomicsService,
        FakeHomeAssistantClient,
        FakeLoadService,
        FakePvService,
        _forecasts,
        _house_state,
        _settings,
        _solved_evaluation,
    )

    from energymanager.actuators import ActuatorRegistry
    from energymanager.planner_service import PlannerService

    class BrokenStore:
        def save(self, *args, **kwargs):
            raise OSError("disk full")

    monkeypatch.setattr(
        "energymanager.planner_service.evaluate_plan_milp", lambda frame, *a, **kw: _solved_evaluation(frame)
    )
    load, pv = _forecasts(NOW)
    client = FakeHomeAssistantClient()
    service = PlannerService(
        client,
        FakeLoadService(load),
        FakePvService(pv),
        actuator_registry=ActuatorRegistry(_settings()),
        task_registry=TaskRegistry(Settings().ev),
        economics_service=FakeEconomicsService(NOW),
        decision_store=BrokenStore(),
    )

    async def run():
        await service.update_from_house_state(_house_state(NOW), now_utc=NOW)
        await service._solve_task
        assert service.plan is not None
        assert client.states["sensor.energy_manager_v3_decision"]["attributes"]["persisted"] is False
        await service.shutdown()

    asyncio.run(run())


def test_defer_discretionary_imports_when_departure_minimum_already_met():
    # No PV, lossy ESS at reserve. Soft-target penalty equals marginal import cost;
    # buying early has no proven economic advantage and should not be pulled forward.
    base = frame()
    ess = replace(_ess(), soc_percent=10)
    task = replace(
        _task(NOW), required_energy_kwh=0, minimum_soc_percent=50, preferred_energy_kwh=15.6, target_soc_percent=80
    )
    base = replace(base, tasks=(task,), actuator_snapshots=(ess, _ev()), ess_initial_soc_percent=10)
    result = snapshot(base).solve()
    assert result.adoption_ready
    assert result.plan.intervals[0].scheduled_load_w == pytest.approx(0, abs=1e-5)
    assert result.preferred_ev_shortfall_kwh > 0


def test_stability_has_explicit_near_term_evidence():
    first = snapshot().solve()
    updated = replace(
        frame(), intervals=tuple(replace(i, background_load_w=i.background_load_w + 20) for i in frame().intervals)
    )
    result = snapshot(updated, previous_plan=first.plan).solve()
    assert result.adoption_ready
    stability = next(s for s in result.stages if s.name == "stability")
    assert stability.unit == "kWh"
    assert stability.objective is not None
    assert result.milp_objective_eur <= result.stages[0].objective + POLICY.economic_tolerance_eur + 1e-5


def test_missing_forecast_timestep_cannot_be_treated_as_zero():
    base = frame()
    result = snapshot(replace(base, intervals=base.intervals[:2] + base.intervals[3:])).solve()
    assert not result.adoption_ready
    assert result.reason == "nonuniform_forecast_grid"


def test_generic_thermal_storage_dynamics_and_state_deadline_share_the_scheduler():
    from energymanager.requirements import Requirement

    provenance = Provenance("thermal_example", "1", NOW, ("synthetic_policy",), "valid",
                            "stored_next = stored + .25 * input_kw * efficiency - draw_kwh", ())
    resource = StorageResource("thermal", 8, 1, 0, 1, max_input_kw=3,
                               withdrawals_kwh=(0, 0, 0, 0, 1, 0, 0, 0))
    requirement = Requirement("hot_water", "thermal", "state_by_deadline", True, 3, "kWh",
                              NOW, NOW + timedelta(hours=1), True, provenance)
    result = snapshot(replace(frame(), resources=(resource,), requirements=(requirement,))).solve()
    assert result.adoption_ready, result.reason
    assert dict(result.plan.intervals[3].resource_energy_kwh)["thermal"] >= 3 - 1e-6
    before = 1
    for i, interval in enumerate(result.plan.intervals):
        charge_kw = dict(interval.job_power_w)["thermal"] / 1000
        energy = dict(interval.resource_energy_kwh)["thermal"]
        assert energy == pytest.approx(before + .25 * charge_kw - resource.withdrawals_kwh[i])
        before = energy


def test_two_cycles_cannot_occupy_the_same_physical_appliance_simultaneously():
    provenance = Provenance("synthetic", "1", NOW, (), "valid", "cycle", ())
    jobs = tuple(FlexibleJob(str(i), "washer", NOW, NOW + timedelta(minutes=45), 1, 2,
                             provenance, cycle_kw=(2, 2)) for i in range(2))
    result = snapshot(replace(frame(), jobs=jobs)).solve()
    assert result.status == "infeasible"
    assert not result.adoption_ready


def test_non_quarter_deadline_conservatively_uses_the_preceding_state():
    task = replace(_task(NOW), minimum_soc_percent=55, latest_end_local=NOW + timedelta(minutes=35))
    result = snapshot(replace(frame(), tasks=(task,))).solve()
    assert result.adoption_ready
    assert result.plan.intervals[1].projected_ev_soc_percent >= 55 - 1e-5


def test_live_grid_ceiling_reduces_ev_even_with_exhausted_ess_capacity():
    from test_fast_dispatch import _NOW, _plan, _registry, _state

    from energymanager.fast_dispatch import evaluate_fast_dispatch

    result = evaluate_fast_dispatch(_plan(planned_grid_w=4000, planned_ess_w=0, planned_ev_w=6000),
                                    _state(grid_w=7000, ess_w=0, ev_w=3000), _registry(), now_utc=_NOW,
                                    live_control=True, grid_import_limit_w=4500)
    ev = next(command for command in result.command_results if command.actuator_id == "ev")
    # 4 kW household - 2 kW maximum ESS leaves <= 2.5 kW for EV.
    assert ev.accepted_power_w <= 2500


def test_timeout_status_is_not_labelled_optimal():
    from energymanager.milp_planner import _status_from_model

    assert _status_from_model("Time limit reached", has_solution=True) == "feasible_time_limit"
    assert _status_from_model("Time limit reached", has_solution=False) == "time_limit_no_solution"


def test_dispatch_never_executes_a_future_interval_early():
    from test_fast_dispatch import _NOW, _plan, _registry, _state

    from energymanager.fast_dispatch import evaluate_fast_dispatch

    old = _plan(planned_grid_w=4000, planned_ess_w=0, planned_ev_w=6000)
    future = replace(old, intervals=(replace(old.intervals[0], period_start_local=_NOW + timedelta(minutes=15)),))
    result = evaluate_fast_dispatch(future, _state(grid_w=500, ess_w=0), _registry(), now_utc=_NOW)
    assert result.status == "unavailable"
    assert result.command_results == ()


def test_future_replan_preserves_the_previous_current_interval(monkeypatch):
    from types import SimpleNamespace

    from test_fast_dispatch_reliability import FakeController, _service

    service = _service(ess=FakeController())
    from energymanager.control_health import ControlHealth

    health = ControlHealth(
        state="healthy", ess_available=True, ev_available=True,
        stale_inputs=(), unavailable_inputs=(), reasons=(), replan_required=False, held_inputs=(),
    )
    monkeypatch.setattr(service, "_evaluate_control_health", lambda state, now: health)
    now = datetime.now(UTC)
    current = replace(frame(), generated_at_utc=now,
                      intervals=(replace(frame().intervals[0], period_start_local=now - timedelta(minutes=1)),))
    future = replace(
        current, intervals=(replace(current.intervals[0], period_start_local=now + timedelta(minutes=14)),)
    )
    service._plan, service._dispatch_previous_plan = future, current
    selected = []

    def dispatch(plan, *args, **kwargs):
        selected.append(plan)
        return SimpleNamespace(command_results=(), replan_required=False)

    monkeypatch.setattr("energymanager.planner_service.evaluate_fast_dispatch", dispatch)
    asyncio.run(service._run_fast_dispatch_once())
    assert selected == [current]
