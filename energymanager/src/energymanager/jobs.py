"""Generic flexible consumption and non-interruptible cycles in the shared AC balance."""

from datetime import UTC, timedelta


def add_jobs(model, highspy, plan):
    variables = {}
    occupancy = {}
    totals = [0.0 for _ in plan.intervals]
    for job in plan.jobs:
        if job.job_id in variables or job.job_id in {"ev", "ess"}:
            raise ValueError("duplicate or reserved job ID")
        occupied = [0.0 for _ in plan.intervals]
        shared = sum(j.resource_id == job.resource_id for j in plan.jobs) > 1
        eligible = []
        for i, slot in enumerate(plan.intervals):
            start = slot.period_start_local.astimezone(UTC)
            end = start + timedelta(minutes=15)
            if (
                start >= job.earliest_start.astimezone(UTC)
                and end <= job.latest_finish.astimezone(UTC)
                and not any(start < b.astimezone(UTC) and end > a.astimezone(UTC) for a, b in job.unavailable)
            ):
                eligible.append(i)
        powers = [0.0 for _ in plan.intervals]
        if job.cycle_kw:
            starts = [i for i in eligible if all(i + j in eligible for j in range(len(job.cycle_kw)))]
            if not starts:
                raise ValueError(f"infeasible job cycle: {job.job_id}")
            choices = [model.addVariable(lb=0, ub=1, type=highspy.HighsVarType.kInteger) for _ in starts]
            model.addConstr(sum(choices) == 1)
            for start, choice in zip(starts, choices, strict=True):
                for j, power in enumerate(job.cycle_kw):
                    powers[start + j] += power * choice
                    occupied[start + j] += choice
        else:
            if len(eligible) * 0.25 * job.max_power_kw + 1e-8 < job.energy_kwh:
                raise ValueError(f"infeasible job energy: {job.job_id}")
            for i in eligible:
                powers[i] = model.addVariable(lb=0, ub=job.max_power_kw)
                if shared:
                    occupied[i] = model.addVariable(lb=0, ub=1, type=highspy.HighsVarType.kInteger)
                    model.addConstr(powers[i] <= job.max_power_kw * occupied[i])
            model.addConstr(sum(powers) * 0.25 == job.energy_kwh)
        if shared:
            occupancy.setdefault(job.resource_id, []).append(occupied)
        variables[job.job_id] = powers
        totals = [a + b for a, b in zip(totals, powers, strict=True)]
    for jobs in occupancy.values():
        for i in range(len(plan.intervals)):
            used = sum(job[i] for job in jobs)
            if not isinstance(used, (int, float)):
                model.addConstr(used <= 1)
    states = {}
    penalty = 0.0
    shortfalls = []
    for resource in plan.resources:
        if resource.resource_id in variables or resource.resource_id in {"ess", "ev"}:
            raise ValueError("duplicate or reserved generic resource ID")
        if resource.withdrawals_kwh and len(resource.withdrawals_kwh) != len(plan.intervals):
            raise ValueError("resource withdrawals must cover the frozen horizon")
        # Requirement.earliest_start describes a state requirement, not hardware availability.
        # Only explicit resource windows restrict input; every charged slot must fit wholly.
        charge = []
        for slot in plan.intervals:
            start = slot.period_start_local.astimezone(UTC)
            allowed = resource.charging_windows is None or any(
                start >= a.astimezone(UTC) and start + timedelta(minutes=15) <= b.astimezone(UTC)
                for a, b in resource.charging_windows
            )
            charge.append(model.addVariable(lb=0, ub=resource.max_input_kw if allowed else 0))
        energy = [model.addVariable(lb=resource.initial_kwh, ub=resource.initial_kwh)]
        for i in range(len(plan.intervals)):
            energy.append(model.addVariable(lb=resource.reserve_kwh, ub=resource.capacity_kwh))
            withdrawal = resource.withdrawals_kwh[i] if resource.withdrawals_kwh else 0
            model.addConstr(energy[i + 1] == energy[i] + .25 * resource.charge_efficiency * charge[i] - withdrawal)
        variables[resource.resource_id] = charge
        states[resource.resource_id] = energy
        totals = [a + b for a, b in zip(totals, charge, strict=True)]
    for requirement in plan.requirements:
        if requirement.resource_id in {"ev", "ess"}:
            continue  # Native resources retain their existing specialized electrical constraints.
        if requirement.resource_id not in states or requirement.unit != "kWh" or requirement.deadline is None:
            raise ValueError("unsupported generic state requirement")
        if requirement.earliest_start is not None and (
            requirement.earliest_start.astimezone(UTC) > requirement.deadline.astimezone(UTC)
        ):
            raise ValueError("state requirement starts after deadline")
        boundaries = [i.period_start_local.astimezone(UTC) for i in plan.intervals]
        boundaries.append(boundaries[-1] + timedelta(minutes=15))
        indexes = [i for i, at in enumerate(boundaries) if at <= requirement.deadline.astimezone(UTC)]
        if not indexes or requirement.deadline.astimezone(UTC) > boundaries[-1] or requirement.amount is None:
            raise ValueError("state requirement outside horizon or without amount")
        stored = states[requirement.resource_id][indexes[-1]]
        if requirement.hard:
            model.addConstr(stored >= requirement.amount)
        else:
            if requirement.penalty_eur_per_unit is None or requirement.penalty_eur_per_unit < 0:
                raise ValueError("soft generic state requires explicit EUR/kWh penalty")
            shortfall = model.addVariable(lb=0, ub=requirement.amount)
            model.addConstr(stored + shortfall >= requirement.amount)
            penalty += shortfall * requirement.penalty_eur_per_unit
            shortfalls.append((shortfall, stored, requirement.amount))
    return variables, totals, states, penalty, shortfalls
