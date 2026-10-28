"""Synthetic archives and charger readbacks; startup recovery never calls a live service."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import json

import pytest

from energymanager.configuration import configured_application, create_configuration_if_missing
from energymanager.control import GuardedActuator
from energymanager.domain import Goal
from energymanager.ev_faults import EVFaults
from energymanager.hardware import HardwareControl
from energymanager.publication import admit
from energymanager.settings import ConfigurationFile, SETTING_FIELDS
from energymanager.store import Store
from test_first_slice import tiny
from test_goe import ChargerFixture
from test_publication_closed_loop import result_for, scheduled_flows


class RecoveryFixture:
    def __init__(self, directory, *, travel=False):
        self.directory = directory
        self.charger = ChargerFixture()
        self.charger.set("force", 2)
        self.charger.set("charger_status", 3)
        self.charger.refresh()
        self.path = directory / "configuration.json"
        create_configuration_if_missing(self.path)
        config = json.loads(self.path.read_bytes())
        config["home_assistant_url"] = "http://127.0.0.1:1/api"
        config["token_environment"] = "SYNTHETIC_UNUSED_TOKEN"
        for field in SETTING_FIELDS:
            if field.kind == "entity" and field.required:
                group, key = field.path.split(".")
                config[group][key] = f"{field.domains[0]}.synthetic_{key}"
        config["actuators"].update(self.charger.actuators)
        config["ev_diagnostics"].update(self.charger.diagnostics)
        self.path.write_text(json.dumps(config), encoding="utf-8")
        self.database = directory / "synthetic.sqlite"
        store = Store(self.database)
        store.put("hardware_control_enabled", True)
        source_app = configured_application(self.path, store)
        source_app.hardware = HardwareControl(source_app, ConfigurationFile(self.path, mode="configured"))
        policy = replace(source_app.policy, control_enabled=True)
        base = tiny(hours=4, ev=24, ess=7)
        shift = self.charger.at - timedelta(seconds=20) - base.observation.at
        intervals = tuple(replace(i, start=i.start + shift, end=i.end + shift,
                                  withdrawal_kwh=.1 if travel and t == 0 else 0)
                          for t, i in enumerate(base.intervals))
        self.snapshot = replace(base, policy=policy, capabilities=source_app.snapshot.capabilities,
                                observation=replace(base.observation, at=base.observation.at + shift),
                                forecast_at=base.forecast_at + shift, intervals=intervals,
                                goals=(Goal("goal", "SYNTHETIC charge", intervals[-1].end, 41.8 if travel else 42),))
        source_app.policy = policy
        source_app.goals = self.snapshot.goals
        store.put("goals", source_app.goals)
        rates = [1.38 if i.start < self.snapshot.observation.at + timedelta(hours=1) else 0
                 for i in intervals]
        plan = result_for(self.snapshot, scheduled_flows(self.snapshot, rates))
        plan["input_digest"] = self.snapshot.digest
        live = replace(self.snapshot.observation, at=self.charger.at)
        self.plan, errors = admit(self.snapshot, plan, live, self.charger.at)
        assert not errors, errors
        source_app.plan_recovery.stamp(self.plan)
        store.record(self.snapshot, self.plan, "accepted")
        store.close()
        self.app = None

    def restart(self):
        app = configured_application(self.path, Store(self.database))
        app.now = lambda: self.charger.at
        app.observation = replace(self.snapshot.observation, at=self.charger.at, ev_power_kw=1.38)
        app.actuator = GuardedActuator(self.charger, self.charger.actuators, app.snapshot.capabilities,
                                      generation=lambda: app.revision, charger=self.charger.readings)
        app.ev_faults = EVFaults(app, "", self.charger.diagnostics)
        editor = ConfigurationFile(self.path, mode="configured")

        async def inventory():
            loaded = editor.read()["values"]
            return {"entities": [{"entity_id": loaded[f.path], "state": "1",
                                  "unit": f.units[0] if f.units else None}
                                 for f in SETTING_FIELDS if f.kind == "entity" and f.required]}

        editor.entities = inventory
        app.hardware = HardwareControl(app, editor)
        self.app = app
        return app

    async def close(self):
        if self.app:
            await asyncio.gather(*self.app.protective_tasks, return_exceptions=True)
            self.app.store.close()


async def test_restart_resumes_before_a_blocked_optimizer_and_shutdown_still_stops(tmp_path, monkeypatch):
    f = RecoveryFixture(tmp_path)
    app = f.restart()
    entered = asyncio.Event()
    blocked = asyncio.Event()

    captured = []

    async def calculate(snapshot):
        captured.append(snapshot)
        entered.set()
        await blocked.wait()

    monkeypatch.setattr(app, "run_calculation", calculate)
    app.forecast_data = {"issued_at": f.snapshot.forecast_at.isoformat(), "revision": f.snapshot.forecast_id,
                         "provenance": "SYNTHETIC complete forecast", "intervals": [{
                             "start": f.snapshot.intervals[0].start.isoformat(),
                             "end": (f.charger.at + timedelta(hours=168)).isoformat(),
                             "house_kw": .4, "pv_ac_kw": 0, "pv_dc_kw": 0}]}
    app.planning = asyncio.create_task(app.planning_loop())
    app.control_task = asyncio.create_task(app.control_loop())
    app.request_plan("startup")
    try:
        await app.hardware.set_requested(True)
        await asyncio.gather(*app.protective_tasks)
        await asyncio.wait_for(entered.wait(), 2)
        assert app.plan_recovery.state == "restored" and app.ev_valid and app.ess_valid
        assert app.accepted == f.plan and app.revision != app.accepted["revision"]
        assert app.snapshot.forecast_id == f.snapshot.forecast_id
        assert captured[0].hold_ev_kw == pytest.approx(1.38)
        assert not any(c[2].get("option") == "1" for c in f.charger.calls)
        async with asyncio.timeout(3):
            while app.current_command is None or app.current_command.current_a != 6:
                await asyncio.sleep(.01)
        assert not blocked.is_set() and app.current_command.ev_kw == pytest.approx(1.38)
        assert app.state()["plan_recovery"]["revision"] == app.revision
        await app.close()
        assert any(c[2].get("option") == "1" for c in f.charger.calls)
    finally:
        app.shutdown = True
        for task in (app.planning, app.control_task):
            task.cancel()
        await asyncio.gather(app.planning, app.control_task, return_exceptions=True)
        await f.close()


@pytest.mark.parametrize("problem", ["legacy", "changed_goal", "changed_permission", "changed_settings",
                                    "changed_capability", "changed_policy", "tampered_flow", "corrupt_archive",
                                    "compressed_corruption", "invalid_context", "elapsed", "stale_forecast", "disconnected", "fault", "hardware_off"])
async def test_incompatible_or_revoked_work_never_regains_authority(tmp_path, problem):
    f = RecoveryFixture(tmp_path)
    app = f.restart()
    if problem == "legacy":
        del app.accepted["execution_context"]
    elif problem == "changed_goal":
        app.goals = (replace(app.goals[0], target_soc_percent=60, revision=2),)
    elif problem == "changed_permission":
        app.store.put("daily_approvals", {"synthetic": {"state": "rejected"}})
    elif problem == "changed_settings":
        config = json.loads(f.path.read_bytes())
        config["actuators"]["current"] = "number.other_synthetic_car"
        f.path.write_text(json.dumps(config), encoding="utf-8")
        app.hardware.configuration.started_values = app.hardware.configuration.values(config)
    elif problem == "changed_capability":
        app.snapshot = replace(app.snapshot, capabilities=replace(app.snapshot.capabilities, maximum_current_a=15))
    elif problem == "changed_policy":
        app.policy = replace(app.policy, automatic_peak_kw=3)
    elif problem == "tampered_flow":
        app.accepted["flows"]["grid_ev"][0] += 1
    elif problem == "corrupt_archive":
        with app.store.connection:
            app.store.connection.execute("UPDATE decisions SET snapshot='{}'")
    elif problem == "compressed_corruption":
        with app.store.connection:
            app.store.connection.execute("UPDATE decisions SET snapshot=?", (b"SYNTHETIC corrupt compressed data",))
    elif problem == "invalid_context":
        app.accepted["execution_context"] = None
    elif problem in ("elapsed", "stale_forecast"):
        f.charger.refresh(5 * 3600 if problem == "elapsed" else 3 * 3600)
        app.observation = replace(app.observation, at=f.charger.at)
    elif problem == "disconnected":
        app.observation = replace(app.observation, connected=False)
    elif problem == "fault":
        app.actuator.delivery_fault = True
    elif problem == "hardware_off":
        await app.hardware.set_requested(False)
    try:
        await app.hardware.set_requested(True)
        await asyncio.gather(*app.protective_tasks)
        assert not app.ev_valid and not app.ess_valid
        assert app.plan_recovery.state != "restored"
        assert not any(c[2].get("option") == "2" for c in f.charger.calls)
    finally:
        await f.close()


@pytest.mark.parametrize("problem", ["measurement", "phase", "charger"])
async def test_fresh_readiness_can_restore_without_a_solve(tmp_path, problem):
    f = RecoveryFixture(tmp_path)
    app = f.restart()
    if problem == "measurement":
        app.observation = replace(app.observation, at=f.charger.at - timedelta(seconds=31))
    elif problem == "phase":
        app.observation = replace(app.observation, ev_phase_known=False)
    else:
        f.charger.readings.device_at = None
    app.actuator.enabled = True
    try:
        assert not app.plan_recovery.attempt() and not app.ev_valid
        assert app.plan_recovery.pending
        f.charger.refresh()
        app.observation = replace(app.observation, at=f.charger.at, ev_phase_known=True)
        assert app.plan_recovery.attempt() and app.ev_valid
        assert app.accepted == f.plan
    finally:
        await f.close()


async def test_travel_since_calculation_requires_new_reconciliation(tmp_path):
    f = RecoveryFixture(tmp_path, travel=True)
    app = f.restart()
    try:
        await app.hardware.set_requested(True)
        assert not app.ev_valid and "Travel" in app.plan_recovery.reason
    finally:
        await f.close()


async def test_structural_invalidation_cannot_be_overridden_by_later_startup_readiness(tmp_path):
    f = RecoveryFixture(tmp_path)
    app = f.restart()
    try:
        app.changed("goal_changed", ev=True)
        await app.hardware.set_requested(True)
        assert not app.plan_recovery.attempt() and not app.ev_valid
    finally:
        await f.close()
