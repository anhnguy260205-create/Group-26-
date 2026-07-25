"""Capacity Outlook — the prediction heart of Understand Me.

Goes past "what's your capacity today" to answer two questions a caregiver rarely stops to
ask themselves:
  1. CAUSES  — why has my state stayed low? (the recurring driver + what the journals show)
  2. CONSEQUENCES — if this pattern continues, what does it lead to?

Consequences are framed supportively and non-clinically: the point is caregiving
sustainability and getting ahead of burnout, NOT a medical prediction or diagnosis. The LLM
phrases it when reachable; a transparent rule model is the fallback.
"""

import json
import re

from sqlalchemy.orm import Session

from . import capforecast, llm, models

JOURNAL_WINDOW = 7


def _recent_journals(db: Session) -> list[str]:
    rows = (
        db.query(models.Checkin)
        .filter(models.Checkin.journal.isnot(None))
        .order_by(models.Checkin.created_at.desc())
        .limit(JOURNAL_WINDOW)
        .all()
    )
    return [r.journal for r in reversed(rows) if (r.journal or "").strip()]


def _rule_causes(driver: str | None, decline_days: int) -> str:
    if not driver:
        return (
            "There isn't one clear driver yet — a few more check-ins will sharpen what's pulling "
            "your capacity down."
        )
    driver_phrase = {
        "Night Care": "repeated nighttime caregiving is eating into your sleep and next-day energy",
        "Sleep": "not getting enough rest, night after night, is compounding",
        "Energy": "your energy has been depleted with little chance to refill it",
        "Mood": "the emotional weight of caregiving has been sitting heavy without a release",
        "Free Time": "you've had almost no time for yourself, so there's nothing topping you back up",
        "Facial Signs": "the strain is showing on you even when you don't say it out loud",
    }.get(driver, f"{driver.lower()} keeps coming up as the main strain")
    streak = f" for {decline_days} days running" if decline_days >= 2 else ""
    return (
        f"The thread across your recent check-ins is {driver}: {driver_phrase}{streak}. "
        "It's a pattern, not a one-off bad day — which is exactly why it's worth naming."
    )


def _rule_consequences(risk: str, driver: str | None) -> str:
    if risk == "high":
        return (
            "If this keeps up, you're on a path toward burnout — the kind of deep exhaustion where "
            "sleep doesn't fix it, patience runs short, and it gets harder to keep caring the way you "
            "want to. That's not a judgment; it's the cost of running on empty for too long. This is the "
            "point where handing off a shift or protecting real rest changes the trajectory."
        )
    if risk == "moderate":
        return (
            "Left unchanged, this slow slide is the runway to burnout — it rarely arrives all at once. "
            "A small change now (one night off, a protected break) is far easier than climbing back "
            "from empty later."
        )
    return (
        "Your capacity is holding, so there's no alarm here — the value is catching any drift early, "
        "before it builds. Keep what's working."
    )


SYSTEM_PROMPT = (
    "You analyze a caregiver's recent Capacity trend for a support app. You are not a "
    "clinician and NEVER diagnose or predict medical outcomes. Frame everything supportively and "
    "in terms of caregiving sustainability and burnout, not illness. Return ONLY a JSON object: "
    '{"causes": "<2-3 warm sentences on WHY their state has stayed low — the recurring driver and '
    'what the journals suggest>", "consequences": "<2-3 warm sentences on what CONTINUING this '
    'pattern tends to lead to (exhaustion, burnout, harder to sustain care), then one hopeful line '
    'that it is changeable>"}. No numbers, no diagnosis.'
)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None


def analyze(db: Session) -> dict:
    checkins = db.query(models.Checkin).order_by(models.Checkin.created_at).all()
    data = capforecast.analyze(checkins)

    risk = data["risk"]
    driver = data["recurring_driver"]
    decline_days = data["consecutive_decline_days"]

    causes = _rule_causes(driver, decline_days)
    consequences = _rule_consequences(risk, driver)
    source = "rule"

    if data["days_of_data"] >= 3:
        journals = _recent_journals(db)
        journal_text = "\n".join(f"- {j}" for j in journals) if journals else "(no journal entries)"
        series_text = ", ".join(f"{p['date']}:{p['capacity']}" for p in data["points"])
        prompt = (
            f"Daily capacity (date:score): {series_text}.\n"
            f"Recurring driver: {driver}. Consecutive declining days: {decline_days}. Risk: {risk}.\n"
            f"Recent journal lines:\n{journal_text}"
        )
        result = llm.complete(system=SYSTEM_PROMPT, prompt=prompt, max_tokens=600)
        if result:
            text, provider = result
            parsed = _extract_json(text)
            if parsed:
                causes = str(parsed.get("causes") or "").strip() or causes
                consequences = str(parsed.get("consequences") or "").strip() or consequences
                source = provider

    return {
        "risk": risk,
        "recurring_driver": driver,
        "consecutive_decline_days": decline_days,
        "days_of_data": data["days_of_data"],
        "causes": causes,
        "consequences": consequences,
        "source": source,
    }
