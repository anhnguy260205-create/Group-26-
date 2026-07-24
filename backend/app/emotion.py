"""Emotional tone analysis over recent journal entries.

Deliberately NOT diagnostic — the app's own positioning is "support and signposting, not
medical." So this scores descriptive emotional tone (happy / sad / low-mood-and-heavy),
never a clinical construct like "depression." The LLM is instructed accordingly, and no
rule-based diagnosis logic backs this — if the LLM is unavailable, we say so honestly
rather than fabricate scores from nothing.
"""

import json
import re

from . import llm, models

ANALYSIS_WINDOW = 7

SYSTEM_PROMPT = (
    "You describe the emotional tone of a caregiver's journal entries for a support app. "
    "You are not a clinician, you do not diagnose, and you never use clinical/diagnostic "
    "terms like 'depression' — describe tone only, in plain supportive language. Respond "
    "with ONLY a JSON object, no other text, in exactly this shape: "
    '{"happy": <0-100 int>, "sad": <0-100 int>, "low_mood": <0-100 int>, "summary": "<one short sentence>"}. '
    "Each score is how present that tone is across the entries (0 = not present, 100 = dominant) "
    "— they are independent, not required to sum to 100. 'low_mood' means heaviness/flatness/"
    "low energy, not a diagnosis."
)


def _extract_json(text: str) -> dict | None:
    """LLMs (especially reasoning models) sometimes wrap JSON in extra text despite
    instructions — pull out the first {...} block rather than fail outright."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None


def _clamp(value, lo=0, hi=100) -> int:
    try:
        return max(lo, min(int(round(float(value))), hi))
    except (TypeError, ValueError):
        return 0


def analyze(entries: list[models.JournalEntry]) -> dict:
    """entries must be oldest-first. Always returns a complete dict — never raises."""
    if not entries:
        return {
            "happy": 0,
            "sad": 0,
            "low_mood": 0,
            "summary": "No journal entries yet — write a few to see emotional trends here.",
            "source": "template",
            "entry_count": 0,
        }

    recent = entries[-ANALYSIS_WINDOW:]
    lines = "\n".join(f"- {e.text}" for e in recent)
    prompt = f"Journal entries, oldest first:\n{lines}"

    result = llm.complete(system=SYSTEM_PROMPT, prompt=prompt, max_tokens=600)
    if result:
        text, provider = result
        parsed = _extract_json(text)
        if parsed:
            return {
                "happy": _clamp(parsed.get("happy")),
                "sad": _clamp(parsed.get("sad")),
                "low_mood": _clamp(parsed.get("low_mood")),
                "summary": str(parsed.get("summary") or "").strip()
                or "Emotional tone analyzed from your recent entries.",
                "source": provider,
                "entry_count": len(recent),
            }

    return {
        "happy": 0,
        "sad": 0,
        "low_mood": 0,
        "summary": "Emotional tone analysis isn't available right now — your journal entries are still saved.",
        "source": "unavailable",
        "entry_count": len(recent),
    }
