"""Capacity forecasting — the "predict & prevent" read on Capacity check-ins.

Burnout is cumulative, so a Capacity line that falls a little every day for a week is the
real warning sign. Turns recent check-ins into a daily series, a declining-streak count, a
recurring driver, a tomorrow projection, and a risk band. LLM phrases the forecast when
reachable; a rule model is the fallback. Not a clinical prediction.
"""

import json
import re
from collections import Counter

from . import llm, models, scoring

WINDOW_DAYS = 14


def _daily_series(checkins: list[models.Checkin]) -> list[dict]:
    buckets: dict = {}
    for c in checkins:
        buckets.setdefault(c.created_at.date(), []).append(c)
    series = []
    for day in sorted(buckets):
        items = buckets[day]
        caps = [x.capacity_score for x in items]
        drivers = [x.main_driver for x in items]
        series.append(
            {"date": day, "capacity": round(sum(caps) / len(caps)), "driver": Counter(drivers).most_common(1)[0][0]}
        )
    return series


def _consecutive_decline(series: list[dict]) -> int:
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


def _rule_forecast(series, risk, decline_days, driver) -> str:
    if not series:
        return "Not enough check-ins yet to spot a pattern — a few days in a row will unlock this."
    driver_bit = f" The thread running through it is {driver.lower()}." if driver else ""
    if risk == "high":
        streak = f"{decline_days} days running" if decline_days >= 2 else "recently"
        return (
            f"Your capacity has been sliding {streak}.{driver_bit} If the pattern holds, tomorrow "
            "is a high-strain day — worth protecting some rest or handing off a task now, before it tips over."
        )
    if risk == "moderate":
        return (
            f"Your capacity is dipping.{driver_bit} It's not a crisis, but this is the point where a "
            "small change today keeps it from becoming one this week."
        )
    return (
        f"Your capacity is holding.{driver_bit} Keep doing what's working — and keep checking in so any "
        "drift shows up early."
    )


SYSTEM_PROMPT = (
    "You read a family caregiver's recent daily Capacity scores (0-100, higher = more in the tank) "
    "and gently forecast the near term. Not a clinician, never diagnose. Burnout is cumulative, so a "
    "multi-day decline matters more than one low day. Return ONLY a JSON object: "
    '{"predicted_capacity": <0-100 int>, "risk": "<low|moderate|high>", '
    '"forecast": "<two or three warm sentences: name the pattern, what tends to come next, one concrete '
    'action to take now. No numbers.>"}. Ground it in the series and recurring driver given.'
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
    series = _daily_series(checkins)
    points = [{"date": s["date"].isoformat(), "capacity": s["capacity"], "driver": s["driver"]} for s in series]

    if not series:
        return {
            "points": [], "days_of_data": 0, "avg_capacity": None, "trend": "steady",
            "consecutive_decline_days": 0, "recurring_driver": None, "predicted_capacity": None,
            "risk": "low",
            "forecast": "No check-ins yet — do a Daily Check-in for a few days and your trend and forecast appear here.",
            "suggestions": scoring.RISK_SUGGESTIONS["low"], "source": "rule",
        }

    decline_days = _consecutive_decline(series)
    trend = _trend(series)
    predicted = _predict(series)
    risk = _risk(series, decline_days, predicted)
    recurring_driver = Counter(s["driver"] for s in series).most_common(1)[0][0]
    avg_capacity = round(sum(s["capacity"] for s in series) / len(series))
    forecast = _rule_forecast(series, risk, decline_days, recurring_driver)
    source = "rule"

    if len(series) >= 3:
        series_text = "\n".join(
            f"- {s['date'].isoformat()}: capacity {s['capacity']}, main driver {s['driver']}" for s in series
        )
        prompt = (
            f"Daily Capacity series (oldest first):\n{series_text}\n\n"
            f"Consecutive declining days: {decline_days}. Recurring driver: {recurring_driver}. "
            f"Naive projection tomorrow: {predicted}. Computed risk: {risk}."
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
        "points": points, "days_of_data": len(series), "avg_capacity": avg_capacity, "trend": trend,
        "consecutive_decline_days": decline_days, "recurring_driver": recurring_driver,
        "predicted_capacity": predicted, "risk": risk, "forecast": forecast,
        "suggestions": scoring.RISK_SUGGESTIONS[risk], "source": source,
    }
