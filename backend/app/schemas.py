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


class StressReadingCreate(BaseModel):
    source: Literal["rppg", "manual", "checkin"]
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


# ---- Stress trends ----


class StressTrendPoint(BaseModel):
    date: datetime.date
    avg_stress_score: float
    count: int


# ---- Digital Twin: predictive stress forecast ----


class StressForecastPoint(BaseModel):
    date: datetime.date
    predicted_score: float  # 0-1
    predicted_display: int  # 0-100, for UI
    lower: float  # confidence band, 0-1
    upper: float


class StressForecast(BaseModel):
    horizon_days: int
    days_of_history: int
    trend: Literal["rising", "falling", "steady"]
    points: list[StressForecastPoint]
    main_driver: Optional[str] = None  # e.g. "long caregiving hours"
    narrative: str
    narrative_source: Literal["foundry", "anthropic", "template"]


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


# ---- Emotion analysis ----


class EmotionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class EmotionResult(BaseModel):
    emotion: str
    stress: Literal["low", "moderate", "high"]
    burnout_risk: Literal["low", "moderate", "high"]
    source: Literal["foundry", "anthropic", "rule"]


# ---- Weekly summary ----


class WeeklySummary(BaseModel):
    summary: str
    source: Literal["foundry", "anthropic", "template"]
    days_of_data: int
    sleep_trend: Literal["up", "down", "flat"]
    stress_trend: Literal["up", "down", "flat"]
    mood_trend: Literal["up", "down", "flat"]
    main_driver: Optional[str] = None


# ---- Daily suggestions ----


class DailySuggestions(BaseModel):
    suggestions: list[str]
    based_on_checkin: bool


# ---- Resource Finder ----


class Resource(BaseModel):
    name: str
    description: str
    contact: str
    region: str
    category: str