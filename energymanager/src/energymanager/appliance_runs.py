"""Persistent Ready handoff, conflict decisions and feedback-reconciled Bosch execution."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from .domain import instant

if TYPE_CHECKING:
    from .service import Application


class ApplianceRuns:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.key = "appliance_run_"+("demo" if app.demo else "configured")
        self.saved: dict[str,Any] = app.store.get(self.key,{"revision":1,"run":None,"idle":None})
        self.reconciled = False
        self.last_eligibility: tuple[Any,...] | None = None
        self.last_notice: datetime | None = None
        self.error: str | None = None
        self.manual: dict[str,Any] | None = None

    @property
    def run(self) -> dict[str,Any] | None:
        return self.saved["run"]

    def persist(self) -> None:
        self.app.store.put(self.key,self.saved)

    def changed(self, reason: str) -> None:
        self.persist()
        self.app.changed(reason)
        self.app.request_plan(reason)

    def revision(self, body: dict[str,Any]) -> None:
        if type(body.get("revision")) is not int or body["revision"] != self.saved["revision"]:
            raise ValueError("Dishwasher request changed; refresh before editing")

    def view(self) -> dict[str,Any]:
        row = deepcopy(self.run)
        if row:
            row.pop("profile",None)
        return {"revision":self.saved["revision"],"run":row,"error":self.error,
                "reconciled":self.reconciled,"idle":self.saved["idle"],
                "notification":"phone configured" if self.app.notifications.target else "phone not configured"}

    async def preview(self, body: dict[str,Any]) -> dict[str,Any]:
        if self.app.demo:
            raise ValueError("Managed appliance runs require configured mode")
        program = body.get("program")
        if not isinstance(program,str):
            raise ValueError("Choose a program")
        if not isinstance(body.get("deadline"), str):
            raise ValueError("Choose a latest finish with a timezone offset")
        deadline = instant(body["deadline"])
        zone = ZoneInfo(self.app.policy.timezone)
        today = self.app.now().astimezone(zone).date()
        if not today <= deadline.astimezone(zone).date() <= today+timedelta(days=7):
            raise ValueError("Choose a local date from today through seven days ahead")
        profile = await self.app.appliance_profiles.profile_detail("dishwasher",program)
        duration = profile["summary"]["mean_duration_seconds"]
        earliest = self.app.now()+timedelta(seconds=duration)
        return {"program":program,"deadline":deadline.isoformat(),"earliest_finish":earliest.isoformat(),
                "asap":earliest>deadline,"mean_duration_seconds":duration,"energy_kwh":profile["summary"]["energy_kwh"],
                "profile":profile,"warning":"This deadline cannot be met. Ready with this deadline authorizes starting as soon as possible." if earliest>deadline else None}

    async def action(self, action: str, body: dict[str,Any]) -> dict[str,Any]:
        if action == "preview":
            result = await self.preview(body)
            result.pop("profile")
            return result
        self.revision(body)
        if action == "ready":
            if self.run and self.run["phase"] in ("queued","starting","running","attention"):
                raise ValueError("Cancel or finish the current request first")
            preview = await self.preview(body)
            if preview["asap"] and body.get("accept_asap") is not True:
                raise ValueError("Review the earliest-finish warning before confirming Ready for ASAP")
            bosch = self.app.appliance_profiles.bosch
            await bosch.read()
            if bosch.value("operation") not in ("ready","inactive","finished") or bosch.value("power") != "on":
                raise ValueError("Power on the idle dishwasher before confirming Ready")
            if bosch.value("selected_program") != body["program"]:
                raise ValueError("Select the program on the dishwasher and wait for feedback first")
            self.native_delay()
            self.revision(body)  # Reads/profile derivation may yield to another request.
            self.saved["revision"] += 1
            self.saved["run"] = {"id":uuid4().hex,"revision":self.saved["revision"],"program":body["program"],
                "ready_at":self.app.now().isoformat(),"deadline":preview["deadline"],"original_deadline":preview["deadline"],
                "asap":preview["asap"],"profile":preview["profile"],"phase":"queued","approved_peak_kw":None,
                "planned_start":None,"conflict":None,"blocked":None,"command_at":None,"started_at":None}
            self.changed("dishwasher_ready")
        elif action == "cancel":
            if not self.run:
                raise ValueError("No queued request")
            if self.run["phase"] in ("running","starting"):
                raise ValueError("A running cycle is uninterrupted; cancellation cannot stop it")
            self.saved["revision"] += 1
            self.run.update(phase="cancelled",planned_start=None,estimated_finish=None,plan_id=None,conflict=None)
            self.changed("dishwasher_cancelled")
        elif action in ("edit","choose"):
            run = self.run
            if not run or run["phase"] != "queued":
                raise ValueError("Only a queued run can be changed")
            if action == "edit":
                preview = await self.preview({"program":run["program"],"deadline":body["deadline"]})
                if preview["asap"] and body.get("accept_asap") is not True:
                    raise ValueError("Review the impossible-deadline warning and confirm ASAP")
                self.revision(body)
                if self.run is not run or run["phase"] != "queued":
                    raise ValueError("Dishwasher request changed; refresh before editing")
                run.update(deadline=preview["deadline"],asap=preview["asap"],approved_peak_kw=None)
            else:
                conflict = run.get("conflict")
                choice = body.get("choice")
                if (not conflict or body.get("proposal_id") != conflict.get("proposal_id")
                        or choice not in ("later","on_time") or not conflict.get(choice)):
                    raise ValueError("That alternative is no longer available")
                proposal = conflict[choice]
                if choice == "later":
                    run.update(deadline=proposal["estimated_finish"],asap=False,approved_peak_kw=None)
                else:
                    if body.get("approved") is not True:
                        raise ValueError("Explicit approval of the shown peak is required")
                    run["approved_peak_kw"] = proposal["peak_kw"]
            self.saved["revision"] += 1
            run.update(revision=self.saved["revision"],planned_start=None,estimated_finish=None,plan_id=None,conflict=None,blocked=None)
            self.changed("dishwasher_request_changed")
        else:
            raise ValueError("Unknown managed run action")
        return self.view()

    def native_delay(self) -> None:
        bosch = self.app.appliance_profiles.bosch
        try:
            zero = float(bosch.value("delay") or "nan") == 0
        except ValueError:
            zero = False
        if not zero or bosch.readings.get("delay",{}).get("unit") not in ("s","seconds"):
            raise ValueError("Clear the native start delay before handing this run to EnergyManager")

    def context(self) -> dict[str,Any] | None:
        bosch = self.app.appliance_profiles.bosch
        if not bosch.enabled or self.app.demo:
            return None
        if not self.reconciled or bosch.at is None or (self.app.now()-instant(bosch.at)).total_seconds()>15:
            raise ValueError("Dishwasher feedback has not been reconciled")
        idle = self.saved["idle"]
        entity = bosch.profiles.settings["machines"]["dishwasher"]["entity_id"]
        if not idle or idle["entity"] != entity:
            raise ValueError("No measured dishwasher idle/standby evidence is available")
        run = self.run if self.run and self.run["phase"] in ("queued","starting","running","attention") else self.manual
        if not run:
            if bosch.value("operation") not in ("ready","inactive","finished"):
                raise ValueError("Dishwasher operation/remaining demand is unknown")
            return {"id":None,"idle_w":idle["power_w"],"points":[]}
        if (run["phase"] == "attention" or run["phase"] == "queued" and not run.get("profile")) and bosch.value("operation") in ("ready","inactive","finished"):
            return {"id":None,"idle_w":idle["power_w"],"points":[]}
        if run["phase"] == "starting":
            raise ValueError("Waiting for actual dishwasher execution feedback; demand timing remains unconfirmed")
        if run["phase"] == "attention":
            raise ValueError(run.get("blocked") or "Dishwasher execution requires reconciliation")
        profile = run.get("profile")
        if not profile:
            raise ValueError("Running dishwasher has no reviewed remaining-power estimate")
        if run.get("timing_known") is False:
            raise ValueError("Dishwasher was already running when observation began; elapsed phase is unknown")
        summary = profile["summary"]
        if run.get("started_at") and (self.app.now()-instant(run["started_at"])).total_seconds()>=summary["duration_seconds"]:
            raise ValueError("Dishwasher is still running beyond its measured profile; remaining demand is unknown")
        return {"id":run["id"],"revision":run["revision"],"program":run["program"],"ready_at":run["ready_at"],
                "deadline":run["deadline"],"asap":run["asap"],"approved_peak_kw":run.get("approved_peak_kw"),
                "started_at":run.get("started_at"),"idle_w":idle["power_w"],"points":deepcopy(profile["points"]),
                "mean_duration_seconds":summary["mean_duration_seconds"],"curve_seconds":summary["duration_seconds"],
                "profile_revision":profile["revision"],"recording_ids":profile["recording_ids"],
                "profile_energy_kwh":summary["energy_kwh"]}

    async def reconcile(self) -> None:
        bosch = self.app.appliance_profiles.bosch
        operation,program = bosch.value("operation"),bosch.value("active_program")
        now = self.app.now()
        self.reconciled = True
        meter = bosch.readings.get("meter",{}).get("power_w")
        if operation in ("ready","inactive","finished") and meter is not None:
            self.saved["idle"] = {"power_w":meter,"at":now.isoformat(),
                                   "entity":bosch.profiles.settings["machines"]["dishwasher"]["entity_id"]}
        run = self.run
        if operation == "run":
            if not program:
                self.error = "Running program is unavailable; demand cannot be assigned"
                return
            active_recording = bosch.profiles._rows("status='recording'",limit=10)
            recording = next((r for r in active_recording if r["machine"]=="dishwasher" and r["program"]==program),None)
            started = recording["started_at"] if recording else now.isoformat()
            timing_known = bool(recording and recording.get("start_observed", not recording["interrupted"]))
            if run and run["phase"] in ("queued","starting","running","attention"):
                if run["phase"] != "running" or run["program"] != program:
                    if run["program"] != program:
                        run["approved_peak_kw"] = None
                        run["profile"] = await self.profile(program)
                    run.update(program=program,phase="running",started_at=started,timing_known=timing_known,blocked=None,conflict=None)
                    self.changed("dishwasher_execution_observed")
            elif not self.manual or self.manual["program"] != program:
                self.manual = {"id":"observed-"+(recording["id"] if recording else uuid4().hex),"revision":1,
                    "program":program,"profile":await self.profile(program),"phase":"running","ready_at":started,
                    "started_at":started,"timing_known":timing_known,"deadline":(now+timedelta(days=1)).isoformat(),"asap":False}
                self.app.changed("manual_dishwasher_observed")
                self.app.request_plan("manual_dishwasher_observed")
        else:
            if self.manual:
                self.manual = None
                self.app.changed("manual_dishwasher_changed")
                self.app.request_plan("manual_dishwasher_changed")
            if run and run["phase"] == "running":
                run.update(phase="finished" if operation=="finished" else "attention",
                           blocked=None if operation=="finished" else "Cycle interrupted; EnergyManager will not resume it automatically")
                self.changed("dishwasher_execution_ended")
            elif run and run["phase"] == "starting":
                if operation == "finished":
                    run.update(phase="finished",blocked=None)
                    self.changed("dishwasher_completion_observed")
                elif run["command_at"] and (now-instant(run["command_at"])).total_seconds()>=30:
                    run.update(phase="attention",blocked="Start outcome unconfirmed. Check the appliance; cancel and create a new request to retry.")
                    self.persist()
            elif run and run["phase"] == "queued":
                selected = bosch.value("selected_program")
                if selected and selected != run["program"]:
                    run.update(program=selected,profile=await self.profile(selected),approved_peak_kw=None,planned_start=None,estimated_finish=None,plan_id=None,conflict=None)
                    self.saved["revision"] += 1
                    run["revision"] = self.saved["revision"]
                    self.changed("dishwasher_program_changed")
                members = self.app.appliance_profiles.members("dishwasher/"+run["program"])
                previous_members = run["profile"]["recording_ids"] if run.get("profile") else []
                if members != previous_members:
                    run["profile"] = await self.profile(run["program"])
                    self.saved["revision"] += 1
                    run.update(revision=self.saved["revision"],approved_peak_kw=None,planned_start=None,estimated_finish=None,plan_id=None,conflict=None)
                    self.changed("dishwasher_profile_changed")
                eligible = (operation,bosch.value("door"),bosch.value("remote_control"),bosch.value("remote_start"),bool(run.get("profile")))
                if self.last_eligibility is not None and eligible != self.last_eligibility:
                    self.app.changed("dishwasher_eligibility_changed")
                    self.app.request_plan("dishwasher_eligibility_changed")
                self.last_eligibility = eligible
                run["blocked"] = self.start_reason()
                await self.execute()
                if run.get("conflict") and (self.last_notice is None or (now-self.last_notice).total_seconds()>=60):
                    self.last_notice = now
                    await self.app.notifications.inform("dishwasher-choice-"+run["id"],{
                        "message":"Dishwasher needs a deadline/peak choice. Open Appliances to review the alternatives.",
                        "run_id":run["id"],"revision":run["revision"],"deadline":run["deadline"]})
        self.error = None
        self.persist()

    async def profile(self, program: str) -> dict[str,Any] | None:
        if not self.app.appliance_profiles.members("dishwasher/"+program):
            return None
        return await self.app.appliance_profiles.profile_detail("dishwasher",program)

    def start_reason(self) -> str | None:
        bosch = self.app.appliance_profiles.bosch
        if bosch.value("operation") not in ("ready","inactive","finished") or bosch.value("power") != "on":
            return "Appliance is not confirmed powered on and idle"
        if bosch.value("door") not in ("off","closed"):
            return "Door open or unavailable; readiness is retained"
        if bosch.value("remote_start") != "on" or bosch.value("remote_control") != "on":
            return "Waiting for remote permissions"
        if not self.run or not self.run.get("profile"):
            return "No usable reviewed profile; use Start now and record"
        if bosch.value("selected_program") != self.run["program"]:
            return "Waiting for confirmed selected program"
        try:
            self.native_delay()
        except ValueError as exc:
            return str(exc)
        if self.run.get("conflict"):
            return "Waiting for your deadline/peak choice"
        return bosch.authority_reason()

    def accepted(self, plan: dict[str,Any]) -> None:
        run = self.run
        if not run or run["phase"] != "queued":
            return
        evidence = plan.get("appliance") or {}
        conflict = plan.get("appliance_conflict")
        if conflict and conflict["id"]==run["id"] and conflict["revision"]==run["revision"]:
            run.update(conflict=conflict,planned_start=None)
        elif evidence.get("id")==run["id"] and evidence.get("revision")==run["revision"]:
            run.update(conflict=None,planned_start=evidence.get("planned_start"),estimated_finish=evidence.get("estimated_finish"),plan_id=plan["id"])
        self.persist()

    async def execute(self) -> None:
        run = self.run
        if not run or run["phase"] != "queued" or not run.get("planned_start") or self.start_reason():
            return
        plan = self.app.accepted
        if (not plan or plan["id"] != run.get("plan_id") or plan["revision"] != self.app.revision
                or not plan.get("admission",{}).get("passed")):
            return
        now = self.app.now()
        observation = self.app.observation
        if (observation.quality != "measured" or not 0 <= (now-observation.at).total_seconds() <= self.app.policy.measurement_max_age_seconds
                or (now-instant(plan["forecast_at"])).total_seconds()>self.app.policy.forecast_max_age_seconds
                or self.app.house_mismatch_since is not None):
            run["blocked"] = "Waiting for fresh validated inputs/forecast"
            return
        if now < instant(run["planned_start"]):
            return
        if (now-instant(run["planned_start"])).total_seconds()>15:
            run.update(planned_start=None,estimated_finish=None,plan_id=None)
            self.app.request_plan("dishwasher_start_reconcile")
            return
        self.native_delay()
        bosch = self.app.appliance_profiles.bosch
        previous_command = bosch.last_command
        run.update(phase="starting",command_at=now.isoformat())
        self.persist()  # An ambiguous write is never automatically repeated, including after restart.
        try:
            await self.app.appliance_profiles.bosch.command({"command":"start","program":run["program"]},
                authorize=lambda: self.run is run and run["phase"]=="starting" and self.app.revision==plan["revision"])
        except ValueError as exc:
            if bosch.last_command is previous_command:
                run.update(phase="queued",command_at=None,planned_start=None,estimated_finish=None,plan_id=None,blocked=str(exc))
                self.app.request_plan("dishwasher_start_guard_changed")
            else:
                run.update(phase="attention",blocked=str(exc))
            self.persist()

    def peak_limit(self) -> float | None:
        run = self.run
        bosch = self.app.appliance_profiles.bosch
        if (not run or run["phase"] != "running" or bosch.at is None
                or (self.app.now()-instant(bosch.at)).total_seconds()>15
                or bosch.value("operation") != "run" or bosch.value("active_program") != run["program"]):
            return None
        return max(self.app.policy.automatic_peak_kw,run.get("approved_peak_kw") or 0)
