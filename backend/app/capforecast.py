"""Capacity forecasting -- the "predict, don't summarise" read on Capacity check-ins.

Burnout is cumulative, so a Capacity line that falls a little every day for a week is the real
warning sign. This module turns recent check-ins into:

  * a daily series
  * a multi-day projection (not just tomorrow), so the user sees where they are heading
  * the specific day they are projected to cross the low-capacity line
  * a recurring weekday pattern ("your Wednesdays are consistently your hardest day")
  * a declining-streak count, a recurring driver, and a risk band

Every number here is produced by deterministic code. The LLM is only ever asked to phrase the
forecast in warm language -- it cannot change a score, a projection, a risk band or a date. That
split is deliberate: it keeps the forecast reproducible and explainable, and it means the whole
feature still works with the network unplugged (the rule text is a real fallback, not a stub).

Not a clinical prediction.
"""

import datetime
import json
import re
from collections import Counter, defaultdict

from . import llm, models, scoring

WINDOW_DAYS = 14

# --- Projection ---------------------------------------------------------------
PROJECTION_DAYS = 3
# Days of history the slope is fitted over. Four is a compromise: long enough that one odd
# day doesn't dominate, short enough that it tracks a week that is actively falling apart.
SLOPE_WINDOW = 4
# Momentum fades. Without damping a straight-line extrapolation reaches 0 within a fortnight,
# which is both alarmist and obviously wrong to anyone looking at it.
DAMPING = 0.85
# Below this, capacity is "running low" -- the line whose crossing we warn about. Chosen to sit
# just under the moderate-risk band (60) so the warning arrives before the state does.
LOW_CAPACITY_LINE = 55

# --- Weekday pattern ----------------------------------------------------------
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# One bad Wednesday is a bad Wednesday. Two is the start of a pattern worth naming.
PATTERN_MIN_SAMPLES = 2
PATTERN_MIN_DAYS = 7
# A weekday has to sit this far under the overall average before we'll call it a pattern.
PATTERN_MIN_DROP = 6


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


def _slope(series: list[dict]) -> float:
    """Least-squares slope (capacity points per day) over the last SLOPE_WINDOW days.

    Least squares rather than last-minus-first: a single unusually good or bad day at either
    end of the window shouldn't set the whole forecast.
    """
    recent = series[-SLOPE_WINDOW:]
    n = len(recent)
    if n < 2:
        return 0.0
    xs = list(range(n))
    ys = [p["capacity"] for p in recent]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    sxx = sum((x - mean_x) ** 2 for x in xs)
    return sxy / sxx if sxx else 0.0


def _project(series: list[dict], days: int = PROJECTION_DAYS) -> list[dict]:
    """Damped straight-line projection for the next `days` days.

    Each step carries less of the slope than the one before, so the line bends toward flat
    instead of running off the bottom of the chart.
    """
    if not series:
        return []
    slope = _slope(series)
    last_date = series[-1]["date"]
    value = float(series[-1]["capacity"])
    out = []
    for step in range(1, days + 1):
        value += slope * (DAMPING ** (step - 1))
        capacity = max(0, min(int(value + 0.5), 100))
        date = last_date + datetime.timedelta(days=step)
        out.append({"date": date, "capacity": capacity, "weekday": WEEKDAY_NAMES[date.weekday()]})
    return out


def _risk_day(projection: list[dict]) -> dict | None:
    """First projected day at or below the low-capacity line, if any."""
    for point in projection:
        if point["capacity"] <= LOW_CAPACITY_LINE:
            return point
    return None


