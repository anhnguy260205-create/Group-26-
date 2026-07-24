"""Emotion analysis of a journal entry or chat message.

Produces the "Emotion: Frustrated · Stress: High · Burnout Risk: Moderate" tag from
FEATURES.md. Rule-based first so it always returns something offline; an LLM refines
the labels when reachable. Never diagnoses — these are supportive reflections only.
"""

import json

from . import llm

# Ordered by rough severity so a strong signal wins when several match.
EMOTION_KEYWORDS = {
    "overwhelmed": ["overwhelm", "too much", "can't cope", "cant cope", "drowning", "breaking point"],
    "exhausted": ["exhaust", "so tired", "drained", "worn out", "no energy", "burnt out", "burned out"],
    "frustrated": ["frustrat", "angry", "fed up", "annoyed", "irritat", "sick of"],
    "anxious": ["anxious", "worried", "scared", "afraid", "panic", "nervous", "on edge"],
    "sad": ["sad", "cry", "crying", "hopeless", "empty", "down", "depress"],
    "lonely": ["alone", "lonely", "no one", "nobody", "isolated", "by myself"],
    "hopeful": ["hopeful", "better", "improving", "grateful", "thankful", "proud", "relief"],
    "calm": ["calm", "okay", "fine", "peaceful", "rested", "good day"],
}

HIGH_STRESS_WORDS = [
    "overwhelm", "breaking point", "can't cope", "cant cope", "exhaust", "burnt out",
    "burned out", "hopeless", "too much", "drowning", "panic",
]
MODERATE_STRESS_WORDS = [
    "tired", "worried", "frustrat", "stress", "hard", "difficult", "struggl", "anxious", "angry",
]


def _rule_based(text: str) -> dict:
    lowered = text.lower()

    emotion = "neutral"
    for label, keywords in EMOTION_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            emotion = label
            break

    high = sum(1 for w in HIGH_STRESS_WORDS if w in lowered)
    moderate = sum(1 for w in MODERATE_STRESS_WORDS if w in lowered)
    if high >= 1:
        stress = "high"
    elif moderate >= 1:
        stress = "moderate"
    else:
        stress = "low"

    # Burnout risk leans on exhaustion/overwhelm specifically, not one-off frustration.
    if emotion in ("overwhelmed", "exhausted") or high >= 2:
        burnout = "high"
    elif stress == "high" or emotion in ("frustrated", "anxious", "sad", "lonely"):
        burnout = "moderate"
    else:
        burnout = "low"

    return {"emotion": emotion, "stress": stress, "burnout_risk": burnout, "source": "rule"}


_VALID = {
    "emotion": set(EMOTION_KEYWORDS) | {"neutral"},
    "stress": {"low", "moderate", "high"},
    "burnout_risk": {"low", "moderate", "high"},
}


def analyze(text: str) -> dict:
    """Return {emotion, stress, burnout_risk, source}. Always succeeds."""
    rule = _rule_based(text)

    prompt = (
        f'Caregiver wrote: "{text}"\n\n'
        "Classify it. Reply with ONLY a JSON object, no prose, with keys:\n"
        '  "emotion": one of '
        f'{sorted(_VALID["emotion"])}\n'
        '  "stress": "low" | "moderate" | "high"\n'
        '  "burnout_risk": "low" | "moderate" | "high"'
    )
    result = llm.complete(
        system=(
            "You label a caregiver's text for a support app. You are not a clinician and do "
            "not diagnose; these are supportive reflections. Output strict JSON only."
        ),
        prompt=prompt,
        max_tokens=60,
    )
    if not result:
        return rule

    text_out, provider = result
    try:
        start, end = text_out.find("{"), text_out.rfind("}")
        parsed = json.loads(text_out[start : end + 1])
        out = {
            "emotion": parsed["emotion"] if parsed.get("emotion") in _VALID["emotion"] else rule["emotion"],
            "stress": parsed["stress"] if parsed.get("stress") in _VALID["stress"] else rule["stress"],
            "burnout_risk": parsed["burnout_risk"]
            if parsed.get("burnout_risk") in _VALID["burnout_risk"]
            else rule["burnout_risk"],
            "source": provider,
        }
        return out
    except (ValueError, KeyError, TypeError):
        return rule
