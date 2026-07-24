"""Journal: one-line daily entries, plus an AI summary across recent ones.

Summary is LLM-phrased when available, with a simple heuristic fallback (entry count +
average mood trend) so the Journal page never shows nothing.
"""

from . import llm, models

SUMMARY_WINDOW = 7


def generate_summary(entries: list[models.JournalEntry]) -> tuple[str, str]:
    """entries must be oldest-first. Returns (summary, source)."""
    if not entries:
        return "No journal entries yet — write a line about today to get started.", "template"

    recent = entries[-SUMMARY_WINDOW:]
    lines = "\n".join(f"- {e.text}" for e in recent)
    prompt = (
        f"A caregiver's last {len(recent)} journal entries, oldest first:\n{lines}\n\n"
        "In one or two short sentences, name the main recurring theme or biggest stressor "
        "across these entries. Be specific and grounded in what they wrote, not generic."
    )
    result = llm.complete(
        system=(
            "You are a perceptive, warm assistant that summarizes a caregiver's journal to "
            "help them notice patterns. You never diagnose or give medical advice."
        ),
        prompt=prompt,
        max_tokens=100,
    )
    if result:
        text, provider = result
        return text, provider

    moods = [e.mood for e in recent if e.mood is not None]
    if moods:
        trend = "holding steady"
        if len(moods) > 1 and moods[-1] > moods[0]:
            trend = "trending harder"
        elif len(moods) > 1 and moods[-1] < moods[0]:
            trend = "trending a bit easier"
        return (
            f"Over your last {len(recent)} entries, things have been {trend}. "
            "Keep an eye on what's coming up most often.",
            "template",
        )
    return (
        f"You've written {len(recent)} entries recently — worth a look back to spot what keeps coming up.",
        "template",
    )
