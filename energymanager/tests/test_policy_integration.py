from dataclasses import replace
from datetime import timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from energymanager.adapters import HomeAssistantAdapter
from energymanager.control import Command, FastControl, GuardedActuator
from energymanager.domain import Goal, json_data
from energymanager.forecasts import demo_snapshot
from energymanager.planner import Planner
from energymanager.service import Application
from energymanager.store import Store
from energymanager.validation import validate
from energymanager.web import create_web
from test_first_slice import tiny, solve


def test_later_pv_cannot_erase_earlier_required_grid():
    s = tiny(hours=2, ev=24, ess=2.8, house=0)
    deadline = s.intervals[11].end
    s = replace(
        s,
        goals=(Goal("early", "Early deadline", deadline, 42),),
        intervals=tuple(replace(i, pv_ac_kw=4) if t >= 12 else i for t, i in enumerate(s.intervals)),
    )
    f = solve(s, optional=True)
    assert sum(f["grid_ev"][:12]) > 0
    assert sum(f["pv_ev"][12:]) > 0
    assert validate(s, f) == []


def test_no_forced_discharge_when_initial_soc_above_normal_ceiling():
    s = tiny(ev=55, pv=4)
    f = solve(s, optional=True, ceilings=[48] * len(s.intervals), tight_ceilings=True)
    assert f["ev_energy"][-1] == pytest.approx(55)
    assert sum(f["grid_ev"]) == pytest.approx(0)


def test_permission_diagnostic_proposes_only_a_feasible_useful_extension():
    s = tiny(hours=1, ev=24, house=0.4)
    s = replace(
        s,
        policy=replace(s.policy, planning_budget_seconds=15),
        goals=(Goal("urgent", "Urgent departure", s.intervals[-1].end, 47),),
    )
    result = Planner().plan(s)
    assert result["valid"], result
    assert result["goals"][0]["shortfall_kwh"] > 0.1
    assert result["permission_proposals"], result["stages"]
    assert 4 < result["permission_proposals"][0]["proposed_peak_kw"] <= 17
    impossible = replace(s, goals=(replace(s.goals[0], target_soc_percent=100),))
    result = Planner().plan(impossible)
    assert result["valid"]
    assert result["permission_proposals"] == []
    assert min(result["flows"]["ev_energy"]) >= 0


def test_optional_controller_cannot_draw_grid_during_source_loss():
    s = tiny(hours=1, ev=24, pv=4)
    f = solve(s, optional=True)
    position = next(i for i, v in enumerate(f["pv_ev"]) if v > 1)
    plan = {
        "id": "accepted",
        "flows": f,
        "intervals": json_data(s.intervals),
        "goals": [],
        "reasons": [{"kind": "joint_capture"}],
    }
    at = s.intervals[position].start
    o = replace(
        s.observation,
        at=at,
        ev_kwh=f["ev_energy"][position],
        pv_ac_kw=0,
        pv_dc_kw=0,
        ess_kwh=s.capabilities.ess_min_kwh,
        ess_grid_kwh=0,
        house_kw=0.5,
    )
    command = FastControl(s.capabilities, s.policy).tick(o, at, plan, 1)
    assert command.ev_kw == 0


async def test_ha_measurements_and_actuator_calls_against_local_http_server():
    s = demo_snapshot(hours=1, goals=())
    calls = []
    vals = {
        "ev_soc": (42, "%"),
        "ess_soc": (50, "%"),
        "connected": ("on", None),
        "house_kw": (420, "W"),
        "pv_ac_kw": (2000, "W"),
        "pv_dc_kw": (1.5, "kW"),
        "ev_kw": (0, "kW"),
        "ess_kw": (0, "kW"),
        "quarter_import_kwh": (0.1, "kWh"),
        "monthly_peak_kw": (2.5, "kW"),
        "ev_phases": (1, None),
    }

    async def state(request):
        value, unit = vals[request.match_info["key"]]
        return web.json_response(
            {
                "state": str(value),
                "attributes": {"unit_of_measurement": unit},
                "last_updated": s.observation.at.isoformat(),
            }
        )

    async def service(request):
        calls.append(await request.json())
        return web.json_response([])

    fake = web.Application()
    fake.add_routes([web.get("/states/{key}", state), web.post("/services/{domain}/{service}", service)])
    async with TestServer(fake) as server:
        async with HomeAssistantAdapter(
            str(server.make_url("")).rstrip("/"), {key: key for key in vals}
        ) as adapter:
            observation = await adapter.observe(s.capabilities, at=s.observation.at)
            assert observation.house_kw == pytest.approx(0.42)
            actuator = GuardedActuator(
                adapter,
                {
                    "force": "fake.force",
                    "phase": "fake.phase",
                    "current": "fake.current",
                    "ess_setpoint": "fake.ess",
                },
                s.capabilities,
                enabled=True,
            )
            command = Command(1, "fake-plan", observation.at, 1.38, -0.5, 1, 6, 4, "local verification")
            await actuator.apply(command, 1, observation)
            assert calls == [
                {"entity_id": "fake.ess", "value": 500},
                {"entity_id": "fake.current", "value": 6},
                {"entity_id": "fake.force", "option": "2"},
            ]
            vals["ev_soc"] = ("unavailable", "%")
            unknown = await adapter.observe(s.capabilities, at=s.observation.at)
            assert not unknown.ev_state_known
            assert (
                unknown.ev_kwh == observation.ev_kwh
            )  # explicitly labelled last-known, never current evidence
            assert unknown.ess_grid_kwh == pytest.approx(unknown.ess_kwh - s.capabilities.ess_min_kwh)
            from energymanager.control import FastControl

            command = FastControl(s.capabilities, s.policy).tick(unknown, unknown.at, None, 2)
            assert command.ev_kw == 0
            assert command.ess_kw < 0  # fresh shared powers still permit useful solar balancing


async def test_goal_edit_approval_delete_round_trip_api_and_same_origin(tmp_path):
    s = tiny(hours=2)
    s = replace(s, policy=replace(s.policy, planning_budget_seconds=2))
    application = Application(Store(tmp_path / "api.sqlite"), snapshot=s, policy=s.policy, demo=False)
    async with TestClient(TestServer(create_web(application))) as client:
        headers = {"X-EnergyManager": "1"}
        response = await client.post(
            "/api/goals",
            json={
                "title": "API goal",
                "deadline": (s.observation.at + timedelta(hours=1)).isoformat(),
                "target_soc_percent": 60,
            },
            headers=headers,
        )
        # Frozen fixture clock uses real time when demo=False; choose a future goal for API validation.
        if response.status == 400:
            from datetime import UTC, datetime

            response = await client.post(
                "/api/goals",
                json={
                    "title": "API goal",
                    "deadline": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    "target_soc_percent": 60,
                },
                headers=headers,
            )
        assert response.status == 201, await response.text()
        goal = await response.json()
        response = await client.post(
            f"/api/goals/{goal['id']}/approval",
            json={"state": "granted", "peak_kw": 6, "revision": goal["revision"]},
            headers=headers,
        )
        assert response.status == 200
        response = await client.get("/api/state")
        assert (await response.json())["goals"][0]["approval_state"] == "granted"
        response = await client.post(
            "/api/replan", json={}, headers={**headers, "Origin": "http://evil.invalid"}
        )
        assert response.status == 403
        response = await client.delete(f"/api/goals/{goal['id']}", json={}, headers=headers)
        assert response.status == 200
        assert application.goals == ()