def _weekday_pattern(series: list[dict]) -> dict | None:
    """The weekday that is reliably worse than the rest, if there is one.

    Requires a full week of data, at least two observations of that weekday, and a drop
    meaningful enough that we're not narrating noise.
    """
    if len(series) < PATTERN_MIN_DAYS:
        return None
    by_weekday = defaultdict(list)
    for point in series:
        by_weekday[point["date"].weekday()].append(point["capacity"])

    eligible = {wd: caps for wd, caps in by_weekday.items() if len(caps) >= PATTERN_MIN_SAMPLES}
    if not eligible:
        return None

    averages = {wd: sum(caps) / len(caps) for wd, caps in eligible.items()}
    worst = min(averages, key=averages.get)
    overall = sum(p["capacity"] for p in series) / len(series)
    drop = overall - averages[worst]
    if drop < PATTERN_MIN_DROP:
        return None

    drivers = [p["driver"] for p in series if p["date"].weekday() == worst]
    return {
        "weekday": WEEKDAY_NAMES[worst],
        "avg_capacity": round(averages[worst]),
        "overall_avg": round(overall),
        "drop": round(drop),
        "samples": len(eligible[worst]),
        "driver": Counter(drivers).most_common(1)[0][0] if drivers else None,
        "note": (
            f"Your {WEEKDAY_NAMES[worst]}s are consistently your hardest day -- "
            f"about {round(drop)} points below your usual. Is there something about that day "
            "in particular, like a shift or an appointment?"
        ),
    }


def _risk(series: list[dict], decline_days: int, projection: list[dict], risk_day: dict | None) -> str:
    if not series:
        return "low"
    recent = [s["capacity"] for s in series[-3:]]
    avg = sum(recent) / len(recent)
    projected = projection[-1]["capacity"] if projection else None
    # A projection that crosses the low line while capacity is already falling is the
    # signal this whole feature exists to catch -- treat it as high even if today looks fine.
    if avg < 40 or (decline_days >= 2 and risk_day is not None):
        return "high"
    if decline_days >= 3 and projected is not None and projected < 50:
        return "high"
    if avg < 60 or decline_days >= 2:
        return "moderate"
    return "low"


def _rule_forecast(series, risk, decline_days, driver, projection, risk_day, pattern) -> str:
    """Offline phrasing. Deliberately covers the same ground as the LLM version so that a
    demo with no network tells the same story, just less warmly."""
    if not series:
        return "Not enough check-ins yet to spot a pattern -- a few days in a row will unlock this."

    parts = []
    driver_bit = f" The thread running through it is {driver.lower()}." if driver else ""

    if risk_day is not None:
        streak = f"{decline_days} days running" if decline_days >= 2 else "over the last few days"
        parts.append(
            f"Your capacity has been sliding {streak}, and if it keeps going the way it has been, "
            f"{risk_day['weekday']} is where it runs low.{driver_bit} That's the day worth "
            "protecting now, while you still have room to move something."
        )
    elif risk == "high":
        parts.append(
            f"Your capacity has been dropping for {decline_days} days.{driver_bit} This is the "
            "point where handing off one task or claiming one evening changes the week."
        )
    elif risk == "moderate":
        parts.append(
            f"Your capacity is dipping.{driver_bit} It's not a crisis, but this is the point "
            "where a small change today keeps it from becoming one this week."
        )
    else:
        parts.append(
            f"Your capacity is holding.{driver_bit} Keep doing what's working -- and keep "
            "checking in so any drift shows up early."
        )

    if pattern:
        parts.append(pattern["note"])
    return " ".join(parts)


