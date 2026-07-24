"""Capacity forecasting.

Burnout is cumulative, not a single bad day — a Capacity line that falls a little every
day for a week is the real warning sign. This module turns the recent run of Daily
Check-ins into: a daily Capacity series, how many days it's been declining in a row, the
recurring main driver, a naive projection of tomorrow, and a risk band. An LLM phrases the
short forecast when reachable; a transparent rule model is the fallback so the page always
says something grounded and never depends on the network.

Explicitly NOT a clinical prediction — it's a "here's the pattern, here's what tends to
come next" nudge so the caregiver can act *before* they hit the wall.
"""

import json
import re
from collections import Counter

from . import llm, models, scoring

WINDOW_DAYS = 14


def _daily_series(checkins: list[models.Checkin]) -> list[dict]:
    """checkins oldest-first -> one point per day: average Capacity + that day's dominant driver."""
    buckets: dict = {}
    for c in checkins:
        buckets.setdefault(c.created_at.date(), []).append(c)
    series = []
    for day in sorted(buckets):
        items = buckets[day]
        caps = [x.capacity_score for x in items]
        drivers = [x.main_driver for x in items]
        series.append(
            {
                "date": day,
                "capacity": round(sum(caps) / len(caps)),
                "driver": Counter(drivers).most_common(1)[0][0],
            }
        )
    return series


def _consecutive_decline(series: list[dict]) -> int:
    """Trailing run of days where Capacity dropped versus the day before."""
    n = 0
    for i in range(len(series) - 1, 0, -1):
        if series[i]["capacity"] < series[i - 1]["capacity"]:
            n += 1
        else:
            break
    return n


def _trend(series: list[dict]) -> str:
    if len(series) < 2:
        return "steady"
    delta = series[-1]["capacity"] - series[0]["capacity"]
    if delta <= -8:
        return "declining"
    if delta >= 8:
        return "improving"
    return "steady"


def _predict(series: list[dict]) -> int | None:
    """Project tomorrow's Capacity from the slope of the last few days."""
    if not series:
        return None
    if len(series) == 1:
        return series[-1]["capacity"]
    recent = series[-4:]
    slope = (recent[-1]["capacity"] - recent[0]["capacity"]) / (len(recent) - 1)
    return max(0, min(round(series[-1]["capacity"] + slope), 100))


def _risk(series: list[dict], decline_days: int, predicted: int | None) -> str:
    if not series:
        return "low"
    recent = [s["capacity"] for s in series[-3:]]
    avg = sum(recent) / len(recent)
    if avg < 40 or (decline_days >= 3 and (predicted is None or predicted < 50)):
        return "high"
    if avg < 60 or decline_days >= 2:
        return "moderate"
    return "low"


def _rule_forecast(
    series: list[dict], risk: str, decline_days: int, recurring_driver: str | None
) -> str:
    if not series:
        return "Not enough check-ins yet to spot a pattern — a few days in a row will unlock this."
    driver_bit = f" The thread running through it is {recurring_driver.lower()}." if recurring_driver else ""
    if risk == "high":
        streak = f"{decline_days} days running" if decline_days >= 2 else "recently"
        return (
            f"Your capacity has been sliding {streak}.{driver_bit} If the pattern holds, "
            "tomorrow is a high-strain day — worth protecting some rest or handing off a task now, "
            "before it tips over."
        )
    if risk == "moderate":
        return (
            f"Your capacity is dipping.{driver_bit} It's not a crisis, but this is the point where "
            "a small change today keeps it from becoming one this week."
        )
    return (
        f"Your capacity is holding.{driver_bit} Keep doing what's working — and keep checking in so "
        "any drift shows up early."
    )


SYSTEM_PROMPT = (
    "You read a family caregiver's recent daily Capacity scores (0-100, higher = more in the tank) "
    "and gently forecast the near term for a support app. You are not a clinician and never "
    "diagnose. Burnout is cumulative, so a multi-day decline matters more than one low day. "
    "Return ONLY a JSON object, no other text, in exactly this shape: "
    '{"predicted_capacity": <0-100 int>, "risk": "<low|moderate|high>", '
    '"forecast": "<two or three warm, plain sentences: name the pattern, say what tends to come '
    'next, and suggest one concrete action to take *now*. No numbers.>"}. '
    "Ground it in the actual series and the recurring driver you are given."
)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None


def analyze(checkins: list[models.Checkin]) -> dict:
    """checkins oldest-first. Always returns a complete dict; never raises."""
    series = _daily_series(checkins)
    points = [
        {"date": s["date"].isoformat(), "capacity": s["capacity"], "driver": s["driver"]}
        for s in series
    ]

    if not series:
        return {
            "points": [],
            "days_of_data": 0,
            "avg_capacity": None,
            "trend": "steady",
            "consecutive_decline_days": 0,
            "recurring_driver": None,
            "predicted_capacity": None,
            "risk": "low",
            "forecast": "No check-ins yet — do a Daily Check-in for a few days and your trend and "
            "forecast appear here.",
            "suggestions": scoring.RISK_SUGGESTIONS["low"],
            "source": "rule",
        }

    decline_days = _consecutive_decline(series)
    trend = _trend(series)
    predicted = _predict(series)
    risk = _risk(series, decline_days, predicted)
    recurring_driver = Counter(s["driver"] for s in series).most_common(1)[0][0]
    avg_capacity = round(sum(s["capacity"] for s in series) / len(series))

    forecast = _rule_forecast(series, risk, decline_days, recurring_driver)
    source = "rule"

    # Only ask the LLM once there's enough of a run to forecast anything meaningful.
    if len(series) >= 3:
        series_text = "\n".join(
            f"- {s['date'].isoformat()}: capacity {s['capacity']}, main driver {s['driver']}"
            for s in series
        )
        prompt = (
            f"Daily Capacity series (oldest first):\n{series_text}\n\n"
            f"Consecutive declining days: {decline_days}. Recurring main driver: {recurring_driver}. "
            f"Naive projection for tomorrow: {predicted}. Computed risk: {risk}."
        )
        result = llm.complete(system=SYSTEM_PROMPT, prompt=prompt, max_tokens=600)
        if result:
            text, provider = result
            parsed = _extract_json(text)
            if parsed:
                try:
                    predicted = max(0, min(int(round(float(parsed.get("predicted_capacity", predicted)))), 100))
                except (TypeError, ValueError):
                    pass
                r = str(parsed.get("risk", "")).strip().lower()
                if r in ("low", "moderate", "high"):
                    risk = r
                forecast = str(parsed.get("forecast") or "").strip() or forecast
                source = provider

    return {
        "points": points,
        "days_of_data": len(series),
        "avg_capacity": avg_capacity,
        "trend": trend,
        "consecutive_decline_days": decline_days,
        "recurring_driver": recurring_driver,
        "predicted_capacity": predicted,
        "risk": risk,
        "forecast": forecast,
        "suggestions": scoring.RISK_SUGGESTIONS[risk],
        "source": source,
    }
