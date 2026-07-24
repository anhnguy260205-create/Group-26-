"""The 'AI brain': combines behavioral (task load) and physiological (stress) signals
into a single burnout score, and decides the paced-breathing rhythm during a session.

Kept rule-based by default and reliable offline; an LLM is only used to phrase the
reasoning/reflection text, never to make the intervene/don't-intervene decision itself,
so a flaky network can't cause a missed or spurious intervention mid-demo.
"""

import datetime
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import llm, models

INTERVENE_THRESHOLD = 0.7
RESTING_HEART_RATE_BPM = 70.0
ELEVATED_HEART_RATE_BPM = 110.0


@dataclass
class ThresholdDecision:
    intervene: bool
    combined_score: float
    behavioral_score: float
    physiological_score: float
    reasoning: str
    reasoning_source: str


def behavioral_score(db: Session, now: datetime.datetime | None = None) -> float:
    """0-1 score: how busy/overdue/disorganized the caregiver's task load is right now."""
    now = now or datetime.datetime.utcnow()
    pending = db.query(models.Task).filter(models.Task.done.is_(False)).all()

    if not pending:
        return 0.0

    overdue = sum(1 for t in pending if t.due_at and t.due_at < now)
    due_soon = sum(
        1 for t in pending if t.due_at and now <= t.due_at <= now + datetime.timedelta(hours=1)
    )

    load = min(len(pending) / 8.0, 1.0)  # 8+ open tasks = maxed out
    overdue_pressure = min(overdue / 3.0, 1.0)  # 3+ overdue = maxed out
    urgency = min(due_soon / 3.0, 1.0)

    return round(min(0.5 * overdue_pressure + 0.3 * load + 0.2 * urgency, 1.0), 3)


def physiological_score(reading: models.StressReading | None) -> float:
    """0-1 score derived from the most recent stress reading (rPPG or manual)."""
    if reading is None:
        return 0.0
    return reading.stress_score


def heart_rate_to_stress_score(heart_rate_bpm: float, signal_quality: float | None) -> float:
    span = ELEVATED_HEART_RATE_BPM - RESTING_HEART_RATE_BPM
    raw = (heart_rate_bpm - RESTING_HEART_RATE_BPM) / span
    score = max(0.0, min(raw, 1.0))
    # Low-confidence rPPG readings get pulled toward neutral so noisy frames can't
    # single-handedly trigger an intervention.
    confidence = 1.0 if signal_quality is None else max(0.0, min(signal_quality, 1.0))
    return round(score * confidence + 0.3 * (1 - confidence) * score, 3)


def self_report_to_stress_score(level_1_to_10: int) -> float:
    return round(max(0.0, min((level_1_to_10 - 1) / 9.0, 1.0)), 3)


def checkin_to_stress_score(
    mood: int, hours_slept: float, care_hours: float, had_me_time: bool
) -> float:
    """Combine the Daily Check-in's answers into a 0-1 stress score.
    mood is 1 (good) - 4 (barely holding on)."""
    mood_score = (mood - 1) / 3.0
    sleep_score = max(0.0, min((8.0 - hours_slept) / 8.0, 1.0))  # 8h = no penalty
    care_score = min(care_hours / 12.0, 1.0)  # 12h+/day caregiving = maxed out
    me_time_penalty = 0.0 if had_me_time else 0.15
    return round(
        min(0.35 * mood_score + 0.25 * sleep_score + 0.25 * care_score + me_time_penalty, 1.0), 3
    )


def burnout_risk_level(recent_scores: list[float]) -> Literal["low", "moderate", "high"]:
    """Sustained-pattern risk band from recent daily stress scores — a current-state read,
    not a forecast. Needs several days of data to mean anything; treats a thin history as low
    risk rather than over-calling it from one or two data points."""
    if len(recent_scores) < 3:
        return "low"
    avg = sum(recent_scores) / len(recent_scores)
    if avg >= 0.7:
        return "high"
    if avg >= 0.45:
        return "moderate"
    return "low"


RISK_SUGGESTIONS = {
    "high": [
        "Rest for 30 minutes today, even if the to-do list doesn't shrink.",
        "Ask a relative or friend to cover one caregiving shift this week.",
        "Consider reaching out to a hospital medical social worker for support options.",
    ],
    "moderate": [
        "Try to protect a short block of time for yourself today.",
        "Note what's driving the load this week — it may be worth delegating.",
    ],
    "low": [
        "Things look steady — keep doing what's working.",
    ],
}


