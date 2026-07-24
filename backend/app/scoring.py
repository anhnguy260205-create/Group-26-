"""The 'AI brain': combines behavioral (task load) and physiological (stress) signals
into a single burnout score, and decides the paced-breathing rhythm during a session.

Kept rule-based by default and reliable offline; an LLM is only used to phrase the
reasoning/reflection text, never to make the intervene/don't-intervene decision itself,
so a flaky network can't cause a missed or spurious intervention mid-demo.
"""

import datetime
import json
import re
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


# ---------------------------------------------------------------------------
# Daily Check-in -> Capacity score
#
# Capacity = how much the caregiver has left in the tank right now (0-100, higher
# is better). Five self-report sliders, each 0-10:
#   mood        0 = terrible      10 = great
#   sleep       0 = no rest       10 = fully rested
#   energy      0 = depleted      10 = energized
#   night_care  0 = none          10 = heavy nighttime caregiving   (a BURDEN -> lowers capacity)
#   free_time   0 = none          10 = plenty of time to myself
#
# An LLM reads the journal + sliders and returns capacity + the single main driver
# + a warm reason. If no LLM is reachable, a transparent rule-based model produces
# the same three fields so Check-in never shows nothing.
# ---------------------------------------------------------------------------

# Weights sum to 1.0. night_care is a burden, so it's scored on its "relief" (10 - value).
CAPACITY_WEIGHTS = {
    "mood": 0.25,
    "energy": 0.25,
    "sleep": 0.20,
    "night_care": 0.15,
    "free_time": 0.15,
}

# When a fresh facial-expression reading is available, it's fused in as a sixth factor
# with this weight; the five self-report weights are scaled down proportionally so the
# effective weights still sum to 1.0. No face reading -> five-factor model, unchanged.
FACE_WEIGHT = 0.20

# How recent a facial-expression reading must be to count at check-in time.
FACE_FRESH_SECONDS = 600

# Human-readable labels for the "main driver" field.
CAPACITY_LABELS = {
    "mood": "Mood",
    "energy": "Energy",
    "sleep": "Sleep",
    "night_care": "Night Care",
    "free_time": "Free Time",
    "face": "Facial Signs",
}


def _effective_weights(has_face: bool) -> dict[str, float]:
    if not has_face:
        return dict(CAPACITY_WEIGHTS)
    scale = 1.0 - FACE_WEIGHT
    weights = {k: v * scale for k, v in CAPACITY_WEIGHTS.items()}
    weights["face"] = FACE_WEIGHT
    return weights


def _capacity_contributions(
    mood: int, sleep: int, energy: int, night_care: int, free_time: int
) -> dict[str, float]:
    """Each factor's 0-10 'goodness' (night_care inverted, since more = heavier)."""
    return {
        "mood": float(mood),
        "energy": float(energy),
        "sleep": float(sleep),
        "night_care": float(10 - night_care),  # relief from nighttime caregiving
        "free_time": float(free_time),
    }


def compute_capacity_rule(
    mood: int,
    sleep: int,
    energy: int,
    night_care: int,
    free_time: int,
    face_stress: float | None = None,
) -> tuple[int, str, str]:
    """Transparent, offline fallback. Returns (capacity 0-100, main_driver_key, reason).
    If face_stress (0-1) is given, a calm face reads as high 'goodness' and is fused in."""
    goodness = _capacity_contributions(mood, sleep, energy, night_care, free_time)
    if face_stress is not None:
        goodness["face"] = (1.0 - face_stress) * 10.0  # calm face = high capacity signal

    weights = _effective_weights(face_stress is not None)
    weighted = sum(weights[k] * goodness[k] for k in weights)
    capacity = round(weighted * 10)  # 0-10 weighted avg -> 0-100

    # Main driver = the factor draining the most capacity right now
    # (largest weighted deficit from a full 10).
    deficits = {k: weights[k] * (10 - goodness[k]) for k in weights}
    main_key = max(deficits, key=deficits.get)

    reason = _rule_reason(main_key, night_care, capacity)
    return capacity, main_key, reason


def _rule_reason(main_key: str, night_care: int, capacity: int) -> str:
    label = CAPACITY_LABELS[main_key]
    band = "running low" if capacity < 40 else "holding steady" if capacity < 70 else "in a good place"
    phrases = {
        "mood": "how heavy today has felt is what's weighing on you most",
        "energy": "low energy is the biggest drain on you right now",
        "sleep": "not enough rest is the main thing pulling your capacity down",
        "night_care": "the nighttime caregiving load is what's taking the most out of you",
        "free_time": "having little time to yourself is the biggest squeeze right now",
        "face": "your face is reading as tense right now, more than anything you reported",
    }
    return f"Your capacity is {band}, and {phrases[main_key]} (main driver: {label})."


