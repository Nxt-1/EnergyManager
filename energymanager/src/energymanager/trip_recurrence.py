"""Weekly wall-time recurrence with independent, stable occurrence identities."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo

from .domain import instant


def weekly_rule(value: dict[str, Any]) -> dict[str, Any]:
    interval, days = value.get("weeks", 1), value.get("weekdays")
    if type(interval) is not int or not 1 <= interval <= 52:
        raise ValueError("Repeat every 1–52 weeks")
    if (
        not isinstance(days, list)
        or not days
        or any(type(day) is not int or not 0 <= day <= 6 for day in days)
    ):
        raise ValueError("Select recurrence weekdays")
    until = value.get("until")
    if until:
        date.fromisoformat(until)
    result = {"weeks": interval, "weekdays": sorted(set(days)), "until": until or None}
    week_start = value.get("week_start", 0)
    if type(week_start) is not int or not 0 <= week_start <= 6:
        raise ValueError("Invalid recurrence week start")
    if week_start:
        result["week_start"] = week_start
    return result


def google_rule(master: dict[str, Any]) -> list[str]:
    rule = weekly_rule(master["rule"])
    names = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
    text = f"RRULE:FREQ=WEEKLY;INTERVAL={rule['weeks']};BYDAY=" + ",".join(
        names[day] for day in rule["weekdays"]
    )
    if rule.get("week_start"):
        text += ";WKST=" + names[rule["week_start"]]
    until = date.fromisoformat(rule["until"]) if rule["until"] else None
    if master.get("cutoff"):
        cutoff = date.fromisoformat(master["cutoff"]) - timedelta(days=1)
        until = min(until, cutoff) if until else cutoff
    if until:
        stop = datetime.combine(until, time(23, 59, 59), ZoneInfo(master["timezone"]))
        text += ";UNTIL=" + instant(stop).strftime("%Y%m%dT%H%M%SZ")
    return [text]


def parse_google_rule(lines: list[str], timezone: str, start: str | None = None) -> dict[str, Any]:
    from icalendar import vRecur

    rules = [line[6:] for line in lines if line.startswith("RRULE:")]
    if len(rules) != 1 or any(not line.startswith("RRULE:") for line in lines):
        raise ValueError("Use one weekly rule; edit exceptions individually")
    rule = vRecur.from_ical(rules[0])
    if rule.get("FREQ") != ["WEEKLY"] or set(rule) - {"FREQ", "INTERVAL", "BYDAY", "UNTIL", "WKST"}:
        raise ValueError("Supported recurrence is every N weeks, selected weekdays and optional end date")
    names = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
    until = rule.get("UNTIL", [None])[0]
    if until is not None and not isinstance(until,date):
        raise ValueError("Invalid recurrence end date")
    until_date = (instant(until).astimezone(ZoneInfo(timezone)).date() if isinstance(until,datetime) else until)
    days = [names.index(str(day)) for day in rule.get("BYDAY", [])]
    if not days and start:
        days = [instant(start).astimezone(ZoneInfo(timezone)).weekday()]
    return weekly_rule(
        {
            "weeks": int(rule.get("INTERVAL", [1])[0]),
            "weekdays": days,
            "week_start": names.index(str(rule.get("WKST", ["MO"])[0])),
            "until": until_date.isoformat() if until_date else None,
        }
    )


def wall_instant(day: date, clock: time, zone: ZoneInfo, fold: int) -> datetime | None:
    naive = datetime.combine(day, clock.replace(tzinfo=None))
    candidate = naive.replace(tzinfo=zone, fold=fold)
    checked = instant(candidate).astimezone(zone)
    # RFC recurrence omits nonexistent wall times rather than moving the drive.
    return checked if checked.replace(tzinfo=None) == naive else None


def occurrences(master: dict[str, Any], start: datetime, end: datetime) -> list[dict[str, Any]]:
    rule = weekly_rule(master["rule"])
    zone = ZoneInfo(master["timezone"])
    first = instant(master["start"]).astimezone(zone)
    finish = instant(master["end"]).astimezone(zone)
    anchor = first.date() - timedelta(days=(first.weekday() - rule.get("week_start", 0)) % 7)
    day = max(first.date(), instant(start).astimezone(zone).date() - timedelta(days=2))
    last = instant(end).astimezone(zone).date()
    if rule["until"]:
        last = min(last, date.fromisoformat(rule["until"]))
    if master.get("cutoff"):
        last = min(last, date.fromisoformat(master["cutoff"]) - timedelta(days=1))
    result = []
    while day <= last:
        if day.weekday() in rule["weekdays"] and (day - anchor).days // 7 % rule["weeks"] == 0:
            left = wall_instant(day, first.timetz(), zone, first.fold)
            right = wall_instant(day + (finish.date() - first.date()), finish.timetz(), zone, finish.fold)
            key = day.isoformat()
            if left is not None and right is not None and instant(start) <= instant(left) < instant(end):
                identity = sha256(f"{master['id']}:{key}".encode()).hexdigest()[:32]
                result.append(
                    {
                        **master["template"],
                        "id": identity,
                        "series": master["id"],
                        "occurrence": key,
                        "start": instant(left).isoformat(),
                        "end": instant(right).isoformat(),
                    }
                )
        day += timedelta(days=1)
    return result