def latest_reading(db: Session) -> models.StressReading | None:
    return db.query(models.StressReading).order_by(models.StressReading.created_at.desc()).first()


def recent_stress_trend(db: Session, limit: int = 5) -> list[float]:
    """Oldest-to-newest stress_score of the last `limit` readings, for trend direction."""
    rows = (
        db.query(models.StressReading)
        .order_by(models.StressReading.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r.stress_score for r in reversed(rows)]


def check_threshold(db: Session) -> ThresholdDecision:
    behavioral = behavioral_score(db)
    reading = latest_reading(db)
    physiological = physiological_score(reading)

    combined = round(0.6 * physiological + 0.4 * behavioral, 3)
    intervene = combined >= INTERVENE_THRESHOLD

    reasoning, source = _explain(combined, behavioral, physiological, intervene)
    return ThresholdDecision(intervene, combined, behavioral, physiological, reasoning, source)


def _explain(
    combined: float, behavioral: float, physiological: float, intervene: bool
) -> tuple[str, str]:
    prompt = (
        f"Caregiver burnout monitor. Physiological stress score: {physiological:.2f}/1.0. "
        f"Task-load/behavioral score: {behavioral:.2f}/1.0. Combined: {combined:.2f}/1.0. "
        f"Decision already made: {'intervene now' if intervene else 'no intervention yet'}. "
        "In one short, warm sentence (no more than 25 words), explain why this reading "
        "matters, addressed gently to the caregiver. Do not mention numbers or scores."
    )
    result = llm.complete(
        system="You are a calm, brief clinical-empathy assistant for a caregiver support app.",
        prompt=prompt,
        max_tokens=80,
    )
    if result:
        text, provider = result
        return text, provider

    if intervene:
        return (
            "Your body and your to-do list are both signaling the same thing right now: "
            "it's time for a short pause.",
            "rule",
        )
    return (
        "Things look manageable right now — steady heart rate, steady task load.",
        "rule",
    )


TARGET_RESPIRATION_BPM = 10.0


def breathing_pace(physiological: float, respiration_rate_bpm: float | None = None) -> dict:
    """Slower, more exhale-biased pacing the higher the stress score is.

    If a live respiration reading is available, stretch the exhale further when
    the caregiver is actually breathing faster than the calm target — this is
    the real-time sync with physiological status.
    """
    if physiological >= 0.8:
        inhale, hold, exhale = 4.0, 2.0, 8.0
        guidance = "Let's slow all the way down. In for 4, hold for 2, out for 8."
    elif physiological >= 0.5:
        inhale, hold, exhale = 4.0, 4.0, 6.0
        guidance = "In for 4, hold for 4, out for 6."
    else:
        inhale, hold, exhale = 4.0, 4.0, 4.0
        guidance = "Nice and steady — in for 4, hold for 4, out for 4."

    if respiration_rate_bpm is not None and respiration_rate_bpm > TARGET_RESPIRATION_BPM:
        # Breathing faster than calm target -> stretch exhale proportionally, capped.
        excess = respiration_rate_bpm - TARGET_RESPIRATION_BPM
        stretch = min(1.0 + excess * 0.1, 1.5)  # cap at +50% exhale
        exhale = round(exhale * stretch, 1)
        guidance = f"You're at {respiration_rate_bpm:.0f} breaths a minute — let's stretch that exhale out."

    return {
        "inhale_seconds": inhale,
        "hold_seconds": hold,
        "exhale_seconds": exhale,
        "guidance": guidance,
    }


def generate_breathing_guidance(
    physiological: float,
    respiration_rate: float,
    stress_trend: list[float],
) -> str | None:
    """AI-personalized breathing cue. Returns None if LLM unavailable — caller must
    fall back to the rule-based `guidance` string from breathing_pace() in that case.
    """
    trend = "improving" if len(stress_trend) > 1 and stress_trend[-1] < stress_trend[0] else "elevated"

    prompt = (
        f"Caregiver breathing at {respiration_rate:.1f} breaths/min (target 10). "
        f"Stress trend: {trend}. Stress level: {physiological:.2f}/1.0. "
        "In one caring, short sentence, give ONE breathing instruction. "
        "e.g., 'Exhale for a count of 6' or 'Let's slow down together'."
    )
    result = llm.complete(
        system="You are a calm respiratory therapist for burnout prevention.",
        prompt=prompt,
        max_tokens=30,
    )
    return result[0] if result else None