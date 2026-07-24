"""AI Weekly Summary — a cross-metric read of the last 7 days.

Compares the first half of the week to the second half for sleep, stress and mood, names
the likely driver, and phrases it warmly (LLM when reachable, template otherwise).
Example: "Over the past 7 days: Sleep down, Stress up, Mood down — mainly longer
night-time caregiving." Not a diagnosis.
"""

import datetime

from sqlalchemy.orm import Session

from . import llm, models, twin

WINDOW_DAYS = 7


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _trend(first: float | None, second: float | None, flat_eps: float) -> str:
    if first is None or second is None:
        return "flat"
    delta = second - first
    if delta > flat_eps:
        return "up"
    if delta < -flat_eps:
        return "down"
    return "flat"


def generate(db: Session) -> dict:
    """Return a dict matching schemas.WeeklySummary. Never raises."""
    since = datetime.datetime.utcnow() - datetime.timedelta(days=WINDOW_DAYS)
    checkins = (
        db.query(models.StressReading)
        .filter(models.StressReading.source == "checkin")
        .filter(models.StressReading.created_at >= since)
        .filter(models.StressReading.mood.isnot(None))
        .order_by(models.StressReading.created_at)
        .all()
    )
    days_of_data = len({r.created_at.date() for r in checkins})

    if len(checkins) < 2:
        return {
            "summary": (
                "Not enough check-ins this week for a summary yet — a minute a day builds the "
                "picture, and you'll see your first weekly read soon."
            ),
            "source": "template",
            "days_of_data": days_of_data,
            "sleep_trend": "flat",
            "stress_trend": "flat",
            "mood_trend": "flat",
            "main_driver": None,
        }

    mid = len(checkins) // 2
    first, second = checkins[:mid] or checkins[:1], checkins[mid:]

    sleep_trend = _trend(
        _avg([r.hours_slept for r in first if r.hours_slept is not None]),
        _avg([r.hours_slept for r in second if r.hours_slept is not None]),
        flat_eps=0.5,
    )
    stress_trend = _trend(
        _avg([r.stress_score for r in first]),
        _avg([r.stress_score for r in second]),
        flat_eps=0.05,
    )
    # Wellbeing scale: mood is 1 (good) .. 4 (barely holding on), so invert to "feeling better".
    mood_trend = _trend(
        _avg([4 - r.mood for r in first if r.mood is not None]),
        _avg([4 - r.mood for r in second if r.mood is not None]),
        flat_eps=0.3,
    )

    driver_key = twin._detect_driver(db, days=WINDOW_DAYS)
    main_driver = twin.DRIVER_LABELS.get(driver_key) if driver_key else None

    def word(metric: str, t: str) -> str:
        return {"up": f"{metric} up", "down": f"{metric} down", "flat": f"{metric} steady"}[t]

    facts = f"{word('Sleep', sleep_trend)}, {word('Stress', stress_trend)}, {word('Mood', mood_trend)}"
    prompt = (
        f"Over a caregiver's past week: {facts}"
        + (f". The main driver appears to be {main_driver}" if main_driver else "")
        + ". In one or two warm, plain sentences, summarize how their week went and gently point "
        "at what to watch. No numbers, no diagnosis."
    )
    result = llm.complete(
        system=(
            "You write a short, caring weekly reflection for a family caregiver. You never "
            "diagnose or give medical advice."
        ),
        prompt=prompt,
        max_tokens=110,
    )
    if result:
        summary, source = result[0], result[1]
    else:
        tail = f" — the main driver appears to be {main_driver}." if main_driver else "."
        summary = f"Over the past 7 days: {facts}{tail} Worth protecting a little rest this week."
        source = "template"

    return {
        "summary": summary,
        "source": source,
        "days_of_data": days_of_data,
        "sleep_trend": sleep_trend,
        "stress_trend": stress_trend,
        "mood_trend": mood_trend,
        "main_driver": main_driver,
    }
