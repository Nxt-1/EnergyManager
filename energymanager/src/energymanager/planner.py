"""One budgeted planning process with finite comparisons and independently audited output."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from time import monotonic
from typing import Any
from uuid import uuid4
from collections.abc import Callable
from copy import deepcopy

from .domain import PeakPermission, Snapshot, json_data, instant
from .charging_timing import ChargingTiming
from .charging_continuity import ChargingContinuity, ChargingWindow
from .incumbent import seed
from .solar_capture import SolarCapture
from .optimization import JointModel
from .validation import TOL, accounting, rolling_comparison_errors, validate
from .reservations import reservations
from .session_attribution import attribute_ev_sessions


class Planner:
    def __init__(self, progress: Callable[[str], None] | None = None) -> None:
        self.started = 0.0
        self.deadline = 0.0
        self.stages: list[dict[str, Any]] = []
        self.progress = progress
        self.validation_seconds = 0.0
        self.solar_reserve = 0.0
        self.continuity_reserve = 0.0
        self.solver_overrun = 0.0
        self.reference_flows: dict[str, list[float]] | None = None

    def remaining(self) -> float:
        reserved = self.solar_reserve + self.continuity_reserve + (self.validation_seconds + self.solver_overrun) * 1.25
        return max(0.0, self.deadline - monotonic() - 0.25 - reserved)

    def validate_candidate(self, snapshot: Snapshot, flows: dict[str, list[float]],
                           service: dict[str, float] | None = None) -> list[str]:
        """Reserve measured audit time so a late solver stage cannot consume the wall budget."""
        started = monotonic()
        errors = validate(snapshot, flows, service)
        self.validation_seconds = max(self.validation_seconds, monotonic() - started)
        return errors

    def starting_point(self, model: JointModel) -> list[float] | None:
        s = model.snapshot
        baseline = max(s.policy.billing_floor_kw, s.observation.monthly_peak_kw)
        limits = [baseline, (baseline + max(baseline, s.policy.automatic_peak_kw)) / 2, None]
        best = None
        for limit in limits:
            candidate = seed(model, limit)
            if candidate is not None and (
                best is None or model.value(model.economic, candidate) < model.value(model.economic, best)
            ):
                best = candidate
            if self.remaining() < 2:
                break
        if best is not None and 1 in s.capabilities.phases and self.remaining() > 2:
            steady = seed(model, baseline, preferred_phase=1)
            if (steady is not None
                    and model.value(model.economic, steady) <= model.value(model.economic, best) + 1e-6
                    and model.value(model.cash, steady) <= model.value(model.cash, best) + 1e-6
                    and model.value(model.continuity_objective(), steady)
                    < model.value(model.continuity_objective(), best)):
                best = steady
        return best

    def run_model(
        self, name: str, model: JointModel, allowance: float, warm: list[float] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        economic_search = "objective" not in kwargs
        if self.progress:
            self.progress(name)
        started = monotonic()
        allowance = max(0., min(allowance, self.remaining()))
        solver_allowance = allowance * .8 if economic_search else allowance
        result: dict[str, Any]
        if solver_allowance < .1:
            # Even a nominal one-millisecond run can pay seconds of presolve.
            # Keep any checked warm fallback, including all requested bounds.
            for terms, upper in kwargs.get("bounds", []):
                model.linear.row(list(terms.items()), upper=upper)
            result = {"feasible": False, "status": "Time limit reached", "seconds": 0.,
                      "columns": len(model.linear.lower), "rows": len(model.linear.row_lower),
                      "integers": len(model.linear.integer), "objective": None, "bound": None,
                      "gap": None, "skipped_budget": True}
        else:
            result = model.run(solver_allowance, warm=warm, **kwargs)
            self.solver_overrun = max(self.solver_overrun, monotonic() - started - solver_allowance)
        self.stages.append(
            {"name": name, **{k: v for k, v in result.items() if k not in ("flows", "values")}}
        )
        # A bounded solve may fail to return its valid warm start, or return a worse one.
        # Keep the raw solver evidence in stages and retain only a fully checked candidate.
        if warm is not None:
            values = model.canonical_values(warm)
            objective = kwargs.get("objective", model.economic)
            timed_out = not result["feasible"] and result["status"] == "Time limit reached"
            better_start = (result["feasible"] and model.value(objective, values)
                            < model.value(objective, result["values"]) - 1e-6)
            if model.linear.accepts(values) and (timed_out or better_start):
                self.stages[-1]["retained_starting_candidate"] = True
                result = {**result, "feasible": True, "values": values, "retained_starting_candidate": True,
                          "canonical_objective": model.value(objective, values),
                          "flows": {name: [values[index] for index in indexes]
                                    for name, indexes in model.linear.variables.items()}}
        if economic_search and result["feasible"]:
            remaining = min(self.remaining(), allowance - (monotonic() - started))
            result = self.prefer_continuity(name, model, result, remaining)
        return result

    def prefer_continuity(self, name: str, model: JointModel, result: dict[str, Any],
                          allowance: float, *, single_only: bool = False) -> dict[str, Any]:
        """Choose charger continuity within the same carried economic/cash allowance."""
        actual = (model.value(model.economic, result["values"]), model.value(model.cash, result["values"]))
        carried = (result.get("economic_baseline", actual[0]), result.get("cash_baseline", actual[1]))
        economic, cash = min(actual, carried)
        result["economic_baseline"], result["cash_baseline"] = economic, cash
        if allowance < 0.3:
            return result
        if single_only:
            return self.review_continuity(name, model, result, allowance)
        started = monotonic()
        guided = deepcopy(model)
        guided.add_continuity_limits()
        # ESS and source allocations remain decisions in the original physical model.
        # A fragmented ESS incumbent must not dictate fragmented EV charging.
        for variable, indexes in guided.linear.variables.items():
            if variable.startswith("margin_shortfall_"):
                guided.linear.upper[indexes[0]] = result["values"][indexes[0]] + 1e-6
        ev = guided.linear.variables["ev_energy"]
        guided.linear.lower[ev[-1]] = result["flows"]["ev_energy"][-1] - 1e-6
        tolerance = model.snapshot.policy.polish_tolerance_eur
        bounds = [(guided.economic, economic + tolerance), (guided.cash, cash + tolerance)]
        result = self.review_continuity(name, model, result, allowance * .35)
        continuity = guided.continuity_objective()
        guided.linear.row(list(continuity.items()), upper=model.value(
            model.continuity_objective(), result["values"]) + 1e-6)
        refined = self.run_model(name + "_joint_continuity", guided, allowance - (monotonic() - started),
                                 guided.warm_from(result["flows"]), objective=guided.continuity_objective(),
                                 bounds=bounds)
        if (refined["feasible"] and not self.continuity_errors(model, refined["flows"])
                and guided.value(guided.continuity_objective(), refined["values"])
                < model.value(model.continuity_objective(), result["values"]) - 1e-6):
            refined["values"] = model.warm_from(refined["flows"])
            refined["status"] = result["status"]  # Refinement optimality is not economic optimality.
            refined["economic_baseline"], refined["cash_baseline"] = economic, cash
            return refined
        result["economic_baseline"], result["cash_baseline"] = economic, cash
        return result

    def continuity_errors(self, model: JointModel, flows: dict[str, list[float]]) -> list[str]:
        errors = self.validate_candidate(model.snapshot, flows, model.service)
        if model.optional and self.reference_flows is not None:
            errors += rolling_comparison_errors(model.snapshot, self.reference_flows, flows)
        return errors

    def review_continuity(self, name: str, model: JointModel, result: dict[str, Any],
                          allowance: float) -> dict[str, Any]:
        """Visit every charging window, retaining valid plans when bounded work is unfinished."""
        deadline = monotonic() + max(0., min(allowance, self.remaining()))
        review = ChargingContinuity(model, result["flows"])
        actual = (model.value(model.economic, result["values"]), model.value(model.cash, result["values"]))
        economic, cash = min(actual, (result.get("economic_baseline", actual[0]),
                                     result.get("cash_baseline", actual[1])))
        tolerance = model.snapshot.policy.polish_tolerance_eur
        coverage: list[dict[str, Any]] = []
        revision = 0
        # A second sweep reuses time saved by easy windows for unfinished work.
        # The partition and all accepted window bounds remain unchanged.
        for sweep in range(2):
            current = ChargingContinuity(model, result["flows"], review.windows)
            pending = sum(w.available and (current.sessions(w) > 1 or len(current.phases(w)) > 1)
                          for w in review.windows)
            for number, window in enumerate(review.windows):
                current = ChargingContinuity(model, result["flows"], review.windows)
                before = current.sessions(window)
                if sweep == 0:
                    record: dict[str, Any] = {"first": window.first, "last": window.last, "available": window.available,
                        "start": model.snapshot.intervals[window.first].start.isoformat(),
                        "end": model.snapshot.intervals[window.last - 1].end.isoformat(),
                        "sessions_before": before, "sessions_after": before}
                    coverage.append(record)
                else:
                    record = coverage[number]
                if not window.available:
                    if sweep == 0:
                        record["outcome"] = "unavailable"
                    continue
                if not before:
                    if sweep == 0:
                        record["outcome"] = "no_charging"
                    continue
                if before == 1 and len(current.phases(window)) == 1:
                    if sweep == 0:
                        record["outcome"] = "already_continuous"
                    continue
                remaining = min(deadline - monotonic(), self.remaining())
                window_deadline = monotonic() + remaining / max(1, pending)
                pending -= 1
                if sweep == 0:
                    record["outcome"] = "not_checked_budget"
                if remaining < .3:
                    continue
                phase = min(model.snapshot.capabilities.phases)
                if model.snapshot.hold_ev_kw > TOL and window.first == 0:
                    phase = model.snapshot.hold_phases
                record.setdefault("attempts", [])
                # A single session can be impossible (for example, a partial departure
                # interval fixes an energy residue). Still minimize the remaining gaps.
                infeasible_profiles: set[str] = set()
                relaxed_starts: dict[str, dict[str, list[float]]] = {}
                for kind in ("packed_relaxed", "packed", "consolidated_relaxed", "consolidated", "single", "flexible"):
                    if kind in infeasible_profiles:
                        continue
                    if min(window_deadline - monotonic(), self.remaining()) < .3:
                        break
                    current = ChargingContinuity(model, result["flows"], review.windows)
                    chosen_phase: int | None = phase if kind == "single" else None
                    profile_kind = kind.removesuffix("_relaxed")
                    relaxed = kind.endswith("_relaxed")
                    if profile_kind in ("packed", "consolidated"):
                        packed = current.packed_candidate(window, longest_run=profile_kind == "consolidated")
                        if packed is None:
                            continue
                        local, chosen_phase = packed
                    else:
                        local = current.candidate(window, chosen_phase)
                    integer_model = local
                    if relaxed:
                        # Fixed EV currents need no integer search. Try unrestricted
                        # source dispatch first, then certify it against the integer model.
                        local = deepcopy(local)
                        local.linear.integer = []
                    remaining = min(window_deadline - monotonic(), self.remaining())
                    seconds = (min(2., remaining * .8) if relaxed else
                               min(6., remaining * .8) if profile_kind in ("packed", "consolidated") else
                               remaining * .65 if kind == "single" else remaining)
                    if seconds < .1:
                        break
                    objective = local.economic if profile_kind in ("packed", "consolidated") else local.continuity_objective()
                    warm_flows = relaxed_starts.get(kind, result["flows"])
                    trial = self.run_model(f"{name}_window:{window.first}:{kind}", local, seconds,
                        local.warm_from(warm_flows), objective=objective,
                        bounds=[(local.economic, economic + tolerance), (local.cash, cash + tolerance)])
                    attempt = {"kind": kind, "phase": chosen_phase, "status": trial["status"],
                               "seconds": trial["seconds"], "basis_revision": revision}
                    if kind in relaxed_starts:
                        attempt["warm_from_relaxation"] = True
                    record["attempts"].append(attempt)
                    if not trial["feasible"]:
                        if relaxed and trial["status"] == "Infeasible":
                            # The identical integer profile is a subset of this LP.
                            # Try a different profile rather than proving it again.
                            infeasible_profiles.add(profile_kind)
                        continue
                    flows = (current.integer_dispatch(integer_model, trial["flows"])
                             if relaxed else trial["flows"])
                    values = model.warm_from(flows)
                    errors = []
                    if not integer_model.linear.accepts(integer_model.warm_from(flows)):
                        errors.append("integer_dispatch")
                    if not local.linear.accepts(local.warm_from(flows)):
                        errors.append("candidate_model")
                    if not model.linear.accepts(values):
                        errors.append("original_model")
                    errors += self.continuity_errors(model, flows)
                    if errors:
                        attempt["rejected"] = True
                        attempt["rejection_errors"] = errors[:3]
                        if relaxed:
                            # An invalid point is only a solver hint. The following
                            # integer solve remains free to change every source decision.
                            relaxed_starts[profile_kind] = flows
                        continue
                    improved = ChargingContinuity(model, flows)
                    old_score = model.value(model.continuity_objective(), result["values"])
                    score = model.value(model.continuity_objective(), values)
                    if improved.sessions(window) > before:
                        attempt["rejected"] = True
                        attempt["rejection_errors"] = ["session_count"]
                        continue
                    attempt["valid"] = True
                    attempt["result_revision"] = revision
                    if score >= old_score - 1e-6:
                        continue
                    result = {**result, "flows": flows, "values": values}
                    revision += 1
                    attempt["result_revision"] = revision
                    record["sessions_after"] = improved.sessions(window)
                    record["improvement_retained"] = True
                    if improved.sessions(window) == 1 and len(improved.phases(window)) == 1:
                        break
        final = ChargingContinuity(model, result["flows"], review.windows)
        for window, record in zip(review.windows, coverage):
            final.summarize(window, record, revision)
        unresolved = sum(record["unresolved"] for record in coverage)
        result["economic_baseline"], result["cash_baseline"] = economic, cash
        result["continuity_review"] = {"intervals": len(model.snapshot.intervals), "windows": coverage,
                                     "coverage_complete": True, "unresolved_windows": unresolved,
                                     "complete": unresolved == 0}
        return result

    @staticmethod
    def prefer_result(current: dict[str, Any], current_model: JointModel,
                      trial: dict[str, Any], trial_model: JointModel) -> bool:
        """Do not discard a known continuous session for a sub-allowance cost improvement."""
        def evidence(result: dict[str, Any], model: JointModel) -> tuple[float, float, float]:
            values = model.warm_from(result["flows"])
            return (model.value(model.economic, values), model.value(model.cash, values),
                    model.value(model.continuity_objective(), values))

        old_cost, old_cash, old_score = evidence(current, current_model)
        cost, cash, score = evidence(trial, trial_model)
        references = [(current.get("economic_baseline", old_cost), current.get("cash_baseline", old_cash)),
                      (trial.get("economic_baseline", cost), trial.get("cash_baseline", cash))]
        reference, cash_reference = min(references)
        tolerance = current_model.snapshot.policy.polish_tolerance_eur
        old_allowed = old_cost <= reference + tolerance + 1e-6 and old_cash <= cash_reference + tolerance + 1e-6
        allowed = cost <= reference + tolerance + 1e-6 and cash <= cash_reference + tolerance + 1e-6
        preferred = allowed and (not old_allowed or score < old_score - 1e-6
                                or abs(score - old_score) <= 1e-6 and cost < old_cost - TOL)
        chosen = trial if preferred else current
        # Carry the same reference forward: comparing stages must not stack allowances.
        chosen["economic_baseline"], chosen["cash_baseline"] = reference, cash_reference
        return preferred

    def prefer_solar(self, model: JointModel, result: dict[str, Any], allowance: float) -> dict[str, Any]:
        """Retain checked solar alternatives before the full search and before certification."""
        if allowance < .3:
            return result
        deadline = monotonic() + min(allowance, self.remaining())
        allocation_deadline = deadline

        def consider(values: list[float]) -> None:
            nonlocal result
            if not model.linear.accepts(values):
                return
            flows = {name: [values[index] for index in indexes]
                     for name, indexes in model.linear.variables.items()}
            if self.continuity_errors(model, flows):
                return
            candidate = {"status": result["status"], "feasible": True, "values": values, "flows": flows}
            if self.prefer_result(result, model, candidate, model):
                result = candidate

        capture = SolarCapture(model, result["flows"])
        consider(capture.export_seed())
        windows = capture.windows()
        for number, (first, last) in enumerate(windows):
            remaining = min(allocation_deadline - monotonic(), self.remaining())
            if remaining < .3:
                break
            local = SolarCapture(model, result["flows"]).neighborhood(first, last)
            remaining = min(allocation_deadline - monotonic(), self.remaining())
            if remaining < .1:
                break
            # Do not split a tiny budget into searches shorter than presolve. The
            # immediate window gets first priority; farther windows use what remains.
            share = remaining * .65 if number == 0 else remaining / (len(windows) - number)
            trial = self.run_model(f"solar_capture:{first}", local, min(remaining, max(.75, share)),
                                   local.warm_from(result["flows"]), objective=local.economic)
            if trial["feasible"] and local.linear.accepts(local.warm_from(trial["flows"])):
                consider(model.warm_from(trial["flows"]))
        return result

    def prefer_dispatch(self, model: JointModel, result: dict[str, Any], allowance: float) -> dict[str, Any]:
        """Refine source/ESS economics for the selected EV schedule before smoothing."""
        if allowance < .3:
            return result
        started = monotonic()
        dispatch = deepcopy(model)
        for name in ("one", "three", "amps_one", "amps_three"):
            for index, value in zip(dispatch.linear.variables[name], result["flows"][name]):
                dispatch.linear.lower[index] = dispatch.linear.upper[index] = value
        trial = self.run_model("selected_ev_dispatch", dispatch, allowance - (monotonic() - started),
                               dispatch.warm_from(result["flows"]), objective=dispatch.economic)
        if not trial["feasible"]:
            return result
        values = model.warm_from(trial["flows"])
        if (not dispatch.linear.accepts(dispatch.warm_from(trial["flows"]))
                or not model.linear.accepts(values) or self.continuity_errors(model, trial["flows"])):
            return result
        candidate = {**trial, "values": values, "status": result["status"]}
        return candidate if self.prefer_result(result, model, candidate, model) else result

    def prefer_earlier(self, model: JointModel, result: dict[str, Any], allowance: float) -> dict[str, Any]:
        """Resolve equal-benefit required timings on this snapshot before grid certification."""
        if allowance < .3 or not any(value > TOL for value in result["flows"]["grid_ev"]):
            return result
        started = monotonic()
        timing = ChargingTiming(model, result["flows"])
        warm = timing.earlier_seed(min(2.0, max(0, allowance - (monotonic() - started)) * .4))
        trial = self.run_model("earlier_required_charging", timing.model,
                               allowance - (monotonic() - started), warm, objective=timing.objective)
        # The checked seed is a candidate even when the timed solver has no incumbent.
        candidates = [warm]
        if trial["feasible"]:
            candidates.append(trial["values"])
        original = timing.model.warm_from(result["flows"])
        best_score = timing.model.value(timing.objective, original)
        for values in sorted(candidates, key=lambda v: timing.model.value(timing.objective, v)):
            score = timing.model.value(timing.objective, values)
            if score >= best_score - 1e-6 or not timing.model.linear.accepts(values):
                continue
            flows = {name: [values[index] for index in indexes]
                     for name, indexes in timing.model.linear.variables.items()}
            original_values = model.warm_from(flows)
            if not model.linear.accepts(original_values) or self.continuity_errors(model, flows):
                continue
            return {**result, "flows": flows, "values": original_values}
        return result

    def plan(self, snapshot: Snapshot) -> dict[str, Any]:
        self.started = monotonic()
        self.deadline = self.started + snapshot.policy.planning_budget_seconds
        self.validation_seconds = 0.0
        self.solar_reserve = 0.0
        self.continuity_reserve = 0.0
        self.solver_overrun = 0.0
        self.reference_flows = None
        self.stages = []
        s = snapshot
        service: dict[str, float] = {}
        permission_proposals: list[dict[str, Any]] = []
        reasons: list[dict[str, Any]] = []
        required_support = False
        reference_model = JointModel(s)
        reference_seed = self.starting_point(reference_model)
        reference = self.run_model(
            "required_reference",
            reference_model,
            max(1, self.remaining() * 0.10),
            reference_seed,
        )
        if (not reference["feasible"] and reference["status"] == "Time limit reached"
                and self.remaining() > 2):
            # A stage allowance is not the whole planning budget. Find a usable
            # required schedule before spending time on optional refinements.
            reference = self.run_model("required_reference_recovery", reference_model, self.remaining() - 2,
                                       reference_seed)
        if not reference["feasible"] and reference["status"] == "Infeasible" and self.remaining() > 3:
            # A late EV window can need ESS household support to avoid a larger necessary peak.
            support_model = JointModel(s, grid_ess=True)
            support = self.run_model("required_ess_support", support_model, min(5, self.remaining() * 0.15))
            higher = replace(
                s,
                goals=tuple(
                    replace(
                        g,
                        approval_state="granted",
                        approval_revision=g.revision,
                        approved_peak_kw=s.capabilities.grid_connection_kw,
                    )
                    for g in s.goals
                ),
            )
            alternative_model = JointModel(higher)
            alternative = self.run_model(
                "required_support_counterfactual",
                alternative_model,
                min(5, self.remaining() * 0.15),
                self.starting_point(alternative_model),
            )
            if (
                support["feasible"]
                and alternative["feasible"]
                and not self.validate_candidate(s, support["flows"])
                and not self.validate_candidate(higher, alternative["flows"])
            ):
                supported, without = accounting(s, support["flows"]), accounting(higher, alternative["flows"])
                if (
                    supported["peak_kw"] < without["peak_kw"] - TOL
                    and supported["comparison_eur"] < without["comparison_eur"] - TOL
                ):
                    reference, reference_model = support, support_model
                    required_support = True
                    reasons.append(
                        {
                            "kind": "peak_precharge",
                            "counterfactual_peak_kw": without["peak_kw"],
                            "counterfactual_comparison_eur": without["comparison_eur"],
                            "text": "ESS household support restores the required EV goal while avoiding a larger necessary peak within 24 hours; losses and both inventories are included.",
                        }
                    )
        if not reference["feasible"]:
            if reference["status"] != "Infeasible":
                return self.failure(
                    snapshot, reference["status"],
                    "Required schedule search ended without a feasible candidate; previous instructions continue only while valid"
                )
            relaxed = JointModel(s, relaxed_service=True)
            physical = self.run_model(
                "travel_feasibility",
                relaxed,
                min(8.0, self.remaining() * 0.15),
                self.starting_point(relaxed),
                objective={},
            )
            if not physical["feasible"]:
                if physical["status"] != "Infeasible":
                    return self.failure(
                        snapshot,
                        physical["status"],
                        "Travel feasibility not established; timeout is not impossibility",
                    )
                trips = sorted(
                    (g for g in s.goals if g.kind == "trip"), key=lambda g: g.deadline, reverse=True
                )
                for trip in trips:
                    effective = tuple(
                        replace(i, withdrawal_kwh=0.0, available=False, ev_state_known=False)
                        if i.start >= trip.deadline
                        else i
                        for i in snapshot.intervals
                    )
                    trial = replace(snapshot, intervals=effective)
                    relaxed = JointModel(trial, relaxed_service=True)
                    physical = self.run_model(
                        f"conditional_travel:{trip.id}",
                        relaxed,
                        min(8.0, self.remaining() * 0.15),
                        self.starting_point(relaxed),
                        objective={},
                    )
                    if physical["feasible"]:
                        s = trial
                        reasons.append(
                            {
                                "kind": "conditional_return",
                                "text": "This journey may lack departure energy. Preserve useful charging before it; subsequent battery state requires measured reconciliation.",
                            }
                        )
                        break
                    if physical["status"] != "Infeasible":
                        return self.failure(
                            snapshot, physical["status"], "Conditional travel diagnostic timed out"
                        )
                if not physical["feasible"]:
                    return self.failure(snapshot, "Infeasible", "No physical best-effort trajectory")
            achieved = None
            service_warm = physical["values"]
            tiers = sorted(s.goals, key=lambda g: (-g.priority, g.deadline, g.id))
            for goal in tiers:
                if goal.id not in relaxed.goal_slack or self.remaining() < 0.2:
                    continue
                slack = relaxed.goal_slack[goal.id]
                result = self.run_model(
                    f"service:{goal.id}",
                    relaxed,
                    self.remaining() * 0.25,
                    service_warm,
                    objective={slack: 1.0},
                )
                if not result["feasible"]:
                    return self.failure(snapshot, result["status"], "Best-effort model has no incumbent")
                achieved = result
                service_warm = result["values"]
                value = result["values"][slack]
                relaxed.linear.row([(slack, 1)], upper=value + 1e-6)
            if achieved is None:
                return self.failure(snapshot, "Infeasible", "No attainable goal profile")
            service = {
                g.id: min(
                    g.target(s.capabilities, s.policy),
                    achieved["flows"]["ev_energy"][s.checkpoint_index(g.deadline)],
                )
                for g in tiers
                if s.intervals[0].start <= g.deadline <= s.intervals[-1].end
            }
            reference_model = JointModel(s, service=service)
            reference = self.run_model(
                "best_effort_economics",
                reference_model,
                self.remaining() * 0.3,
                self.starting_point(reference_model) or reference_model.warm_from(achieved["flows"]),
            )
            if not reference["feasible"]:
                return self.failure(snapshot, reference["status"], "No authorized best-effort incumbent")
            reasons.append(
                {
                    "kind": "shortfall",
                    "text": "Original goals preserved; executable service is best effort within current permissions.",
                }
            )
        errors = self.validate_candidate(s, reference["flows"], service)
        if errors:
            return self.failure(snapshot, "invalid_solution", "; ".join(errors))
        for goal in sorted(s.goals, key=lambda g: (-g.priority, g.deadline)):
            achieved_energy = service.get(goal.id, goal.target(s.capabilities, s.policy))
            if not s.ev_known_at(s.checkpoint_index(goal.deadline)):
                continue
            if achieved_energy >= goal.target(s.capabilities, s.policy) - TOL or self.remaining() < 1:
                continue
            if goal.approval_state == "rejected":
                continue
            diagnostic_goal = replace(
                goal,
                approved_peak_kw=s.capabilities.grid_connection_kw,
                approval_state="granted",
                approval_revision=goal.revision,
            )
            trial = replace(s, goals=tuple(diagnostic_goal if g.id == goal.id else g for g in s.goals))
            diagnostic_service = {**service, goal.id: goal.target(s.capabilities, s.policy)}
            permission_model = JointModel(trial, service=diagnostic_service)
            permission_result = self.run_model(
                f"permission_diagnostic:{goal.id}",
                permission_model,
                min(4.0, self.remaining() * 0.2),
                seed(permission_model),
            )
            if permission_result["feasible"] and not self.validate_candidate(
                trial, permission_result["flows"], diagnostic_service
            ):
                required_peak = accounting(trial, permission_result["flows"])["peak_kw"]
                automatic = max(
                    s.policy.automatic_peak_kw, s.observation.monthly_peak_kw, s.policy.billing_floor_kw
                )
                if required_peak > automatic + TOL:
                    if goal.rejected_peak_kw is not None and required_peak <= goal.rejected_peak_kw + TOL:
                        continue
                    permission_proposals.append(
                        {
                            "goal_id": goal.id,
                            "revision": goal.revision,
                            "proposed_peak_kw": required_peak,
                            "shortfall_kwh": goal.target(s.capabilities, s.policy) - achieved_energy,
                            "state": "pending",
                            "text": "A feasible diagnostic meets this goal with a higher task-specific ceiling. This is forecast evidence, not an unavoidable realized peak.",
                            "diagnostic_status": permission_result["status"],
                        }
                    )
        selected, selected_model = reference, reference_model
        reference_flows = reference["flows"]
        self.reference_flows = reference_flows
        self.continuity_reserve = min(6.0, self.remaining() * .06)
        exceptional_windows: list[tuple[int, int]] = []
        normal_ceilings = [
            max(
                s.policy.normal_soc_percent / 100 * s.capabilities.ev_capacity_kwh,
                reference_flows["ev_energy"][t + 1],
            )
            for t in range(len(s.intervals))
        ]
        if self.remaining() > 1:
            normal_model = JointModel(
                s,
                optional=True,
                service=service,
                ceilings=normal_ceilings,
                tight_ceilings=True,
                grid_ess=required_support,
            )
            normal_model.add_optional_peak_limits(reference_flows)
            # Preserve time for one final solar pass before optional probes consume the budget.
            self.solar_reserve = min(6.0, self.remaining() * .10)
            solar_start = {**selected, "values": normal_model.warm_from(selected["flows"])}
            solar_start = self.prefer_solar(normal_model, solar_start,
                                            min(8.0, max(2.0, self.remaining() * .18)))
            if self.prefer_result(selected, selected_model, solar_start, normal_model):
                selected, selected_model = solar_start, normal_model
                reasons.append({"kind": "joint_capture", "text":
                                "Checked bounded solar allocation retained before the full joint search."})
            normal_seed = self.starting_point(normal_model) or normal_model.warm_from(selected["flows"])
            seed_result: dict[str, Any] = {
                "status": "Feasible incumbent",
                "feasible": True,
                "values": normal_seed,
                "flows": {
                    name: [normal_seed[i] for i in indexes]
                    for name, indexes in normal_model.linear.variables.items()
                },
            }
            if (normal_model.linear.accepts(normal_seed)
                    and not self.validate_candidate(s, seed_result["flows"], service)
                    and not rolling_comparison_errors(s, reference_flows, seed_result["flows"])):
                if self.prefer_result(selected, selected_model, seed_result, normal_model):
                    selected, selected_model = seed_result, normal_model
            normal_seed = normal_model.warm_from(selected["flows"])
            normal = self.run_model(
                "normal_ceiling_joint",
                normal_model,
                self.remaining() * 0.50,
                normal_seed,
            )
            seed_result["status"] = normal["status"]
            rolling_errors = (
                rolling_comparison_errors(s, reference_flows, normal["flows"]) if normal["feasible"] else []
            )
            if rolling_errors and self.remaining() > 2:
                time_indexes = {i.start.isoformat(): t for t, i in enumerate(s.intervals)}
                bad_origins = {
                    time_indexes[error.rsplit(" at ", 1)[-1]]
                    for error in rolling_errors
                    if error.rsplit(" at ", 1)[-1] in time_indexes
                }
                normal_model.add_rolling_limits(reference_flows, origins=bad_origins)
                normal = self.run_model(
                    "rolling_window_repair",
                    normal_model,
                    self.remaining() * 0.45,
                    normal_model.complete_warm(normal_seed),
                )
            if (
                normal["feasible"]
                and not self.validate_candidate(s, normal["flows"], service)
                and not rolling_comparison_errors(s, reference_flows, normal["flows"])
            ):
                if self.prefer_result(selected, selected_model, normal, normal_model):
                    selected, selected_model = normal, normal_model
                    reasons.append(
                        {
                            "kind": "joint_capture",
                            "text": "Normal-ceiling EV and ESS capture selected together; cash and both residual inventories pass rolling 24-hour comparisons.",
                        }
                    )
        if self.remaining() > 1:
            candidate_model = JointModel(s, optional=True, service=service, grid_ess=required_support)
            candidate_model.add_optional_peak_limits(reference_flows)
            candidate = self.run_model(
                "exceptional_opportunity_probe",
                candidate_model,
                self.remaining() * 0.20,
                candidate_model.warm_from(selected["flows"]),
            )
            if candidate["feasible"] and not self.validate_candidate(s, candidate["flows"], service):
                ceilings = [
                    max(
                        s.policy.normal_soc_percent / 100 * s.capabilities.ev_capacity_kwh,
                        reference_flows["ev_energy"][t + 1],
                    )
                    for t in range(len(s.intervals))
                ]
                # Group contiguous actual solar availability; later diagnostics may use physical 100%.
                windows: list[tuple[int, int]] = []
                left = None
                for t, interval in enumerate(s.intervals):
                    useful = interval.available and interval.pv_ac_kw + interval.pv_dc_kw > 0.05
                    if useful and left is None:
                        left = t
                    if left is not None and (not useful or t == len(s.intervals) - 1):
                        windows.append((left, t if not useful else t + 1))
                        left = None
                rejected: set[int] = set()
                for left, right in windows:
                    if not any(
                        candidate["flows"]["ev_energy"][t + 1] > ceilings[t] + TOL
                        and candidate["flows"]["amps_one"][t] + candidate["flows"]["amps_three"][t] > TOL
                        for t in range(left, right)
                    ):
                        # Later smoothing/certification must not create an unproven exception here.
                        rejected.update(range(left, right))
                        continue
                    if self.remaining() < 2:
                        rejected.update(range(left, right))
                        continue
                    diagnostic_ceilings = [s.capabilities.ev_capacity_kwh] * len(s.intervals)
                    for t in range(0, right):
                        diagnostic_ceilings[t] = ceilings[t]
                    diagnostic = JointModel(
                        s,
                        optional=True,
                        service=service,
                        ceilings=diagnostic_ceilings,
                        grid_ess=required_support,
                    )
                    v = diagnostic.linear.variables
                    for name in ("ev_energy", "ess_solar", "ess_grid"):
                        diagnostic.linear.row([(v[name][-1], 1)], lower=candidate["flows"][name][-1] - TOL)
                    imports = [
                        (v[name][t], i.hours)
                        for t, i in enumerate(s.intervals)
                        for name in ("grid_ev", "grid_house", "grid_store")
                    ]
                    diagnostic.linear.row(
                        imports, upper=accounting(s, candidate["flows"])["imports_kwh"] + TOL
                    )
                    result = self.run_model(
                        f"later_replacement:{left}", diagnostic, min(2.0, self.remaining() * 0.15)
                    )
                    if result["feasible"] or result["status"] != "Infeasible":
                        # A timeout cannot establish scarcity; keep unvalidated extra energy disabled.
                        rejected.update(range(left, right))
                    else:
                        exceptional_windows.append((left, right))
                        reasons.append(
                            {
                                "kind": "scarce_solar",
                                "start": s.intervals[left].start.isoformat(),
                                "text": "This additional solar opportunity cannot be replaced later with matching EV/ESS inventories and no additional imports.",
                            }
                        )
                if rejected:
                    final_ceilings = [
                        ceilings[t] if t in rejected else s.capabilities.ev_capacity_kwh
                        for t in range(len(s.intervals))
                    ]
                    candidate_model = JointModel(
                        s, optional=True, service=service, ceilings=final_ceilings, grid_ess=required_support
                    )
                    candidate_model.add_optional_peak_limits(reference_flows)
                    candidate = self.run_model(
                        "health_constrained_joint",
                        candidate_model,
                        self.remaining() * 0.45,
                        candidate_model.warm_from(selected["flows"]),
                    )
                if candidate["feasible"] and not self.validate_candidate(s, candidate["flows"], service):
                    rolling_errors = rolling_comparison_errors(s, reference_flows, candidate["flows"])
                    if not rolling_errors and self.prefer_result(selected, selected_model, candidate, candidate_model):
                        selected, selected_model = candidate, candidate_model
                        reasons.append(
                            {
                                "kind": "joint_capture",
                                "text": "EV and ESS capture selected together; combined cash and both residual inventories pass the rolling 24-hour comparison.",
                            }
                        )
                    elif rolling_errors:
                        reasons.append({"kind": "optional_rejected", "text": rolling_errors[0]})
        # One authorized ESS peak-intervention candidate; no standing reserve or price arbitrage.
        if self.remaining() > 2 and any(
            i.house_kw - i.pv_ac_kw > max(s.policy.billing_floor_kw, s.observation.monthly_peak_kw)
            for i in s.intervals[: min(288, len(s.intervals))]
        ):
            support_model = JointModel(s, optional=selected_model.optional, service=service, grid_ess=True)
            for t, interval in enumerate(s.intervals):
                future_peak = any(
                    j.house_kw - j.pv_ac_kw > max(s.policy.billing_floor_kw, s.observation.monthly_peak_kw)
                    for j in s.intervals[t:]
                    if interval.start < j.start <= interval.start + timedelta(hours=24)
                )
                if not future_peak:
                    support_model.linear.upper[support_model.linear.variables["grid_store"][t]] = 0
            support = self.run_model(
                "specific_peak_precharge",
                support_model,
                self.remaining() * 0.4,
                support_model.warm_from(selected["flows"]),
            )
            if (
                support["feasible"]
                and not self.validate_candidate(s, support["flows"], service)
                and not rolling_comparison_errors(s, reference_flows, support["flows"])
            ):
                if self.prefer_result(selected, selected_model, support, support_model):
                    selected, selected_model = support, support_model
                    reasons.append(
                        {
                            "kind": "peak_precharge",
                            "text": "Deliberately allow a smaller peak now to avoid a larger forecast peak within 24 hours; comparison includes losses and inventories.",
                        }
                    )
            # Show a task-specific ESS request only when the expanded strategy improves the executable one.
            future_peaks = [
                i
                for i in s.intervals
                if i.house_kw - i.pv_ac_kw
                > max(s.policy.automatic_peak_kw, s.observation.monthly_peak_kw, s.policy.billing_floor_kw)
            ]
            if future_peaks and self.remaining() > 2:
                peak = max(future_peaks, key=lambda i: i.house_kw - i.pv_ac_kw)
                identity = f"ess-peak-{peak.start.isoformat()}"
                previous = next(
                    (g for g in s.peak_permissions if g.id == identity and g.forecast_id == s.forecast_id),
                    None,
                )
                if previous is None or previous.state != "rejected":
                    grant = PeakPermission(
                        identity, s.forecast_id, peak.start, s.capabilities.grid_connection_kw, "granted"
                    )
                    trial = replace(s, peak_permissions=s.peak_permissions + (grant,))
                    expanded_model = JointModel(
                        trial, optional=selected_model.optional, service=service, grid_ess=True
                    )
                    expanded = self.run_model(
                        "ess_permission_diagnostic",
                        expanded_model,
                        min(3, self.remaining() * 0.2),
                        expanded_model.warm_from(selected["flows"]),
                    )
                    if (
                        expanded["feasible"]
                        and not self.validate_candidate(trial, expanded["flows"])
                        and not rolling_comparison_errors(trial, reference_flows, expanded["flows"])
                    ):
                        current, proposed = (
                            accounting(s, selected["flows"]),
                            accounting(trial, expanded["flows"]),
                        )
                        automatic = max(
                            s.policy.automatic_peak_kw,
                            s.observation.monthly_peak_kw,
                            s.policy.billing_floor_kw,
                        )
                        purchase_peak = max(
                            (
                                sum(
                                    expanded["flows"][name][t] * s.intervals[t].hours * 4
                                    for name in ("grid_ev", "grid_house", "grid_store")
                                    for t in slots
                                )
                                + (s.observation.quarter_import_kwh * 4 if slots[0] == 0 else 0)
                                for slots in expanded_model.quarters.values()
                                if any(expanded["flows"]["grid_store"][t] > TOL for t in slots)
                            ),
                            default=0,
                        )
                        if (
                            purchase_peak > automatic + TOL
                            and proposed["comparison_eur"] < current["comparison_eur"] - TOL
                            and proposed["peak_kw"] < current["peak_kw"] - TOL
                        ):
                            permission_proposals.append(
                                {
                                    "goal_id": identity,
                                    "kind": "ess_peak",
                                    "title": "ESS peak prevention",
                                    "revision": 1,
                                    "forecast_id": s.forecast_id,
                                    "deadline": peak.start.isoformat(),
                                    "proposed_peak_kw": purchase_peak,
                                    "shortfall_kwh": 0,
                                    "state": "pending",
                                    "text": "A smaller peak during this specific precharge avoids a larger forecast household peak within 24 hours. The automatic portion continues while approval is pending.",
                                }
                            )
        before_dispatch = selected
        selected = self.prefer_dispatch(selected_model, selected, min(8.0, self.remaining() * .5))
        if selected is not before_dispatch:
            reasons.append({"kind": "joint_dispatch", "text":
                            "Sources and ESS dispatch refined for the selected EV schedule before continuity review."})
        reserved = self.solar_reserve
        self.solar_reserve = 0.0
        if selected_model.optional:
            before_solar = selected
            selected = self.prefer_solar(selected_model, selected, min(reserved, self.remaining() * .75))
            if selected is not before_solar:
                reasons.append({"kind": "solar_allocation", "text":
                                "Checked bounded solar allocation improved the plan before source certification."})
        selected = self.prefer_earlier(selected_model, selected, min(8.0, self.remaining() * .35))
        self.continuity_reserve = 0.0
        selected = self.review_continuity("final_continuity", selected_model, selected,
                                           min(24.0, self.remaining() * .85))
        continuity_review = selected["continuity_review"]
        protected = ChargingContinuity(selected_model, selected["flows"], [
            ChargingWindow(r["first"], r["last"], r["available"]) for r in continuity_review["windows"]])
        economic_status = selected["status"]
        polish_reference_summary = accounting(s, selected["flows"])
        before_score = selected.get("economic_baseline", selected_model.value(
            selected_model.economic, selected["values"]))
        before_cash = selected.get("cash_baseline", selected_model.value(
            selected_model.cash, selected["values"]))
        planning_status = economic_status
        source_certificate = False
        if self.remaining() > 0.5:
            source_model = JointModel(
                s,
                optional=True,
                service=service,
                ceilings=selected_model.ceilings,
                tight_ceilings=selected_model.tight_ceilings,
                grid_ess=any(v > TOL for v in selected["flows"]["grid_store"]),
            )
            source_model.add_continuity_limits()
            protected.protect(source_model)
            timing = protected.timing_terms(source_model)
            source_model.linear.row(list(timing.items()), upper=source_model.value(
                timing, source_model.warm_from(selected["flows"])) + 1e-6)
            continuity = source_model.continuity_objective()
            source_model.linear.row(list(continuity.items()), upper=source_model.value(
                continuity, source_model.warm_from(selected["flows"])) + 1e-6)
            source_model.linear.row(list(source_model.economic.items()),
                                    upper=before_score + s.policy.polish_tolerance_eur + TOL)
            source_model.linear.row(list(source_model.cash.items()),
                                    upper=before_cash + s.policy.polish_tolerance_eur + TOL)
            for _, slots in source_model.quarters.items():
                original_import = sum(
                    sum(selected["flows"][name][t] for name in ("grid_ev", "grid_house", "grid_store"))
                    * s.intervals[t].hours
                    for t in slots
                )
                source_model.linear.row(
                    [
                        (source_model.linear.variables[name][t], s.intervals[t].hours)
                        for t in slots
                        for name in ("grid_ev", "grid_house", "grid_store")
                    ],
                    upper=original_import + 1e-7,
                )
            adjustable = {
                "ev_energy",
                "grid_ev",
                "grid_cumulative",
                "amps_one",
                "amps_three",
                "start",
                "phase_change",
                "phase_restart",
                "variation",
                "phase_setting",
                "causal_witness",
                "grid_direction",
            }
            for name, indexes in source_model.linear.variables.items():
                if name in adjustable or name.startswith(("peak_", "quarter_")):
                    continue
                for index, value in zip(indexes, selected["flows"][name]):
                    source_model.linear.lower[index] = value
                    source_model.linear.upper[index] = value
            for t, index in enumerate(source_model.linear.variables["ev_energy"]):
                source_model.linear.upper[index] = selected["flows"]["ev_energy"][t] + TOL
            for goal in s.goals:
                at = max(
                    s.intervals[0].start,
                    goal.deadline - timedelta(minutes=s.policy.completion_margin_minutes),
                )
                k = s.checkpoint_index(at)
                source_model.linear.lower[source_model.linear.variables["ev_energy"][k]] = min(
                    goal.target(s.capabilities, s.policy), selected["flows"]["ev_energy"][k]
                )
            source_result = self.run_model(
                "minimum_necessary_grid_certificate",
                source_model,
                self.remaining() - 0.3,
                source_model.warm_from(selected["flows"]),
                objective={source_model.linear.variables["grid_cumulative"][-1]: 1.0},
            )
            if (source_result["feasible"]
                    and source_model.linear.accepts(source_model.warm_from(source_result["flows"]))
                    and not self.validate_candidate(s, source_result["flows"], service)):
                if not selected_model.optional or not rolling_comparison_errors(
                    s, reference_flows, source_result["flows"]
                ):
                    selected = source_result
                    source_certificate = source_result["status"] == "Optimal"
        output = self.output(snapshot, s, selected, reference, service, reasons, exceptional_windows)
        output["status"] = planning_status
        output["minimum_grid_certified"] = source_certificate
        output["permission_proposals"] = permission_proposals
        output["polish_reference_summary"] = polish_reference_summary
        final_continuity = ChargingContinuity(selected_model, selected["flows"])
        for window, record in zip(protected.windows, continuity_review["windows"]):
            record["sessions_final"] = final_continuity.sessions(window)
        output["continuity_review"] = continuity_review
        return output

    def failure(self, s: Snapshot, status: str, reason: str) -> dict[str, Any]:
        return {
            "id": uuid4().hex,
            "snapshot_id": s.id,
            "revision": s.revision,
            "status": status,
            "valid": False,
            "reason": reason,
            "stages": self.stages,
            "summary": {},
            "seconds": monotonic() - self.started,
        }

    def output(
        self,
        original: Snapshot,
        s: Snapshot,
        result: dict[str, Any],
        reference: dict[str, Any],
        service: dict[str, float],
        reasons: list[dict[str, Any]],
        exceptional: list[tuple[int, int]],
    ) -> dict[str, Any]:
        flows = result["flows"]
        goals = []
        for goal in original.goals:
            if not s.intervals[0].start <= goal.deadline <= s.intervals[-1].end:
                continue
            k = s.checkpoint_index(goal.deadline)
            target = goal.target(s.capabilities, s.policy)
            actual = flows["ev_energy"][k]
            known_state = s.ev_known_at(k)
            ready_index = k
            if actual >= target - TOL and known_state:
                while ready_index > 0 and flows["ev_energy"][ready_index - 1] >= target - TOL:
                    ready_index -= 1
            ready_at = s.intervals[0].start if ready_index == 0 else s.intervals[ready_index - 1].end
            margin = (
                (goal.deadline - ready_at).total_seconds() / 60
                if actual >= target - TOL and known_state
                else None
            )
            goals.append(
                {
                    **json_data(goal),
                    "target_kwh": target,
                    "planned_kwh": actual if known_state else None,
                    "shortfall_kwh": max(0, target - actual) if known_state else None,
                    "status": ("scheduled" if actual >= target - TOL else "shortfall")
                    if known_state
                    else "unknown_return_state",
                    "completion_at": ready_at.isoformat() if margin is not None else None,
                    "completion_margin_minutes": margin,
                    "desired_margin_met": margin is not None and margin >= s.policy.completion_margin_minutes,
                    "external_charging_required": goal.kind == "trip"
                    and goal.withdrawal(s.policy)
                    + s.policy.arrival_reserve_km * s.policy.consumption_kwh_per_100km / 100
                    > s.capabilities.ev_capacity_kwh,
                }
            )
        sessions: list[dict[str, Any]] = []
        left = None
        for t in range(len(s.intervals) + 1):
            power = (
                (flows["amps_one"][t] + 3 * flows["amps_three"][t]) * s.capabilities.voltage / 1000
                if t < len(s.intervals)
                else 0
            )
            if power > TOL and left is None:
                left = t
            if left is not None and power <= TOL:
                sessions.append(
                    {
                        "id": f"ev-{s.intervals[left].start.isoformat()}",
                        "resource": "ev",
                        "title": "EV charging",
                        "start": s.intervals[left].start.isoformat(),
                        "end": s.intervals[t - 1].end.isoformat(),
                        "energy_kwh": sum(
                            (flows["pv_ev"][k] + flows["grid_ev"][k] + flows["solar_dis_ev"][k])
                            * s.intervals[k].hours
                            * s.capabilities.ev_efficiency
                            for k in range(left, t)
                        ),
                        "goal_ids": [],
                        "reason": "Required goal progress and/or jointly selected eligible solar inventory",
                    }
                )
                left = None
        attribute_ev_sessions(s, flows, sessions)
        extra = max(0.0, flows["ev_energy"][-1] - reference["flows"]["ev_energy"][-1])
        conditional_tasks: list[dict[str, Any]] = []
        remaining_optional = extra
        for session in sessions:
            if remaining_optional <= TOL:
                break
            slots = [
                t
                for t, i in enumerate(s.intervals)
                if i.start.isoformat() >= session["start"] and i.end.isoformat() <= session["end"]
            ]
            eligible = sum(
                max(
                    0,
                    flows["pv_ev"][t]
                    + flows["solar_dis_ev"][t]
                    - reference["flows"]["pv_ev"][t]
                    - reference["flows"]["solar_dis_ev"][t],
                )
                * s.intervals[t].hours
                * s.capabilities.ev_efficiency
                for t in slots
            )
            quantity = min(remaining_optional, eligible)
            if quantity <= TOL:
                continue
            conditional_tasks.append(
                {
                    "id": f"solar-capture-{session['start']}",
                    "title": "EV solar capture",
                    "origin": "catalogue.ev_surplus_capture",
                    "scheduled_start": session["start"],
                    "deadline": session["end"],
                    "quantity_kwh": quantity,
                    "target_ev_kwh": flows["ev_energy"][slots[-1] + 1],
                    "source": "eligible solar/ESS only",
                    "allowed_modes": list(s.capabilities.phases),
                    "reason": "Selected jointly with ESS; cash and both residual inventories pass rolling 24-hour comparisons",
                    "forecast_id": s.forecast_id,
                }
            )
            session["title"] = "EV charging · solar capture"
            remaining_optional -= quantity
        if extra > TOL and not any(r["kind"] == "joint_capture" for r in reasons):
            reasons.append(
                {
                    "kind": "joint_capture",
                    "text": "Selected solar inventory and required service share one trajectory; all rolling comparisons passed.",
                }
            )
        ev_session_count = len(sessions)
        ess_left = None
        previous_mode = 0
        for t in range(len(s.intervals) + 1):
            incoming = (
                (flows["pv_store"][t] + flows["grid_store"][t]) * s.capabilities.ac_charge_efficiency
                + flows["dc_store"][t] * s.capabilities.dc_efficiency
                if t < len(s.intervals)
                else 0
            )
            outgoing = (
                sum(flows[name][t] for name in ("solar_dis_ev", "solar_dis_house", "grid_dis_house"))
                / s.capabilities.ac_discharge_efficiency
                if t < len(s.intervals)
                else 0
            )
            mode = 1 if incoming > 0.05 else -1 if outgoing > 0.05 else 0
            if ess_left is not None and mode != previous_mode:
                sessions.append(
                    {
                        "id": f"ess-{s.intervals[ess_left].start.isoformat()}",
                        "resource": "ess",
                        "title": "ESS charging" if previous_mode == 1 else "ESS supplying loads",
                        "start": s.intervals[ess_left].start.isoformat(),
                        "end": s.intervals[t - 1].end.isoformat(),
                        "energy_kwh": sum(
                            abs(
                                (flows["pv_store"][k] + flows["grid_store"][k])
                                * s.capabilities.ac_charge_efficiency
                                + flows["dc_store"][k] * s.capabilities.dc_efficiency
                                - sum(
                                    flows[name][k]
                                    for name in ("solar_dis_ev", "solar_dis_house", "grid_dis_house")
                                )
                                / s.capabilities.ac_discharge_efficiency
                            )
                            * s.intervals[k].hours
                            for k in range(ess_left, t)
                        ),
                        "goal_ids": [],
                        "reason": "Joint household/EV support and surplus capture; source and peak permissions remain binding",
                    }
                )
                ess_left = None
            if mode and ess_left is None:
                ess_left = t
            previous_mode = mode
        sessions.sort(key=lambda item: item["start"])
        grouped = []
        last_ess = None
        for session in sessions:
            if session["resource"] == "ess":
                if (
                    last_ess is not None
                    and session["title"] == last_ess["title"]
                    and (instant(session["start"]) - instant(last_ess["end"])).total_seconds() <= 1800
                ):
                    last_ess["end"] = session["end"]
                    last_ess["energy_kwh"] += session["energy_kwh"]
                    last_ess["contains_pauses"] = True
                    continue
                last_ess = session
            grouped.append(session)
        sessions = sorted(grouped, key=lambda item: item["start"])
        summary: dict[str, Any] = dict(accounting(s, flows))
        last_phase = s.observation.ev_phases
        phase_switches = 0
        for t in range(len(s.intervals)):
            mode = 3 if flows["three"][t] > 0.5 else 1 if flows["one"][t] > 0.5 else 0
            if mode:
                phase_switches += mode != last_phase
                last_phase = mode
        summary.update(
            {
                "ev_terminal_state_known": s.ev_known_at(len(s.intervals)),
                "optional_ev_kwh": extra,
                "sessions": ev_session_count,
                "ess_sessions": len(sessions) - ev_session_count,
                "phase_changes": phase_switches,
                "three_phase_activation_changes": sum(
                    abs(flows["three"][t] - flows["three"][t - 1]) > 0.5 for t in range(1, len(s.intervals))
                ),
                "validation": "passed",
                "intervals": len(s.intervals),
                "provenance": s.provenance,
            }
        )
        return {
            "id": uuid4().hex,
            "snapshot_id": original.id,
            "revision": original.revision,
            "status": result["status"],
            "valid": True,
            "goals": goals,
            "flows": flows,
            "intervals": json_data(s.intervals),
            "sessions": sessions,
            "conditional_tasks": conditional_tasks,
            "reservations": reservations(s, flows),
            "forecast_at": s.forecast_at.isoformat(),
            "peak_permissions": json_data(s.peak_permissions),
            "summary": summary,
            "reference_summary": accounting(s, reference["flows"]),
            "reference_flows": reference["flows"],
            "reasons": reasons,
            "service": service,
            "exceptional_windows": exceptional,
            "stages": self.stages,
            "seconds": monotonic() - self.started,
            "input_digest": original.digest,
            "effective_snapshot": json_data(s) if s != original else None,
        }


def plan_snapshot(data: dict[str, Any], progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Spawn-safe worker entry point; imports no HA client or controller."""
    return Planner(progress).plan(Snapshot.from_dict(data))
