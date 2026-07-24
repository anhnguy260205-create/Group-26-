"""Smart Task Delegation: suggest which pending tasks to hand to which family member.

Same architecture as the rest of the AI brain: the *selection* is rule-based (reliable
offline), and the LLM — via Microsoft Foundry — only *phrases* the ask. Falls back to a
template if the LLM is unavailable.
"""

import datetime

from sqlalchemy.orm import Session

from . import llm, models

# In a real product these come from the caregiver's circle; hardcoded for the demo.
FAMILY_MEMBERS = ["your sister Mei", "your brother Wei", "your cousin Lin"]

MAX_SUGGESTIONS = 3


def _phrase_ask(task_title: str, member: str) -> tuple[str, str]:
    prompt = (
        f"A caregiver is overwhelmed and could hand off this task: '{task_title}'. "
        f"Write one short, warm message (max 20 words) they could send to {member} to ask "
        "for help with it. Natural and specific, not guilt-inducing. No exclamation points."
    )
    result = llm.complete(
        system="You help an overwhelmed caregiver gently ask family for help.",
        prompt=prompt,
        max_tokens=60,
    )
    if result:
        text, provider = result
        return text, provider
    return f"Hi {member}, could you help me with \"{task_title}\" today? It would take a lot off my plate.", "template"


def suggest(db: Session, now: datetime.datetime | None = None) -> list[dict]:
    """Pick the most relieving tasks to delegate and phrase an ask for each."""
    now = now or datetime.datetime.utcnow()
    pending = (
        db.query(models.Task)
        .filter(models.Task.done.is_(False))
        .filter(models.Task.assigned_to.is_(None))
        .all()
    )
    if not pending:
        return []

    # Prioritize: overdue first, then soonest due, then oldest created.
    def sort_key(t: models.Task):
        overdue = t.due_at is not None and t.due_at < now
        due = t.due_at or datetime.datetime.max
        return (not overdue, due, t.created_at)

    pending.sort(key=sort_key)

    suggestions = []
    for i, task in enumerate(pending[:MAX_SUGGESTIONS]):
        member = FAMILY_MEMBERS[i % len(FAMILY_MEMBERS)]
        message, source = _phrase_ask(task.title, member)
        suggestions.append(
            {
                "task_id": task.id,
                "title": task.title,
                "suggested_to": member,
                "message": message,
                "message_source": source,
            }
        )
    return suggestions
