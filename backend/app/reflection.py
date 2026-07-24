from . import llm, models


def generate(session: models.CareSession) -> tuple[str, str]:
    """Return (message, generated_by) for the closing reflection after a session ends."""
    start = session.start_stress_score
    end = session.end_stress_score
    improved = start is not None and end is not None and end < start

    prompt = (
        "A caregiver just finished a short guided-breathing recovery session. "
        f"Stress score before: {start if start is not None else 'unknown'}. "
        f"Stress score after: {end if end is not None else 'unknown'}. "
        "Write a warm, brief (2-3 sentences) closing reflection. Acknowledge the effort of "
        "pausing, not just the outcome. Do not mention numbers or scores. No exclamation points."
    )
    result = llm.complete(
        system=(
            "You are a gentle, grounded companion for caregivers. You never sound clinical "
            "or performative. You close the loop after a recovery session with warmth."
        ),
        prompt=prompt,
        # Generous headroom for reasoning-model "thinking" tokens before the actual reply.
        max_tokens=500,
    )
    if result:
        text, provider = result
        return text, provider

    if improved:
        message = (
            "You noticed something was building, and you stopped to meet it instead of "
            "pushing through. That pause is exactly why you feel a little steadier right now. "
            "The care you're giving is real, and so is the care you just gave yourself."
        )
    else:
        message = (
            "Taking that pause mattered, even if it doesn't show up as a number. Some days "
            "the body needs more than a few minutes, and that's alright — the fact that you "
            "stopped to check in is the part that counts."
        )
    return message, "template"
