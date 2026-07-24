import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---- Task ----


class TaskBase(BaseModel):
    title: str
    kind: Literal["medication", "appointment", "todo"] = "todo"
    due_at: Optional[datetime.datetime] = None


class TaskCreate(TaskBase):
    pass


class Task(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    done: bool
    done_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


# ---- Stress ----


class StressReadingCreate(BaseModel):
    source: Literal["rppg", "manual"]
    heart_rate_bpm: Optional[float] = None
    respiration_rate_bpm: Optional[float] = None
    signal_quality: Optional[float] = Field(default=None, ge=0, le=1)
    self_reported_stress: Optional[int] = Field(default=None, ge=1, le=10)


class StressReading(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    heart_rate_bpm: Optional[float] = None
    respiration_rate_bpm: Optional[float] = None
    signal_quality: Optional[float] = None
    self_reported_stress: Optional[int] = None
    stress_score: float
    created_at: datetime.datetime


# ---- Threshold / AI brain ----


class ThresholdResult(BaseModel):
    intervene: bool
    combined_score: float
    behavioral_score: float
    physiological_score: float
    reasoning: str
    reasoning_source: Literal["llm", "rule"]


# ---- Care session / intervention ----


class SessionStart(BaseModel):
    trigger_score: float
    trigger_reasoning: Optional[str] = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime] = None
    trigger_score: float
    start_stress_score: Optional[float] = None
    end_stress_score: Optional[float] = None


class BreathingPace(BaseModel):
    inhale_seconds: float
    hold_seconds: float
    exhale_seconds: float
    guidance: str


class SessionEnd(BaseModel):
    end_stress_score: Optional[float] = None


# ---- Reflection ----


class ReflectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    message: str
    generated_by: str
    created_at: datetime.datetime
