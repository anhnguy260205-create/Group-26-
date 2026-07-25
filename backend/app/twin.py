"""Caregiver Digital Twin — the headline "predict & prevent" feature.

From the last several days of daily stress scores (and the Check-in components behind
them), forecast the next few days' stress trend and name the *driver* — so the app can
nudge the caregiver to rest or hand off a shift *before* risk peaks, not after.

Design mirrors the rest of the backend: the forecast math is deterministic and works
fully offline; an LLM is only used to *phrase* the narration, with a templated fallback.
Nothing here diagnoses or treats — it is a support-and-signposting signal.
"""

import datetime

from sqlalchemy.orm import Session

from . import llm, models

HISTORY_DAYS = 14
MIN_DAYS_TO_FORECAST = 3
RISING_SLOPE = 0.02   # per-day change in 0-1 stress that counts as a real trend
FALLING_SLOPE = -0.02

DRIVER_LABELS = {
    "sleep": "short sleep",
    "care": "long caregiving hours",
    "me_time": "no time for yourself",
    "mood": "low mood",
}


def _daily_avg_stress(readings: list[models.StressReading]) -> list[tuple[datetime.date, float]]:
    """Oldest-first (date, avg stress 0-1) — one point per day that has readings."""
    buckets: dict[datetime.date, list[float]] = {}
    for r in readings:
        buckets.setdefault(r.created_at.date(), []).append(r.stress_score)
    return [(day, sum(v) / len(v)) for day, v in sorted(buckets.items())]


def _linear_fit(ys: list[float]) -> tuple[float, float, float]:
    """Least-squares fit over x = 0..n-1. Returns (slope, intercept, residual_std)."""
    n = len(ys)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs) or 1.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    intercept = mean_y - slope * mean_x
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    resid_std = (sum(r * r for r in residuals) / n) ** 0.5
    return slope, intercept, resid_std


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _detect_driver(db: Session, days: int = 5) -> str | None:
    """Which Check-in factor is contributing most to recent stress. None if no check-ins."""
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    rows = (
        db.query(models.StressReading)
        .filter(models.StressReading.source == "checkin")
        .filter(models.StressReading.created_at >= since)
        .filter(models.StressReading.mood.isnot(None))
        .all()
    )
    if not rows:
        return None

    n = len(rows)
    sleep = sum(max(0.0, (8.0 - (r.hours_slept or 8.0)) / 8.0) for r in rows) / n
    care = sum(min((r.care_hours or 0.0) / 12.0, 1.0) for r in rows) / n
    me_time = sum(0.0 if r.had_me_time else 1.0 for r in rows) / n
    mood = sum(((r.mood or 1) - 1) / 3.0 for r in rows) / n

    factors = {"sleep": sleep, "care": care, "me_time": me_time, "mood": mood}
    key = max(factors, key=factors.get)
    # If everything's low, there's no meaningful driver to call out.
    if factors[key] < 0.25:
        return None
    return key


def _narrate(trend: str, driver_key: str | None, current: float, projected: float) -> tuple[str, str]:
    """(text, source). LLM-phrased when available, deterministic template otherwise."""
    driver_phrase = DRIVER_LABELS.get(driver_key or "", "")
    direction = {"rising": "rising", "falling": "easing", "steady": "holding steady"}[trend]

    prompt = (
        f"A caregiver's stress has been {direction} over the last two weeks"
        + (f", mainly driven by {driver_phrase}" if driver_phrase else "")
        + f". Today's stress is about {round(current * 100)}/100 and the next couple of days "
        f"are forecast around {round(projected * 100)}/100. "
        "In ONE warm, plain sentence (max 30 words), tell them what the trend looks like and "
        "suggest ONE concrete, non-medical action to get ahead of it (e.g. hand off a night, "
        "protect 30 minutes, ask a relative). Do not mention numbers or scores."
    )
    result = llm.complete(
        system=(
            "You are a caring, brief companion for caregivers. You forecast stress to "
            "help them act early. You never diagnose or give medical advice."
        ),
        prompt=prompt,
        max_tokens=80,
    )
    if result:
        return result[0], result[1]

    # Deterministic fallback.
    if trend == "rising":
        tail = f", mainly from {driver_phrase}" if driver_phrase else ""
        return (
            f"Your stress has been climbing{tail}, and the next couple of days look heavy — "
            "consider handing off one shift or protecting a short break before it peaks.",
            "template",
        )
    if trend == "falling":
        return (
            "Your stress has been easing over the past couple of weeks — keep protecting "
            "whatever's been working for you.",
            "template",
        )
    return (
        "Your stress has been holding steady. A small rest today keeps it from creeping up.",
        "template",
    )


def forecast_stress(db: Session, horizon_days: int = 3) -> dict:
    """Forecast the next `horizon_days` of daily stress from recent history.

    Returns a dict matching schemas.StressForecast. Never raises; degrades gracefully
    when there isn't enough history to forecast on.
    """
    since = datetime.datetime.utcnow() - datetime.timedelta(days=HISTORY_DAYS)
    readings = (
        db.query(models.StressReading)
        .filter(models.StressReading.created_at >= since)
        .order_by(models.StressReading.created_at)
        .all()
    )
    daily = _daily_avg_stress(readings)
    days_of_history = len(daily)

    if days_of_history < MIN_DAYS_TO_FORECAST:
        return {
            "horizon_days": horizon_days,
            "days_of_history": days_of_history,
            "trend": "steady",
            "points": [],
            "main_driver": None,
            "narrative": (
                "Not enough history yet to forecast — check in daily and the twin will start "
                "predicting after about 3 days."
            ),
            "narrative_source": "template",
        }

    ys = [v for _, v in daily]
    slope, intercept, resid_std = _linear_fit(ys)
    n = len(ys)
    current = _clamp01(intercept + slope * (n - 1))

    if slope >= RISING_SLOPE:
        trend = "rising"
    elif slope <= FALLING_SLOPE:
        trend = "falling"
    else:
        trend = "steady"

    band = max(0.05, 1.96 * resid_std)
    last_date = daily[-1][0]
    points = []
    for i in range(1, horizon_days + 1):
        predicted = _clamp01(intercept + slope * (n - 1 + i))
        points.append(
            {
                "date": last_date + datetime.timedelta(days=i),
                "predicted_score": round(predicted, 3),
                "predicted_display": round(predicted * 100),
                "lower": round(_clamp01(predicted - band), 3),
                "upper": round(_clamp01(predicted + band), 3),
            }
        )

    driver = _detect_driver(db)
    projected = points[-1]["predicted_score"]
    narrative, source = _narrate(trend, driver, current, projected)

    return {
        "horizon_days": horizon_days,
        "days_of_history": days_of_history,
        "trend": trend,
        "points": points,
        "main_driver": DRIVER_LABELS.get(driver) if driver else None,
        "narrative": narrative,
        "narrative_source": source,
    }
