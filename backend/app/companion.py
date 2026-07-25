"""AI Companion: warm, non-clinical supportive chat.

Crisis detection is a minimal, deterministic keyword rule — never LLM-based — so it fires
even with zero network access. This is a lightweight safety net, not the full crisis-response
system; refine the keyword list and add proper escalation before relying on this in production.

Normal replies are LLM-phrased when available (via llm.py's Foundry-then-Anthropic chain),
with a templated fallback so the companion always says something supportive.
"""

import datetime

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


# Below this, the companion stops asking the caregiver to *do* things and starts taking
# things off them. This is the difference between a chatbot and a companion that reads the
# room: at low capacity, a prompt to journal is one more demand on someone who has none left.
PROTECT_CAPACITY = 60
DEPLETED_CAPACITY = 40


def _opening_mode(capacity: int | None, delta: int) -> str:
    """Which register to open in. Capacity outranks day-to-day movement -- someone who is
    depleted doesn't need to hear that today is marginally better than yesterday."""
    if capacity is None:
        return "unknown"
    if capacity < DEPLETED_CAPACITY:
        return "depleted"
    if capacity < PROTECT_CAPACITY:
        return "protect"
    if delta <= -5:
        return "harder"
    if delta >= 5:
        return "brighter"
    return "steady"


# Each mode carries a suggested next action, so the opening line ends somewhere concrete
# instead of trailing off into "let me know if you need anything".
MODE_SCRIPTS = {
    "depleted": {
        "line": (
            "Don't write a journal entry today. I can see how much you've already spent, and "
            "I'm not going to ask you for more. Let's just do one minute of breathing together."
        ),
        "action_kind": "box_breathing",
        "action_label": "One minute of breathing",
    },
    "protect": {
        "line": (
            "You've already given a lot today. Skip the long check-in if you want -- one small "
            "thing is enough, and I'd rather you rested than reported."
        ),
        "action_kind": "micro_break",
        "action_label": "Take five minutes off",
    },
    "harder": {
        "line": "Today looks harder than yesterday. I'm here -- want to talk through it?",
        "action_kind": None,
        "action_label": None,
    },
    "brighter": {
        "line": "Today's looking a little brighter than yesterday. How are you feeling?",
        "action_kind": None,
        "action_label": None,
    },
    "steady": {
        "line": "Steady day so far. How are you holding up right now?",
        "action_kind": None,
        "action_label": None,
    },
    "unknown": {
        "line": "I'm here whenever you want to check in. How are you doing right now?",
        "action_kind": None,
        "action_label": None,
    },
}

OPENING_SYSTEM_PROMPT = (
    "You are a warm, brief companion for caregivers. You are never clinical and never "
    "diagnose. You are given the caregiver's current state and the register to write in. Keep "
    "the meaning of the register exactly -- if you are told to relieve them of a task, relieve "
    "them of it; do not turn it back into a request. One or two sentences, max 35 words, no "
    "numbers, second person."
)

MODE_INSTRUCTIONS = {
    "depleted": "They are severely depleted. Explicitly tell them NOT to journal today, and offer one minute of breathing instead. Take the task away from them.",
    "protect": "They are running low. Give them permission to skip the full check-in and do one small thing instead.",
    "harder": "Today is harder than yesterday. Acknowledge it and open the door to talking.",
    "brighter": "Today is a little better than yesterday. Note it lightly and ask how they are.",
    "steady": "Today is steady. Greet them and ask how they are holding up.",
    "unknown": "You have no data on them yet. Greet them and invite them to check in.",
}


def opening_line(db: Session) -> dict:
    """Proactive opening for the Copilot, grounded in today's capacity and the forecast.

    Returns a dict rather than a bare string because the opening is a decision, not just
    text: which register to use, what to suggest next, and whether there's a recurring
    pattern worth raising. The caller renders those; the model only phrases the line.
    """
    checkins = db.query(models.Checkin).order_by(models.Checkin.created_at).all()
    data = capforecast.analyze(checkins) if checkins else None
    points = data["points"] if data else []
    capacity = points[-1]["capacity"] if points else None
    delta = points[-1]["capacity"] - points[-2]["capacity"] if len(points) >= 2 else 0

    mode = _opening_mode(capacity, delta)
    script = MODE_SCRIPTS[mode]
    line = script["line"]
    source = "rule"

    # A recurring weekday dip is raised as an open question, not an assertion -- the app can
    # see *that* Wednesdays are bad, but only the caregiver knows why.
    note = None
    if data and data.get("weekday_pattern_note"):
        today_name = capforecast.WEEKDAY_NAMES[datetime.date.today().weekday()]
        # Surface it on the day itself, or when the forecast already flags a hard stretch.
        if data["weekday_pattern"] == today_name or data["risk"] in ("moderate", "high"):
            note = data["weekday_pattern_note"]

    if points and llm.is_configured():
        prompt = (
            f"Their capacity today is {'unknown' if capacity is None else capacity} out of 100 "
            f"(higher is better), and it moved {delta} points since yesterday (negative = worse). "
            f"Recurring strain: {data['recurring_driver'] if data else 'none clear'}.\n"
            f"Register to write in: {MODE_INSTRUCTIONS[mode]}"
        )
        # Fast tier: this is a one-line greeting on page load, so latency beats depth.
        result = llm.complete(
            system=OPENING_SYSTEM_PROMPT, prompt=prompt, max_tokens=200, tier="fast"
        )
        if result:
            line, source = result

    return {
        "opening": line,
        "mode": mode,
        "capacity": capacity,
        "note": note,
        "suggested_action_kind": script["action_kind"],
        "suggested_action_label": script["action_label"],
        "source": source,
    }


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
            "You are a warm, non-clinical companion for caregivers. You validate "
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
