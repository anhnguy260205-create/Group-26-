"""Daily AI suggestions — small, non-medical nudges tailored to the latest check-in.

Deliberately rule-based and deterministic: these must be safe and sensible even with no
network, and must never read as medical advice. They personalize off the most recent
Check-in's components (sleep, care load, me-time, mood) and always include a gentle
baseline so the list is never empty.
"""

from sqlalchemy.orm import Session

from . import models

BASELINE = [
    "Drink a glass of water.",
    "Step outside for 10 minutes if you can.",
    "Take three slow breaths before the next task.",
]


def _latest_checkin(db: Session) -> models.StressReading | None:
    return (
        db.query(models.StressReading)
        .filter(models.StressReading.source == "checkin")
        .filter(models.StressReading.mood.isnot(None))
        .order_by(models.StressReading.created_at.desc())
        .first()
    )


def daily(db: Session) -> dict:
    """Return {suggestions, based_on_checkin}. Always safe, never empty."""
    reading = _latest_checkin(db)
    tips: list[str] = []

    if reading is not None:
        if reading.hours_slept is not None and reading.hours_slept < 6:
            tips.append("You've been short on sleep — try to wind down and turn in 30 minutes earlier tonight.")
        if not reading.had_me_time:
            tips.append("Protect 10 minutes just for yourself today, even a quiet cup of tea counts.")
        if reading.care_hours is not None and reading.care_hours >= 10:
            tips.append("That's a heavy caregiving load — see if a relative can cover one shift this week.")
        if reading.mood is not None and reading.mood >= 3:
            tips.append("Rough day — be as kind to yourself as you are to the person you care for.")

    # Fill up to three with baseline nudges, no duplicates.
    for b in BASELINE:
        if len(tips) >= 3:
            break
        if b not in tips:
            tips.append(b)

    return {"suggestions": tips[:3], "based_on_checkin": reading is not None}
