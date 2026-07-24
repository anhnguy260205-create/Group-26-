"""Recharge & Reconnect: turn today's capacity main-driver into 1-2 concrete recovery
actions (breathing / walk / early night) the caregiver marks Done or Skip. Rule-based."""

import datetime

from sqlalchemy.orm import Session

from . import models

ACTIONS = {
    "breathing": {"kind": "breathing", "label": "Breathing", "detail": "A few minutes of paced breathing to settle your body.", "reconnect": False},
    "walk": {"kind": "walk", "label": "Walk", "detail": "A short walk outside — light, air, a change of scene.", "reconnect": True},
    "sleep_early": {"kind": "sleep_early", "label": "Go to Bed Early", "detail": "Aim to be in bed 30-60 minutes earlier tonight.", "reconnect": False},
}

DRIVER_RECOMMENDATIONS = {
    "Sleep": ["sleep_early", "breathing"],
    "Night Care": ["sleep_early", "breathing"],
    "Energy": ["walk", "breathing"],
    "Mood": ["walk", "breathing"],
    "Free Time": ["walk", "breathing"],
    "Facial Signs": ["breathing", "walk"],
}
DEFAULT_RECOMMENDATION = ["breathing", "walk"]


def recommend_kinds(driver: str | None) -> list[str]:
    return DRIVER_RECOMMENDATIONS.get(driver or "", DEFAULT_RECOMMENDATION)


def _today_bounds(now: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime]:
    start = datetime.datetime(now.year, now.month, now.day)
    return start, start + datetime.timedelta(days=1)


def actions_for_today(db: Session, driver: str | None, now: datetime.datetime | None = None) -> list[models.RechargeAction]:
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
    for kind in recommend_kinds(driver):
        action = models.RechargeAction(kind=kind, driver=driver, status="pending")
        db.add(action)
        created.append(action)
    db.commit()
    for a in created:
        db.refresh(a)
    return created


def to_dict(action: models.RechargeAction) -> dict:
    meta = ACTIONS.get(action.kind, {"label": action.kind, "detail": "", "reconnect": False})
    return {
        "id": action.id, "kind": action.kind, "label": meta["label"], "detail": meta["detail"],
        "reconnect": meta["reconnect"], "driver": action.driver, "status": action.status,
    }
