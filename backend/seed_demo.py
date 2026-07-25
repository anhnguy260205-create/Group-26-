"""Seed demo data so the dashboard, trends chart, forecast and recharge have something to show.

Run from the backend/ dir:
    python seed_demo.py              # decline story: capacity falling, projection crosses the low line
    python seed_demo.py --pattern    # weekday story: stable overall, but every Wednesday collapses

Wipes and repopulates tasks, stress readings, check-ins and recharge actions.

Capacity is never hardcoded into the Checkin rows. We pick a target capacity per day, derive
sliders that produce it, then run the real scoring function (scoring.compute_capacity_rule) over
those sliders. So the seeded data is scored by exactly the same code path a live user hits --
no fake numbers in the demo.
"""

import argparse
import datetime
import random

from app.database import Base, SessionLocal, engine
from app import models, scoring

parser = argparse.ArgumentParser()
parser.add_argument("--pattern", action="store_true", help="seed the recurring-weekday-dip story instead")
args = parser.parse_args()

Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Reset (children first)
db.query(models.Reflection).delete()
db.query(models.CareSession).delete()
db.query(models.RechargeAction).delete()
db.query(models.Checkin).delete()
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
        ts = day.replace(hour=random.randint(7, 22), minute=random.randint(0, 59))
        db.add(
            models.StressReading(
                source="rppg",
                heart_rate_bpm=round(70 + score * 45, 1),
                signal_quality=round(random.uniform(0.6, 0.95), 2),
                stress_score=round(score, 3),
                created_at=ts,
            )
        )

# ---------------------------------------------------------------------------
# Daily Check-ins -> Capacity series
#
# Two demo profiles, 14 days each, oldest first.
#
#   DECLINE: holds in the high 80s/low 90s, then the last four days fall off a cliff
#            (92 -> 85 -> 79 -> 72). That gives the forecast a slope of about -6.6/day,
#            so the three-day projection lands near 65 / 60 / 55 and crosses the
#            low-capacity line -- the "you are heading for a hard day" demo.
#
#   PATTERN: stable in the mid 80s all fortnight except Wednesdays, which crater to
#            the high 60s both weeks. Weekday-pattern detection picks that up and the
#            Companion asks about it -- the "I noticed your Wednesdays" demo.
#
# Both are deliberately gentle at the start so the change is legible on the chart.
# ---------------------------------------------------------------------------

DECLINE_TARGETS = [89, 91, 88, 90, 87, 89, 91, 88, 90, 89, 92, 85, 79, 72]
PATTERN_TARGETS = [85, 86, 84, 68, 86, 85, 87, 84, 86, 85, 67, 86, 85, 84]

targets = PATTERN_TARGETS if args.pattern else DECLINE_TARGETS

JOURNALS_LOW = [
    "Barely sat down today. Dad was up three times in the night again.",
    "Slept maybe four hours. Everything feels heavier than it should.",
    "Snapped at my sister on the phone. I didn't mean it, I'm just empty.",
    "Ran the whole day on coffee. Fell asleep on the sofa before dinner.",
]
JOURNALS_MID = [
    "Long day but we got through it. Managed a shower and a proper meal.",
    "Dad had a settled afternoon, so I actually read for twenty minutes.",
    "Busy, but nothing went wrong. I'll take that.",
    "Tired but okay. Neighbour dropped off soup, which helped more than she knows.",
]


def r(x: float) -> int:
    """Round-half-up to int, then clamp to the 0-10 slider range."""
    return max(0, min(int(x + 0.5), 10))


def sliders_for(target: int) -> dict:
    """Derive five 0-10 sliders that score to roughly `target` capacity.

    Offsets are fixed relative to the daily average so that Sleep is always the weakest
    component -- that makes Sleep the recurring main driver, which is what the Recharge
    and Companion demos key off. The +0.17 corrects the bias the offsets introduce.
    """
    g = target / 10.0 + 0.17
    return {
        "mood": r(g + 0.5),
        "energy": r(g + 0.3),
        "sleep": r(g - 2.0),
        "night_care": r(10 - (g - 0.5)),  # stored as burden, so invert the goodness
        "free_time": r(g + 0.7),
    }


today = datetime.datetime(now.year, now.month, now.day, 20, 30)

for offset, target in enumerate(targets):
    day = today - datetime.timedelta(days=len(targets) - 1 - offset)
    s = sliders_for(target)
    capacity, driver_key, reason = scoring.compute_capacity_rule(
        mood=s["mood"],
        sleep=s["sleep"],
        energy=s["energy"],
        night_care=s["night_care"],
        free_time=s["free_time"],
    )
    journal = random.choice(JOURNALS_LOW if capacity < 78 else JOURNALS_MID)
    db.add(
        models.Checkin(
            journal=journal,
            mood=s["mood"],
            sleep=s["sleep"],
            energy=s["energy"],
            night_care=s["night_care"],
            free_time=s["free_time"],
            capacity_score=capacity,
            main_driver=scoring.CAPACITY_LABELS[driver_key],
            reason=reason,
            source="rule",
            created_at=day,
        )
    )

db.commit()

seeded = db.query(models.Checkin).order_by(models.Checkin.created_at).all()
db.close()

series = [c.capacity_score for c in seeded]
profile = "pattern" if args.pattern else "decline"
print(f"Seeded ({profile}): 6 tasks, 8 days of stress readings, {len(seeded)} daily check-ins.")
print(f"Capacity series (oldest -> newest): {series}")
print(f"Main driver today: {seeded[-1].main_driver}")
