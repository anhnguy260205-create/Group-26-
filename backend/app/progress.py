"""Progress / Evidence: the morning-after payoff.

If the caregiver did a recharge action yesterday and their Capacity is higher today, show
that as concrete evidence — "Breathing ✓, Capacity +8" — so recovery feels like it's
working, not vanishing into the void. Pure rule-based: it just compares yesterday's done
actions with the day-over-day capacity change.
"""

import datetime

from sqlalchemy.orm import Session

from . import models, recharge


def _day_bounds(day: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    start = datetime.datetime(day.year, day.month, day.day)
    return start, start + datetime.timedelta(days=1)


def _avg_capacity(db: Session, day: datetime.date) -> int | None:
    start, end = _day_bounds(day)
    rows = (
        db.query(models.Checkin.capacity_score)
        .filter(models.Checkin.created_at >= start, models.Checkin.created_at < end)
        .all()
    )
    if not rows:
        return None
    scores = [r[0] for r in rows]
    return round(sum(scores) / len(scores))


def build(db: Session, now: datetime.datetime | None = None) -> dict:
    now = now or datetime.datetime.utcnow()
    today = now.date()
    yesterday = today - datetime.timedelta(days=1)

    y_start, y_end = _day_bounds(yesterday)
    done = (
        db.query(models.RechargeAction)
        .filter(
            models.RechargeAction.status == "done",
            models.RechargeAction.created_at >= y_start,
            models.RechargeAction.created_at < y_end,
        )
        .order_by(models.RechargeAction.id)
        .all()
    )
    done_labels = [recharge.ACTIONS.get(a.kind, {"label": a.kind})["label"] for a in done]

    cap_today = _avg_capacity(db, today)
    cap_yesterday = _avg_capacity(db, yesterday)
    capacity_change = (
        cap_today - cap_yesterday if cap_today is not None and cap_yesterday is not None else None
    )

    has_evidence = bool(done_labels) and capacity_change is not None
    if has_evidence and capacity_change > 0:
        actions = ", ".join(f"{l} ✓" for l in done_labels)
        evidence = (
            f"Yesterday you did {actions}. Today your capacity is up {capacity_change} points — "
            "that recovery is showing up."
        )
    elif done_labels and capacity_change is not None:
        actions = ", ".join(f"{l} ✓" for l in done_labels)
        evidence = (
            f"Yesterday you did {actions}. Capacity is about level today — recovery adds up over "
            "days, so keep going."
        )
    elif done_labels:
        actions = ", ".join(f"{l} ✓" for l in done_labels)
        evidence = f"Yesterday you did {actions}. Check in today to see how it moved your capacity."
    else:
        evidence = "No recharge actions logged yesterday yet — try one today and see it here tomorrow."

    return {
        "yesterday": yesterday.isoformat(),
        "done_actions": done_labels,
        "capacity_yesterday": cap_yesterday,
        "capacity_today": cap_today,
        "capacity_change": capacity_change,
        "has_evidence": has_evidence and capacity_change > 0,
        "evidence": evidence,
    }