CAPACITY_SYSTEM_PROMPT = (
    "You gauge a family caregiver's remaining capacity for a support app. You are not a "
    "clinician and never diagnose. You read a short journal entry, five 0-10 self-report "
    "sliders, and sometimes a live facial-expression tension reading from the webcam. Return "
    "ONLY a JSON object, no other text, in exactly this shape: "
    '{"capacity": <0-100 int>, '
    '"main_driver": "<one of: Mood, Energy, Sleep, Night Care, Free Time, Facial Signs>", '
    '"reason": "<two or three warm, plain sentences addressed to the caregiver, no numbers>"}. '
    "Capacity = how much they have left in the tank right now (100 = full, 0 = empty). Weigh the "
    "journal's tone alongside the sliders, and the facial reading when one is provided. "
    "Only pick 'Facial Signs' as main_driver if a facial reading is provided AND it clearly "
    "disagrees with what they reported. main_driver is the single factor most shaping today's "
    "capacity. Keep the reason specific to what they wrote — never generic."
)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None


def _normalize_driver(value: str) -> str | None:
    """Map an LLM driver string back to a canonical label, tolerating case/spacing."""
    if not value:
        return None
    cleaned = value.strip().lower().replace("_", " ")
    for key, label in CAPACITY_LABELS.items():
        if cleaned == label.lower() or cleaned == key.replace("_", " "):
            return label
    return None


def compute_capacity(
    journal: str,
    mood: int,
    sleep: int,
    energy: int,
    night_care: int,
    free_time: int,
    face_stress: float | None = None,
) -> dict:
    """Capacity + main driver + reason. Tries the LLM (journal- and face-aware), falls back
    to the rule model. face_stress (0-1) is an optional live facial-tension reading — when
    absent, the five-factor model runs unchanged. Always returns a complete dict; never raises."""
    rule_capacity, rule_key, rule_reason = compute_capacity_rule(
        mood, sleep, energy, night_care, free_time, face_stress
    )
    rule_label = CAPACITY_LABELS[rule_key]

    journal_text = (journal or "").strip() or "(no journal written today)"
    if face_stress is not None:
        face_line = (
            f" Live facial-tension reading: {face_stress:.2f}/1.0 "
            "(0 = calm face, 1 = very tense face)."
        )
    else:
        face_line = " No facial reading available."
    prompt = (
        f"Journal entry:\n{journal_text}\n\n"
        f"Sliders (0-10): Mood={mood}, Sleep={sleep}, Energy={energy}, "
        f"Night Care burden={night_care}, Free Time={free_time}."
        f"{face_line}"
    )
    result = llm.complete(system=CAPACITY_SYSTEM_PROMPT, prompt=prompt, max_tokens=600)
    if result:
        text, provider = result
        parsed = _extract_json(text)
        if parsed:
            capacity = parsed.get("capacity")
            try:
                capacity = max(0, min(int(round(float(capacity))), 100))
            except (TypeError, ValueError):
                capacity = rule_capacity
            driver = _normalize_driver(str(parsed.get("main_driver", ""))) or rule_label
            reason = str(parsed.get("reason") or "").strip() or rule_reason
            return {
                "capacity": capacity,
                "main_driver": driver,
                "reason": reason,
                "source": provider,
            }

    return {
        "capacity": rule_capacity,
        "main_driver": rule_label,
        "reason": rule_reason,
        "source": "rule",
    }


# How much each detected facial expression contributes to stress, weighted by how present
# that expression is (probabilities sum to ~1, so this is effectively a weighted average).
# Fallback signal only — same "must keep working without it" status as rPPG: Daily
# Check-in stays the reliable core, this just enriches it when the camera can see a face.
EXPRESSION_STRESS_WEIGHTS = {
    "neutral": 0.3,
    "happy": 0.0,
    "sad": 0.65,
    "angry": 0.85,
    "fearful": 0.8,
    "disgusted": 0.55,
    "surprised": 0.35,
}


def expression_to_stress_score(expression: dict) -> float:
    """expression: plain dict of {name: 0-1 probability} for each key in
    EXPRESSION_STRESS_WEIGHTS — pass a Pydantic model's .model_dump(), not the model itself."""
    total = sum(
        EXPRESSION_STRESS_WEIGHTS[name] * float(expression[name])
        for name in EXPRESSION_STRESS_WEIGHTS
    )
    return round(max(0.0, min(total, 1.0)), 3)


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


def latest_face_stress(db: Session, now: datetime.datetime | None = None) -> float | None:
    """Most recent facial-expression stress score, but only if it's fresh enough to reflect
    how the caregiver looks right now — otherwise None (so check-in ignores stale face data)."""
    now = now or datetime.datetime.utcnow()
    reading = (
        db.query(models.StressReading)
        .filter(models.StressReading.source == "expression")
        .order_by(models.StressReading.created_at.desc())
        .first()
    )
    if reading is None:
        return None
    if (now - reading.created_at) > datetime.timedelta(seconds=FACE_FRESH_SECONDS):
        return None
    return reading.stress_score


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
        # Generous headroom for reasoning-model "thinking" tokens before the actual reply.
        max_tokens=400,
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
        # Generous headroom for reasoning-model "thinking" tokens before the actual reply.
        max_tokens=300,
    )
    return result[0] if result else None