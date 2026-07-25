"""Recharge & Reconnect: turn the *cause* of today's capacity drop into concrete recovery
actions the caregiver marks Done or Skip.

The point of this module is that the recommendation is derived, not fixed. Sleep debt and
anxiety are different problems and get different answers -- telling an exhausted person to
meditate when what they actually need is twenty minutes lying down is the failure mode this
avoids. Two inputs decide the plan:

  1. the main driver from today's check-in  -> WHAT kind of recovery fits the cause
  2. today's capacity score                 -> HOW much effort we're allowed to ask for

Rule-based on purpose: the mapping is inspectable, testable and works offline. Each action
carries a `why` so the UI can show its reasoning rather than just an instruction.
"""

import datetime

from sqlalchemy.orm import Session

from . import models

# Below this, the caregiver has nothing left to spend. Only low-effort actions are offered --
# suggesting a walk to someone at 30 capacity is how an app gets deleted.
LOW_EFFORT_ONLY_BELOW = 40

ACTIONS = {
    "power_nap": {
        "kind": "power_nap", "label": "Power Nap", "effort": "low", "reconnect": False,
        "detail": "Ten to twenty minutes lying down, alarm set. Not a full sleep -- just enough to take the edge off.",
    },
    "sleep_early": {
        "kind": "sleep_early", "label": "Go to Bed Early", "effort": "low", "reconnect": False,
        "detail": "Aim to be in bed 30-60 minutes earlier tonight.",
    },
    "box_breathing": {
        "kind": "box_breathing", "label": "Box Breathing", "effort": "low", "reconnect": False,
        "detail": "In for 4, hold 4, out 4, hold 4. Four rounds is enough to shift your nervous system.",
    },
    "micro_break": {
        "kind": "micro_break", "label": "Five Minutes Off", "effort": "low", "reconnect": False,
        "detail": "Five minutes where nobody needs anything from you. Sit down, put the phone face down.",
    },
    "walking": {
        "kind": "walking", "label": "Walk It Off", "effort": "medium", "reconnect": False,
        "detail": "Ten minutes outside, no destination. Movement does what sitting still can't.",
    },
    "reach_out": {
        "kind": "reach_out", "label": "Reach Out To Someone", "effort": "medium", "reconnect": True,
        "detail": "Message one person who isn't part of the caregiving. Doesn't have to be about any of this.",
    },
    # --- retained so rows created by earlier versions still render ---
    "breathing": {
        "kind": "breathing", "label": "Breathing", "effort": "low", "reconnect": False,
        "detail": "A few minutes of paced breathing to settle your body.",
    },
    "walk": {
        "kind": "walk", "label": "Walk", "effort": "medium", "reconnect": True,
        "detail": "A short walk outside -- light, air, a change of scene.",
    },
}

# Driver -> (ordered actions, why this answers *that* cause). The `why` is the whole point:
# it's what makes this a recommendation rather than a fixed prompt.
DRIVER_PLAN = {
    "Sleep": {
        "actions": ["power_nap", "sleep_early"],
        "why": "You're short on sleep, so rest is the thing that actually moves the needle today -- breathing exercises won't repay sleep debt.",
    },
    "Night Care": {
        "actions": ["power_nap", "reach_out"],
        "why": "Broken nights are the drain here. Recovering some of that sleep matters, and so does asking whether one night this week could be covered by someone else.",
    },
    "Energy": {
        "actions": ["walking", "micro_break"],
        "why": "Low energy with sleep holding up usually responds better to gentle movement and a real break than to more rest.",
    },
    "Mood": {
        "actions": ["walking", "reach_out"],
        "why": "When mood is what's dropping, contact and movement tend to help more than solitude -- isolation is what makes a low day compound.",
    },
    "Free Time": {
        "actions": ["micro_break", "reach_out"],
        "why": "The squeeze is time that belongs to you. The fix isn't a technique, it's carving back a piece of the day.",
    },
    "Facial Signs": {
        "actions": ["box_breathing", "walking"],
        "why": "Your face is reading tense even though your answers look steadier. Box breathing works directly on that physical tension.",
    },
}

DEFAULT_PLAN = {
    "actions": ["box_breathing", "micro_break"],
    "why": "Not enough signal yet to pinpoint a cause, so this is a safe starting point. Do a check-in and the suggestions sharpen.",
}


def plan_for(driver: str | None, capacity: int | None = None) -> dict:
    """Resolve driver + capacity into an ordered action plan and its reasoning."""
    plan = DRIVER_PLAN.get(driver or "", DEFAULT_PLAN)
    kinds = list(plan["actions"])
    why = plan["why"]

    if capacity is not None and capacity < LOW_EFFORT_ONLY_BELOW:
        low_effort = [k for k in kinds if ACTIONS[k]["effort"] == "low"]
        if not low_effort:
            # The cause-appropriate actions all cost something they don't have. Substitute
            # the gentlest thing that still addresses the cause rather than offering nothing.
            low_effort = ["micro_break"]
        kinds = low_effort
        why = (
            f"{why} Your capacity is very low right now, so I've kept this to the "
            "smallest version -- anything more would be asking for energy you don't have today."
        )

    return {"kinds": kinds, "why": why}


def recommend_kinds(driver: str | None, capacity: int | None = None) -> list[str]:
    """Backwards-compatible helper: just the action kinds."""
    return plan_for(driver, capacity)["kinds"]


def _today_bounds(now: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime]:
    start = datetime.datetime(now.year, now.month, now.day)
    return start, start + datetime.timedelta(days=1)


def actions_for_today(
    db: Session,
    driver: str | None,
    capacity: int | None = None,
    now: datetime.datetime | None = None,
) -> list[models.RechargeAction]:
    now = now or datetime.datetime.utcnow()
    start, end = _today_bounds(now)
    existing = (
        db.query(models.RechargeAction)
        .filter(models.RechargeAction.created_at >= start, models.RechargeAction.created_at < end)
        .order_by(models.RechargeAction.id)
        .all()
    )
    if existing:
        return existing
    created = []
    for kind in plan_for(driver, capacity)["kinds"]:
        action = models.RechargeAction(kind=kind, driver=driver, status="pending")
        db.add(action)
        created.append(action)
    db.commit()
    for a in created:
        db.refresh(a)
    return created


def to_dict(action: models.RechargeAction, why: str | None = None) -> dict:
    meta = ACTIONS.get(
        action.kind,
        {"label": action.kind, "detail": "", "reconnect": False, "effort": "low"},
    )
    return {
        "id": action.id, "kind": action.kind, "label": meta["label"], "detail": meta["detail"],
        "reconnect": meta["reconnect"], "effort": meta["effort"], "driver": action.driver,
        "why": why, "status": action.status,
    }
