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
    source = Column(String(32), nullable=False)  # rppg | manual | checkin | expression
    heart_rate_bpm = Column(Float, nullable=True)
    respiration_rate_bpm = Column(Float, nullable=True)
    signal_quality = Column(Float, nullable=True)  # 0-1 confidence of the rPPG estimate
    self_reported_stress = Column(Integer, nullable=True)  # 1-10, used when source == manual
    # Facial-expression probabilities (0-1 each, sum to ~1), used when source == expression
    expr_neutral = Column(Float, nullable=True)
    expr_happy = Column(Float, nullable=True)
    expr_sad = Column(Float, nullable=True)
    expr_angry = Column(Float, nullable=True)
    expr_fearful = Column(Float, nullable=True)
    expr_disgusted = Column(Float, nullable=True)
    expr_surprised = Column(Float, nullable=True)
    stress_score = Column(Float, nullable=False)  # normalized 0-1, computed at ingest time
    created_at = Column(DateTime, nullable=False, default=utcnow)


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
