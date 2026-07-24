"""Seed demo data so the dashboard, trends chart, and delegation have something to show.

Run from the backend/ dir:  python seed_demo.py
Wipes and repopulates tasks + 7 days of stress readings.
"""

import datetime
import random

from app.database import Base, SessionLocal, engine
from app import models

Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Reset
db.query(models.Reflection).delete()
db.query(models.CareSession).delete()
db.query(models.StressReading).delete()
db.query(models.Task).delete()
db.commit()

now = datetime.datetime.utcnow()

# --- Tasks (care dashboard + delegation candidates) ---
tasks = [
    ("Give Dad his morning medication", "medication", now - datetime.timedelta(hours=2)),
    ("Refill blood pressure prescription", "todo", now - datetime.timedelta(hours=5)),
    ("Doctor appointment at General Hospital", "appointment", now + datetime.timedelta(hours=3)),
    ("Buy groceries for the week", "todo", now + datetime.timedelta(hours=6)),
    ("Night-time care shift", "todo", now + datetime.timedelta(hours=10)),
    ("Physiotherapy session booking", "appointment", now + datetime.timedelta(days=1)),
]
for title, kind, due in tasks:
    db.add(models.Task(title=title, kind=kind, due_at=due, done=False))

# --- 7 days of stress readings, trending upward (the story) ---
for day_ago in range(7, -1, -1):
    day = now - datetime.timedelta(days=day_ago)
    base = 0.35 + (7 - day_ago) * 0.06  # rises from ~0.35 to ~0.77 over the week
    for _ in range(random.randint(3, 6)):
        score = max(0.0, min(1.0, base + random.uniform(-0.08, 0.08)))
        if day_ago == 0:
            # "Today": never backdate past the real current moment, or a fake reading
            # with a later clock-hour than "now" would outrank real live readings in
            # latest_reading()'s created_at DESC ordering.
            latest_hour = max(now.hour - 1, 7)
            ts = day.replace(
                hour=random.randint(7, latest_hour),
                minute=random.randint(0, 59),
            )
        else:
            ts = day.replace(hour=random.randint(7, 22), minute=random.randint(0, 59))
        db.add(
            models.StressReading(
                source="rppg",
                heart_rate_bpm=round(70 + score * 45, 1),
                respiration_rate_bpm=round(10 + score * 10, 1),  # 10-20 bpm, rises with stress
                signal_quality=round(random.uniform(0.6, 0.95), 2),
                stress_score=round(score, 3),
                created_at=ts,
            )
        )

# --- One open CareSession so /intervention/{id}/pace has something to query ---
demo_session = models.CareSession(
    trigger_score=0.75,
    trigger_reasoning="Demo session for testing the breathing intervention.",
    start_stress_score=0.75,
)
db.add(demo_session)

db.commit()
print(f"Seeded: 6 tasks + 8 days of stress readings (trending up) + CareSession id={demo_session.id}.")
db.close()