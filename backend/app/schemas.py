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
    journal: str = Field(default="", max_length=500)
    mood: int = Field(ge=0, le=10)
    sleep: int = Field(ge=0, le=10)
    energy: int = Field(ge=0, le=10)
    night_care: int = Field(ge=0, le=10)  # nighttime caregiving burden
    free_time: int = Field(ge=0, le=10)


class CheckinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    journal: Optional[str] = None
    mood: int
    sleep: int
    energy: int
    night_care: int
    free_time: int
    face_stress: Optional[float] = None  # 0-1 fused facial-tension reading, if one was fresh
    capacity_score: int  # 0-100, higher = more capacity left
    main_driver: str
    reason: str
    source: Literal["foundry", "anthropic", "rule"]
    created_at: datetime.datetime


class CapacityPoint(BaseModel):
    date: datetime.date
    capacity: int
    driver: str


class CapacityForecast(BaseModel):
    points: list[CapacityPoint]
    days_of_data: int
    avg_capacity: Optional[int] = None
    trend: Literal["declining", "steady", "improving"]
    consecutive_decline_days: int
    recurring_driver: Optional[str] = None
    predicted_capacity: Optional[int] = None
    risk: Literal["low", "moderate", "high"]
    forecast: str
    suggestions: list[str]
    source: Literal["foundry", "anthropic", "rule"]


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


# ---- Recharge & Reconnect ----


class RechargeActionOut(BaseModel):
    id: int
    kind: str
    label: str
    detail: str
    reconnect: bool
    driver: Optional[str] = None
    status: Literal["pending", "done", "skipped"]


class RechargeStatusUpdate(BaseModel):
    status: Literal["done", "skipped", "pending"]


# ---- Progress / Evidence ----


class ProgressOut(BaseModel):
    yesterday: datetime.date
    done_actions: list[str]
    capacity_yesterday: Optional[int] = None
    capacity_today: Optional[int] = None
    capacity_change: Optional[int] = None
    has_evidence: bool
    evidence: str


# ---- Copilot opening ----


class OpeningLine(BaseModel):
    opening: str
    source: Literal["foundry", "anthropic", "rule"]


# ---- Resource Finder ----


class Resource(BaseModel):
    name: str
    description: str
    contact: str
    region: str
    category: str