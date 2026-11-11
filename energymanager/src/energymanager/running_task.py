"""Bounded joint replacement preference for a still-authorized running EV task."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from time import monotonic
from typing import Any, TYPE_CHECKING

from .domain import encode, instant
from .optimization import JointModel
from .validation import TOL, rolling_comparison_errors

if TYPE_CHECKING:
    from .planner import Planner


def phase_lock(model: JointModel, phase: int, deadline: str) -> None:
    opposite = "three" if phase == 1 else "one"
    until = instant(deadline)
    for t, interval in enumerate(model.snapshot.intervals):
        if interval.start < until:
            model.linear.upper[model.linear.variables[opposite][t]] = 0.0


def profile_on_grid(model: JointModel, context: dict[str, Any]) -> list[tuple[int, int]]:
    profile = context["profile"]
    result = []
    k = 0
    for interval in model.snapshot.intervals:
        while k < len(profile) and instant(profile[k]["end"]) <= interval.start:
            k += 1
        item = profile[k] if k < len(profile) and instant(profile[k]["start"]) <= interval.start else None
        result.append((item["one"], item["three"]) if item else (0, 0))
    return result


def pin_profile(model: JointModel, modes: list[tuple[int, int]], end: int) -> None:
    for t, (one, three) in enumerate(modes[:end]):
        for name, value in (("one", int(one > 0)), ("three", int(three > 0)),
                            ("amps_one", one), ("amps_three", three)):
            model.linear.equality([(model.linear.variables[name][t], 1)], value)


def earlier_current_profile(model: JointModel, modes: list[tuple[int, int]], end: int) -> list[tuple[int, int]] | None:
    """One quantity-preserving current seed, subject to a complete joint solve.

    Equal-length already-on slots exchange integer amps without changing phases,
    starts or useful delivery. Forecast PV only orders the search; full household/
    ESS economics and all source constraints decide whether it is usable/better.
    """
    s, c = model.snapshot, model.snapshot.capabilities
    profile = list(modes)
    slots = [t for t in range(end) if s.ev_commitment(t) is None
             and abs(s.intervals[t].hours-5/60)<1e-9 and sum(profile[t]) > 0]
    surplus = [i.pv_ac_kw+i.pv_dc_kw*c.ac_discharge_efficiency-i.house_kw for i in s.intervals]
    changed = False
    for early in sorted(slots,key=lambda t:(-surplus[t],t)):
        mode = 0 if profile[early][0] else 1
        for late in reversed(slots):
            if late <= early or surplus[late] >= surplus[early] or not profile[late][mode]:
                continue
            amount = min(c.maximum_current_a-profile[early][mode],profile[late][mode]-c.minimum_current_a)
            if amount <= 0:
                continue
            a,b = list(profile[early]),list(profile[late])
            a[mode] += amount
            b[mode] -= amount
            profile[early],profile[late]=(a[0],a[1]),(b[0],b[1])
            changed = True
    return profile if changed else None


def review_running(planner: Planner, model: JointModel, selected: dict[str, Any],
                   economic: float, cash: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Compare checked complete joint candidates inside the original wall deadline.

    No candidate/update adds another tolerance to a previously tolerated candidate.
    One same-phase reference anchors every comparison, at matching useful EV stock
    and terminal value. An unfinished phase-preserving search grants no phase change.
    """
    s = model.snapshot
    context = (s.execution or {}).get("running_task")
    record: dict[str, Any] = {"status":"not_applicable", "attempts":[]}
    if not context:
        return selected, record
    record.update(status="unverified", context=context, input_digest=s.digest)
    scope = sum(i.end <= instant(context["deadline"]) for i in s.intervals)
    if not scope or planner.remaining() < .5:
        return None, record
    phase = context["phase"]
    allowance = context.get("allowance", {})
    spent = min(s.policy.polish_tolerance_eur,max(0.,allowance.get("spent_eur",0.)))
    available = max(0.,s.policy.polish_tolerance_eur-spent)
    phase_name = "three" if phase == 3 else "one"
    opposite = "one" if phase == 3 else "three"
    selected_preserves_phase = not any(v > .5 for v in selected["flows"][opposite][:scope])

    def checked(base: JointModel, name: str, allowance: float, warm: dict[str, Any] | None = None,
                *, proof: bool = False) -> dict[str, Any] | None:
        if planner.remaining() < .35:
            record["attempts"].append({"name":name, "status":"No remaining construction/audit budget"})
            return None
        values = base.warm_from(warm["flows"]) if warm else None
        if values is not None and not base.linear.accepts(values):
            values = None
        until = monotonic() + min(allowance, planner.remaining()-.2)
        result = planner.run_model(name, base, max(.01, until-monotonic()), values,
                                   objective={} if proof else base.economic)
        errors = []
        if result["feasible"]:
            errors = planner.validate_candidate(s, result["flows"], model.service)
            if not base.linear.accepts(base.warm_from(result["flows"])):
                errors.append("Restricted joint rows reject candidate")
            if not proof and model.optional:
                reference = planner.reference_flows or selected["flows"]
                rolling = rolling_comparison_errors(s, reference, result["flows"])
                # Add the same joint rolling constraints used by the ordinary
                # planner, then re-solve within this attempt's existing allowance.
                if rolling and until-monotonic() > .35 and planner.remaining() > .5:
                    indexes = {i.start.isoformat():t for t,i in enumerate(s.intervals)}
                    origins = {indexes[e.rsplit(" at ",1)[-1]] for e in rolling if e.rsplit(" at ",1)[-1] in indexes}
                    base.add_rolling_limits(reference, origins=origins)
                    result = planner.run_model(name+"_rolling", base, min(until-monotonic(),planner.remaining()-.2),
                        base.warm_from(result["flows"]), objective=base.economic)
                    if result["feasible"]:
                        errors = planner.validate_candidate(s,result["flows"],model.service)
                        if not base.linear.accepts(base.warm_from(result["flows"])):
                            errors.append("Restricted rolling rows reject candidate")
                        rolling = rolling_comparison_errors(s,reference,result["flows"])
                errors += rolling
        evidence = {"name":name, "status":result["status"], "feasible":result["feasible"], "errors":errors}
        if result["feasible"] and not errors:
            values = base.warm_from(result["flows"])
            evidence.update(comparison_eur=base.value(base.economic,values),cash_eur=base.value(base.cash,values),
                ev_terminal_kwh=result["flows"]["ev_energy"][-1],
                ess_terminal_kwh=result["flows"]["ess_solar"][-1]+result["flows"]["ess_grid"][-1],
                ev_solar_kwh=sum((result["flows"]["pv_ev"][t]+result["flows"]["solar_dis_ev"][t])*i.hours
                    for t,i in enumerate(s.intervals)),flow_digest=sha256(encode(result["flows"]).encode()).hexdigest())
        record["attempts"].append(evidence)
        return result if result["feasible"] and not errors else None

    same = deepcopy(model)
    phase_lock(same, phase, context["deadline"])
    physical_same = deepcopy(same)
    if selected_preserves_phase:
        same.linear.row(list(same.economic.items()), upper=economic+available+TOL)
        same.linear.row(list(same.cash.items()), upper=cash+available+TOL)
    known_necessity = planner.running_phase_necessity
    proven = (known_necessity.get("input_digest") == s.digest
              and known_necessity.get("status") == "Infeasible" and known_necessity.get("joint_support_infeasible")
              and known_necessity.get("service") == model.service)
    anchor = None if proven else checked(same, "running_same_phase", min(8., planner.remaining()*.3), selected)
    if (anchor is None and selected_preserves_phase and same.linear.accepts(same.warm_from(selected["flows"]))
            and not planner.validate_candidate(s, selected["flows"], model.service)):
        anchor = selected
    if anchor is None:
        # Remove optional-delivery objectives for the necessity proof. Failure to
        # preserve optional capture can never establish a need to switch phases.
        if planner.remaining() < 1.5:
            return None, record
        if proven:
            proof, status = None, "Infeasible"
        else:
            required = JointModel(s, service=model.service, grid_ess=True)
            phase_lock(required, phase, context["deadline"])
            proof = checked(required, "running_phase_necessity", min(7., planner.remaining()*.4), proof=True)
            status = record["attempts"][-1]["status"]
        if proof is not None or status != "Infeasible":
            record["reason"] = "Same-phase required service not disproven; retain independently valid prior execution"
            return None, record
        record["phase_necessity"] = {"status":"Infeasible", "input_digest":s.digest,
            "phase":phase, "deadline":context["deadline"], "service":model.service}
        same, anchor = deepcopy(model), selected
    else:
        record["phase_necessity"] = {"status":"same_phase_feasible", "phase":phase}

    anchor_values = same.warm_from(anchor["flows"])
    # Carry the existing economic floor when it already belonged to this phase
    # family; phase-free price alone cannot overrule phase-preserving feasibility.
    anchor_economic = same.value(same.economic, anchor_values)
    anchor_cash = same.value(same.cash, anchor_values)
    if selected_preserves_phase:
        anchor_economic, anchor_cash = min(anchor_economic, economic), min(anchor_cash, cash)
    modes = profile_on_grid(same, context)
    tail = None
    kind = "same_phase_tail"
    if context.get("finish_at") and planner.remaining() > .5:
        finish, old_end = instant(context["finish_at"]), instant(context["old_end"])
        end_modes = list(modes)
        last = next((modes[t] for t in reversed(range(scope)) if s.intervals[t].start < old_end and sum(modes[t]) > 0), (0, 0))
        for t, interval in enumerate(s.intervals[:scope]):
            if finish <= interval.start < old_end:
                end_modes[t] = (0, 0)
            elif old_end <= interval.start < finish:
                end_modes[t] = last
        finishing = deepcopy(physical_same if record["phase_necessity"]["status"] == "same_phase_feasible" else same)
        pin_profile(finishing, end_modes, scope)
        tail = checked(finishing, "running_finish_only", min(4., planner.remaining()*.25), anchor)
        if tail:
            kind = "finish_only"
            # Integer-slot economic references can contain a few surplus Wh. Do
            # not reject an exact finishing event or call less energy a saving:
            # re-solve the earlier option at this same checked useful delivery.
            # Prices from a different rounded delivery cannot bound this solve.
            # Recompute one matched reference; the carried allowance ledger below
            # still prevents buying another comparison/cash margin on this update.
            matching = deepcopy(physical_same if record["phase_necessity"]["status"] == "same_phase_feasible" else model)
            for k in {scope, len(s.intervals)}:
                matching.linear.equality([(matching.linear.variables["ev_energy"][k], 1)], tail["flows"]["ev_energy"][k])
            warm = tail
            seed_profile = earlier_current_profile(matching,end_modes,scope)
            if seed_profile and planner.remaining() > .8:
                seeded = deepcopy(matching)
                pin_profile(seeded,seed_profile,scope)
                seed = checked(seeded,"running_economic_seed",min(2.,planner.remaining()*.25),tail)
                if seed and matching.value(matching.economic,matching.warm_from(seed["flows"])) < matching.value(
                        matching.economic,matching.warm_from(tail["flows"])):
                    warm = seed
            matched = checked(matching, "running_matched_reference", min(8., planner.remaining()*.5), warm)
            if matched is None:
                return None, record
            anchor = matched
            anchor_values = same.warm_from(anchor["flows"])
            anchor_economic = same.value(same.economic, anchor_values)
            anchor_cash = same.value(same.cash, anchor_values)
        elif record["attempts"][-1]["status"] != "Infeasible":
            record["reason"] = "Finish-only preference unverified within remaining budget"
            return None, record
    if tail is None and planner.remaining() > .5:
        search = deepcopy(physical_same if record["phase_necessity"]["status"] == "same_phase_feasible" else same)
        for k in {scope, len(s.intervals)}:
            search.linear.equality([(search.linear.variables["ev_energy"][k], 1)], anchor["flows"]["ev_energy"][k])
        # Feasibility is monotone as a fixed prefix is shortened. Binary search
        # visits only bounded suffixes; unknown results are never infeasibility.
        low, high = 0, scope
        tail = anchor
        while low + 1 < high and planner.remaining() > .5:
            cut = (low+high)//2
            trial = deepcopy(search)
            pin_profile(trial, modes, cut)
            proposed = checked(trial, "running_suffix:"+str(cut), min(3., planner.remaining()*.45), tail)
            if proposed:
                low, tail = cut, proposed
            elif record["attempts"][-1]["status"] == "Infeasible":
                high = cut
            else:
                record["suffix_optimality"] = "unverified beyond checked prefix"
                if low == 0:
                    return None, record
                break
        record["held_prefix_intervals"] = low
    tail = tail or anchor
    record["comparison"] = {"economic_eur":anchor_economic, "cash_eur":anchor_cash,
        "shared_tolerance_eur":s.policy.polish_tolerance_eur, "matching_stock":{str(k):anchor["flows"]["ev_energy"][k]
            for k in {scope, len(s.intervals)}}}
    values = same.warm_from(tail["flows"])
    comparison, payment = same.value(same.economic, values), same.value(same.cash, values)
    premium, cash_premium = max(0.,comparison-anchor_economic), max(0.,payment-anchor_cash)
    # Revalue the still-held old profile on these matching inputs. Future premium
    # already authorized by the same ledger is retained, not purchased twice.
    retained = min(spent,premium) if kind == "finish_only" else 0.
    retained_cash = min(spent,cash_premium) if kind == "finish_only" else 0.
    if premium > available+retained+TOL or cash_premium > available+retained_cash+TOL:
        record.update(status="earlier_economic_exception", tail_economic_eur=comparison, tail_cash_eur=payment)
        chosen = anchor
    else:
        record["status"] = kind if record["phase_necessity"]["status"] == "same_phase_feasible" else "necessary_phase_tail"
        chosen = tail
    record["phase_family"] = phase_name if record["phase_necessity"]["status"] == "same_phase_feasible" else "phase_change_proven_necessary"
    chosen["economic_baseline"], chosen["cash_baseline"] = anchor_economic, anchor_cash
    chosen_values = same.warm_from(chosen["flows"])
    used = max(0.,same.value(same.economic,chosen_values)-anchor_economic-retained,
               same.value(same.cash,chosen_values)-anchor_cash-retained_cash)
    record["allowance"] = {"task_key":allowance.get("task_key"), "spent_eur":min(s.policy.polish_tolerance_eur,spent+used),
        "remaining_eur":max(0.,available-used),"retained_future_comparison_eur":retained,
        "retained_future_cash_eur":retained_cash}
    return chosen, record
