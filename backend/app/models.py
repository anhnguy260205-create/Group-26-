import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from .database import Base


def utcnow():
    return datetime.datetime.utcnow()


class Task(Base):
    """Care dashboard entry: medication reminder, appointment, or plain to-do."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    kind = Column(String(32), nullable=False, default="todo")  # medication | appointment | todo
    due_at = Column(DateTime, nullable=True)
    done = Column(Boolean, nullable=False, default=False)
    done_at = Column(DateTime, nullable=True)
    assigned_to = Column(String(128), nullable=True)  # delegated family member, if any
    created_at = Column(DateTime, nullable=False, default=utcnow)


class StressReading(Base):
    """A single physiological/behavioral sample taken while the caregiver uses the app."""

    __tablename__ = "stress_readings"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(32), nullable=False)  # rppg | manual
    heart_rate_bpm = Column(Float, nullable=True)
    respiration_rate_bpm = Column(Float, nullable=True)
    signal_quality = Column(Float, nullable=True)  # 0-1 confidence of the rPPG estimate
    self_reported_stress = Column(Integer, nullable=True)  # 1-10, used when source == manual
    stress_score = Column(Float, nullable=False)  # normalized 0-1, computed at ingest time
    # Daily Check-in components (set when source == "checkin"), kept so the Digital Twin
    # and Weekly Summary can name the *driver* of stress, not just the combined score.
    mood = Column(Integer, nullable=True)  # 1 Good - 4 Barely holding on
    hours_slept = Column(Float, nullable=True)
    care_hours = Column(Float, nullable=True)
    had_me_time = Column(Boolean, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Checkin(Base):
    """A Daily Check-in: a journal line + five 0-10 sliders, scored into a Capacity reading
    (0-100, higher = more in the tank) with its main driver and a reason. An optional fused
    facial-tension reading (0-1) from the background camera nudges the score."""

    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, index=True)
    journal = Column(String(500), nullable=True)
    mood = Column(Integer, nullable=False)  # 0-10
    sleep = Column(Integer, nullable=False)  # 0-10
    energy = Column(Integer, nullable=False)  # 0-10
    night_care = Column(Integer, nullable=False)  # 0-10 (burden)
    free_time = Column(Integer, nullable=False)  # 0-10
    face_stress = Column(Float, nullable=True)  # 0-1 fused facial-tension reading, if fresh
    capacity_score = Column(Integer, nullable=False)  # 0-100
    main_driver = Column(String(32), nullable=False)
    reason = Column(String(1024), nullable=False)
    source = Column(String(16), nullable=False, default="rule")  # foundry | anthropic | rule
    created_at = Column(DateTime, nullable=False, default=utcnow)


class RechargeAction(Base):
    """A recommended recovery action (breathing / walk / early night) chosen from the day's
    capacity driver. Marked Done or Skipped; Progress reads the Done ones the next day."""

    __tablename__ = "recharge_actions"

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String(32), nullable=False)  # breathing | walk | sleep_early
    driver = Column(String(32), nullable=True)
    status = Column(String(16), nullable=False, default="pending")  # pending | done | skipped
    created_at = Column(DateTime, nullable=False, default=utcnow)
    completed_at = Column(DateTime, nullable=True)


class CareSession(Base):
    """A guided-recovery (breathing) session triggered by threshold detection."""

    __tablename__ = "care_sessions"

    id = Column(Integer, primary_key=True, index=True)
    trigger_score = Column(Float, nullable=False)
    trigger_reasoning = Column(String(1024), nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow)
    ended_at = Column(DateTime, nullable=True)
    start_stress_score = Column(Float, nullable=True)
    end_stress_score = Column(Float, nullable=True)


class Reflection(Base):
    """Closing message shown after a CareSession ends."""

    __tablename__ = "reflections"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("care_sessions.id"), nullable=False)
    message = Column(String(2048), nullable=False)
    generated_by = Column(String(16), nullable=False, default="template")  # llm | template
    created_at = Column(DateTime, nullable=False, default=utcnow)


class JournalEntry(Base):
    """One-line daily journal entry, with an optional AI-generated summary of recent entries."""

    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(500), nullable=False)
    mood = Column(Integer, nullable=True)  # 1 (great) - 5 (awful), same scale as check-in
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ChatMessage(Base):
    """A single message in the caregiver's ongoing AI Companion thread (one thread, no rooms)."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(String(2000), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
