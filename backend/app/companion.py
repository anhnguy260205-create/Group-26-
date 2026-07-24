"""AI Companion: warm, non-clinical supportive chat.

Crisis detection is a minimal, deterministic keyword rule — never LLM-based — so it fires
even with zero network access. This is a lightweight safety net, not the full crisis-response
system; refine the keyword list and add proper escalation before relying on this in production.

Normal replies are LLM-phrased when available (via llm.py's Foundry-then-Anthropic chain),
with a templated fallback so the companion always says something supportive.
"""

from sqlalchemy.orm import Session

from . import capforecast, llm, models, resources

CRISIS_KEYWORDS = [
    "kill myself",
    "end my life",
    "suicid",  # catches suicide / suicidal
    "not want to live",
    "don't want to live",
    "want to die",
    "hurt myself",
    "self harm",
    "self-harm",
    "no reason to go on",
    "better off without me",
]

CHAT_HISTORY_WINDOW = 6
CONTEXT_CHECKINS = 3
CONTEXT_JOURNAL = 3


def is_crisis_message(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in CRISIS_KEYWORDS)


def crisis_response() -> str:
    lines = " ".join(f"{region} — {line}." for region, line in resources.CRISIS_LINES.items())
    return (
        "I'm really glad you told me that, and I want to take it seriously. What you're "
        "feeling matters, and you don't have to carry it alone right now. Please reach out to "
        f"someone who can help directly: {lines} If you're in immediate danger, please contact "
        "local emergency services. I'm not able to provide medical care or therapy, but I'm "
        "here to keep listening if you want to say more."
    )


def _build_context(db: Session) -> str:
    """Brief, recent context so the companion can reference how things have been going."""
    parts = []

    readings = (
        db.query(models.StressReading)
        .order_by(models.StressReading.created_at.desc())
        .limit(CONTEXT_CHECKINS)
        .all()
    )
    if readings:
        avg = sum(r.stress_score for r in readings) / len(readings)
        parts.append(f"Recent stress readings average {avg:.2f} on a 0-1 scale.")

    entries = (
        db.query(models.JournalEntry)
        .order_by(models.JournalEntry.created_at.desc())
        .limit(CONTEXT_JOURNAL)
        .all()
    )
    if entries:
        joined = "; ".join(e.text for e in reversed(entries))
        parts.append(f"Recent journal entries: {joined}")

    return " ".join(parts)


def opening_line(db: Session) -> tuple[str, str]:
    """Proactive first line grounded in the capacity trend — e.g. 'Today looks harder than
    yesterday.' Returns (line, source)."""
    checkins = db.query(models.Checkin).order_by(models.Checkin.created_at).all()
    data = capforecast.analyze(checkins) if checkins else None
    points = data["points"] if data else []
    delta = points[-1]["capacity"] - points[-2]["capacity"] if len(points) >= 2 else 0

    if not points:
        base = "I'm here whenever you want to check in. How are you doing right now?"
    elif delta <= -5:
        base = "Today looks harder than yesterday. I'm here — want to talk through it?"
    elif delta >= 5:
        base = "Today's looking a little brighter than yesterday. How are you feeling?"
    else:
        base = "Steady day so far. How are you holding up right now?"

    driver = data["recurring_driver"] if data else None
    if data and points and llm.is_configured():
        prompt = (
            f"Caregiver's capacity yesterday->today changed by {delta} points (negative = worse). "
            f"Recurring strain: {driver or 'none clear'}. Write ONE short, warm opening line (max 20 "
            "words) greeting them, naming whether today looks harder or easier than yesterday. No numbers."
        )
        result = llm.complete(
            system="You are a warm, brief companion for family caregivers.", prompt=prompt, max_tokens=200
        )
        if result:
            return result[0], result[1]
    return base, "rule"


def reply(db: Session, user_text: str) -> tuple[str, str]:
    """Returns (assistant_text, source). source is 'foundry'/'anthropic'/'template'/'rule'
    ('rule' only for the deterministic crisis path)."""
    if is_crisis_message(user_text):
        return crisis_response(), "rule"

    context = _build_context(db)
    history = (
        db.query(models.ChatMessage)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(CHAT_HISTORY_WINDOW)
        .all()
    )
    history_text = "\n".join(f"{m.role}: {m.content}" for m in reversed(history))

    prompt = (
        (f"Context on the caregiver's recent state: {context}\n\n" if context else "")
        + (f"Recent conversation:\n{history_text}\n\n" if history_text else "")
        + f"Caregiver just said: \"{user_text}\"\n\n"
        "Respond warmly and briefly (2-4 sentences), validating what they're feeling without "
        "being generic. Ask a gentle follow-up question if it fits naturally. You are support, "
        "not therapy — never diagnose or claim to treat."
    )
    result = llm.complete(
        system=(
            "You are a warm, non-clinical companion for family caregivers. You validate "
            "feelings, never minimize them, and never give medical advice or diagnoses."
        ),
        prompt=prompt,
        max_tokens=180,
    )
    if result:
        text, provider = result
        return text, provider

    return (
        "Many people caring long-term for family feel exactly this way — it's real, and it "
        "makes sense. Do you want to tell me more about what happened today?",
        "template",
    )