SYSTEM_PROMPT = (
    "You write the forecast text for a caregiver's burnout-prevention app. You are not a "
    "clinician and never diagnose. Burnout is cumulative, so a multi-day decline matters far more "
    "than one low day.\n\n"
    "The app has ALREADY computed every number: the projection, the risk band, and the day capacity "
    "is expected to run low. Do not recalculate, contradict or second-guess them. Your only job is "
    "wording.\n\n"
    'Return ONLY a JSON object: {"forecast": "<two to four warm sentences>"}. In it: name the '
    "pattern you were given, say which day is projected to be hard (use the weekday name given -- "
    "never invent a different one), and give ONE concrete thing they could do now. If a recurring "
    "weekday pattern is provided, mention it and ask an open question about it. Write in plain, "
    "second-person language. Never state numbers or scores -- describe them in words instead."
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
            "points": [], "projection": [], "days_of_data": 0, "avg_capacity": None, "trend": "steady",
            "consecutive_decline_days": 0, "recurring_driver": None, "predicted_capacity": None,
            "risk_day": None, "risk_day_weekday": None, "risk_day_capacity": None,
            "weekday_pattern": None, "weekday_pattern_note": None, "weekday_pattern_drop": None,
            "low_capacity_line": LOW_CAPACITY_LINE, "risk": "low",
            "forecast": "No check-ins yet -- do a Daily Check-in for a few days and your trend and forecast appear here.",
            "suggestions": scoring.RISK_SUGGESTIONS["low"], "source": "rule",
        }

    decline_days = _consecutive_decline(series)
    trend = _trend(series)
    projection = _project(series)
    risk_day = _risk_day(projection)
    pattern = _weekday_pattern(series)
    risk = _risk(series, decline_days, projection, risk_day)
    recurring_driver = Counter(s["driver"] for s in series).most_common(1)[0][0]
    avg_capacity = round(sum(s["capacity"] for s in series) / len(series))
    # Kept for the existing single-number readout; it's simply the first projected day.
    predicted = projection[0]["capacity"] if projection else None
    forecast = _rule_forecast(series, risk, decline_days, recurring_driver, projection, risk_day, pattern)
    source = "rule"

    if len(series) >= 3:
        series_text = "\n".join(
            f"- {s['date'].isoformat()}: capacity {s['capacity']}, main driver {s['driver']}" for s in series
        )
        projection_text = ", ".join(f"{p['weekday']} {p['capacity']}" for p in projection)
        risk_day_text = (
            f"Projected to run low on {risk_day['weekday']} ({risk_day['date'].isoformat()})."
            if risk_day
            else "Not projected to run low within the forecast window."
        )
        pattern_text = (
            f"Recurring weekday pattern: {pattern['weekday']}s average {pattern['drop']} points below "
            f"their overall average, seen {pattern['samples']} times."
            if pattern
            else "No recurring weekday pattern detected."
        )
        prompt = (
            f"Daily Capacity series, 0-100, higher is better (oldest first):\n{series_text}\n\n"
            f"Consecutive declining days: {decline_days}. Recurring driver: {recurring_driver}.\n"
            f"Computed projection for the next {PROJECTION_DAYS} days: {projection_text}.\n"
            f"{risk_day_text}\n{pattern_text}\nComputed risk band: {risk}."
        )
        # Deep tier: this is the reasoning-heavy call, so it gets the larger model.
        result = llm.complete(system=SYSTEM_PROMPT, prompt=prompt, max_tokens=600, tier="deep")
        if result:
            text, provider = result
            parsed = _extract_json(text)
            if parsed:
                # Only the wording is taken from the model. Numbers, risk band and dates stay
                # exactly as computed above -- see the module docstring.
                phrased = str(parsed.get("forecast") or "").strip()
                if phrased:
                    forecast = phrased
                    source = provider

    return {
        "points": points,
        "projection": [
            {"date": p["date"].isoformat(), "capacity": p["capacity"], "weekday": p["weekday"]}
            for p in projection
        ],
        "days_of_data": len(series), "avg_capacity": avg_capacity, "trend": trend,
        "consecutive_decline_days": decline_days, "recurring_driver": recurring_driver,
        "predicted_capacity": predicted,
        "risk_day": risk_day["date"].isoformat() if risk_day else None,
        "risk_day_weekday": risk_day["weekday"] if risk_day else None,
        "risk_day_capacity": risk_day["capacity"] if risk_day else None,
        "weekday_pattern": pattern["weekday"] if pattern else None,
        "weekday_pattern_note": pattern["note"] if pattern else None,
        "weekday_pattern_drop": pattern["drop"] if pattern else None,
        "low_capacity_line": LOW_CAPACITY_LINE,
        "risk": risk, "forecast": forecast,
        "suggestions": scoring.RISK_SUGGESTIONS[risk], "source": source,
    }
