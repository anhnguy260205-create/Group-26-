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
    assigned_to: Optional[str] = None
    created_at: datetime.datetime


class TaskAssign(BaseModel):
    assigned_to: Optional[str] = None  # None un-assigns


# ---- Smart delegation ----


class DelegationSuggestion(BaseModel):
    task_id: int
    title: str
    suggested_to: str
    message: str
    message_source: Literal["foundry", "anthropic", "template"]


# ---- Stress ----


class ExpressionScores(BaseModel):
    neutral: float = Field(ge=0, le=1)
    happy: float = Field(ge=0, le=1)
    sad: float = Field(ge=0, le=1)
    angry: float = Field(ge=0, le=1)
    fearful: float = Field(ge=0, le=1)
    disgusted: float = Field(ge=0, le=1)
    surprised: float = Field(ge=0, le=1)


class StressReadingCreate(BaseModel):
    source: Literal["rppg", "manual", "checkin", "expression"]
    heart_rate_bpm: Optional[float] = None
    respiration_rate_bpm: Optional[float] = None
    signal_quality: Optional[float] = Field(default=None, ge=0, le=1)
    self_reported_stress: Optional[int] = Field(default=None, ge=1, le=10)
    expression: Optional[ExpressionScores] = None  # required when source == expression


class StressReading(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    heart_rate_bpm: Optional[float] = None
    respiration_rate_bpm: Optional[float] = None
    signal_quality: Optional[float] = None
    self_reported_stress: Optional[int] = None
    expr_neutral: Optional[float] = None
    expr_happy: Optional[float] = None
    expr_sad: Optional[float] = None
    expr_angry: Optional[float] = None
    expr_fearful: Optional[float] = None
    expr_disgusted: Optional[float] = None
    expr_surprised: Optional[float] = None
    stress_score: float
    created_at: datetime.datetime


# ---- Stress trends ----


class StressTrendPoint(BaseModel):
    date: datetime.date
    avg_stress_score: float
    count: int


# ---- Threshold / AI brain ----


class ThresholdResult(BaseModel):
    intervene: bool
    combined_score: float
    behavioral_score: float
    physiological_score: float
    reasoning: str
    reasoning_source: Literal["foundry", "anthropic", "rule"]


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
    guidance_source: Literal["llm", "rule"] = "rule"


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


# ---- Daily check-in ----


class CheckinCreate(BaseModel):
    mood: int = Field(ge=1, le=4)  # 1 Good, 2 Okay, 3 Drained, 4 Barely holding on
    hours_slept: float = Field(ge=0, le=24)
    care_hours: float = Field(ge=0, le=24)
    had_me_time: bool


class CheckinOut(BaseModel):
    stress_score: float  # 0-1, for internal/API consistency with other stress readings
    stress_score_display: int  # 0-100, for UI display per spec
    reading: StressReading


class BurnoutRisk(BaseModel):
    level: Literal["low", "moderate", "high"]
    avg_stress_score: Optional[float] = None
    days_of_data: int
    suggestions: list[str]


# ---- Journal ----


class JournalEntryCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    mood: Optional[int] = Field(default=None, ge=1, le=5)


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    mood: Optional[int] = None
    created_at: datetime.datetime


class JournalSummary(BaseModel):
    summary: str
    source: Literal["foundry", "anthropic", "template"]
    entry_count: int


class EmotionAnalysis(BaseModel):
    happy: int = Field(ge=0, le=100)
    sad: int = Field(ge=0, le=100)
    low_mood: int = Field(ge=0, le=100)  # descriptive tone signal, not a diagnosis
    summary: str
    source: Literal["foundry", "anthropic", "template", "unavailable"]
    entry_count: int


# ---- AI Companion ----


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime.datetime


class ChatReply(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    source: Literal["foundry", "anthropic", "template", "rule"]


# ---- Resource Finder ----


class Resource(BaseModel):
    name: str
    description: str
    contact: str
    region: str
    category: str