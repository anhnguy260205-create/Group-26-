import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import (
    capforecast,
    capprogress,
    companion,
    outlook,
    delegation,
    emotion,
    journal,
    llm,
    models,
    recharge,
    reflection,
    resources,
    schemas,
    scoring,
    suggestions,
    twin,
    weekly,
)
from .database import Base, engine, get_db

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Group-26 Caregiver Support API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness plus which LLM tier maps to which deployment, so a misrouted demo is
    diagnosable without reading the environment by hand."""
    return {"status": "ok", "llm": llm.routing()}


# ---------------------------------------------------------------------------
# Care dashboard
# ---------------------------------------------------------------------------


@app.get("/tasks", response_model=list[schemas.Task])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(models.Task).order_by(models.Task.done, models.Task.due_at).all()


@app.post("/tasks", response_model=schemas.Task)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    db_task = models.Task(title=task.title, kind=task.kind, due_at=task.due_at)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.post("/tasks/{task_id}/toggle", response_model=schemas.Task)
def toggle_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.done = not task.done
    task.done_at = datetime.datetime.utcnow() if task.done else None
    db.commit()
    db.refresh(task)
    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Smart task delegation (bonus)
# ---------------------------------------------------------------------------


@app.post("/tasks/{task_id}/assign", response_model=schemas.Task)
def assign_task(task_id: int, body: schemas.TaskAssign, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.assigned_to = body.assigned_to
    db.commit()
    db.refresh(task)
    return task


@app.get("/delegation/suggest", response_model=list[schemas.DelegationSuggestion])
def suggest_delegation(db: Session = Depends(get_db)):
    """AI-suggested tasks to hand off to family, each with a ready-to-send ask."""
    return delegation.suggest(db)


# ---------------------------------------------------------------------------
# Stress sensing
# ---------------------------------------------------------------------------


@app.post("/stress", response_model=schemas.StressReading)
def ingest_stress_reading(reading: schemas.StressReadingCreate, db: Session = Depends(get_db)):
    if reading.source == "rppg":
        if reading.heart_rate_bpm is None:
            raise HTTPException(status_code=422, detail="heart_rate_bpm required for rppg readings")
        stress_score = scoring.heart_rate_to_stress_score(
            reading.heart_rate_bpm, reading.signal_quality
        )
    elif reading.source == "expression":
        if reading.expression is None:
            raise HTTPException(status_code=422, detail="expression required for expression readings")
        stress_score = scoring.expression_to_stress_score(reading.expression.model_dump())
    else:
        if reading.self_reported_stress is None:
            raise HTTPException(
                status_code=422, detail="self_reported_stress required for manual readings"
            )
        stress_score = scoring.self_report_to_stress_score(reading.self_reported_stress)

    db_reading = models.StressReading(
        source=reading.source,
        heart_rate_bpm=reading.heart_rate_bpm,
        respiration_rate_bpm=reading.respiration_rate_bpm,
        signal_quality=reading.signal_quality,
        self_reported_stress=reading.self_reported_stress,
        stress_score=stress_score,
    )
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


@app.get("/stress", response_model=list[schemas.StressReading])
def list_stress_readings(limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(models.StressReading)
        .order_by(models.StressReading.created_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/stress/trends", response_model=list[schemas.StressTrendPoint])
def stress_trends(days: int = 7, db: Session = Depends(get_db)):
    """Daily average stress score over the last `days` — powers the trends chart."""
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    readings = (
        db.query(models.StressReading)
        .filter(models.StressReading.created_at >= since)
        .order_by(models.StressReading.created_at)
        .all()
    )
    buckets: dict[datetime.date, list[float]] = {}
    for r in readings:
        buckets.setdefault(r.created_at.date(), []).append(r.stress_score)
    return [
        schemas.StressTrendPoint(
            date=day,
            avg_stress_score=round(sum(scores) / len(scores), 3),
            count=len(scores),
        )
        for day, scores in sorted(buckets.items())
    ]


@app.get("/stress/burnout-risk", response_model=schemas.BurnoutRisk)
def burnout_risk(days: int = 7, db: Session = Depends(get_db)):
    """Current-state risk band from sustained recent patterns — not a forecast."""
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    readings = (
        db.query(models.StressReading)
        .filter(models.StressReading.created_at >= since)
        .order_by(models.StressReading.created_at)
        .all()
    )
    scores = [r.stress_score for r in readings]
    day_count = len({r.created_at.date() for r in readings})
    level = scoring.burnout_risk_level(scores)
    return schemas.BurnoutRisk(
        level=level,
        avg_stress_score=round(sum(scores) / len(scores), 3) if scores else None,
        days_of_data=day_count,
        suggestions=scoring.RISK_SUGGESTIONS[level],
    )


@app.get("/stress/forecast", response_model=schemas.StressForecast)
def stress_forecast(days: int = 3, db: Session = Depends(get_db)):
    """Caregiver Digital Twin: forecast the next `days` of stress + name the driver."""
    horizon = max(1, min(days, 7))
    return twin.forecast_stress(db, horizon_days=horizon)


@app.get("/summary/weekly", response_model=schemas.WeeklySummary)
def weekly_summary(db: Session = Depends(get_db)):
    """Cross-metric AI weekly summary (sleep/stress/mood trends + driver)."""
    return weekly.generate(db)


@app.get("/suggestions/daily", response_model=schemas.DailySuggestions)
def daily_suggestions(db: Session = Depends(get_db)):
    """Small, non-medical daily nudges tailored to the latest check-in."""
    return suggestions.daily(db)


@app.post("/emotion", response_model=schemas.EmotionResult)
def analyze_emotion(body: schemas.EmotionRequest):
    """Emotion / stress / burnout labels for a journal entry or chat message."""
    return emotion.analyze(body.text)


# ---------------------------------------------------------------------------
# Daily check-in
# ---------------------------------------------------------------------------


@app.post("/checkin", response_model=schemas.CheckinOut)
def submit_checkin(body: schemas.CheckinCreate, db: Session = Depends(get_db)):
    """Score a Daily Check-in into a Capacity reading (journal- and face-aware via LLM, with
    a rule fallback), persist it, and mirror it to a StressReading so the Digital Twin,
    burnout dashboard and intervention threshold keep working off one signal."""
    face_stress = scoring.latest_face_stress(db)

    result = scoring.compute_capacity(
        body.journal, body.mood, body.sleep, body.energy, body.night_care, body.free_time, face_stress
    )

    checkin = models.Checkin(
        journal=body.journal or None,
        mood=body.mood, sleep=body.sleep, energy=body.energy,
        night_care=body.night_care, free_time=body.free_time,
        face_stress=face_stress,
        capacity_score=result["capacity"], main_driver=result["main_driver"],
        reason=result["reason"], source=result["source"],
    )
    db.add(checkin)

    # Mirror to the shared stress signal (low capacity == high stress) so the existing twin
    # and dashboard, which read StressReading, still function.
    db.add(models.StressReading(source="checkin", stress_score=round(1 - result["capacity"] / 100, 3)))

    db.commit()
    db.refresh(checkin)
    return checkin


@app.get("/checkin/latest", response_model=schemas.CheckinOut)
def latest_checkin(db: Session = Depends(get_db)):
    checkin = db.query(models.Checkin).order_by(models.Checkin.created_at.desc()).first()
    if checkin is None:
        raise HTTPException(status_code=404, detail="No check-in yet")
    return checkin


@app.get("/capacity/forecast", response_model=schemas.CapacityForecast)
def capacity_forecast(days: int = capforecast.WINDOW_DAYS, db: Session = Depends(get_db)):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    checkins = (
        db.query(models.Checkin)
        .filter(models.Checkin.created_at >= since)
        .order_by(models.Checkin.created_at)
        .all()
    )
    return schemas.CapacityForecast(**capforecast.analyze(checkins))


@app.get("/capacity/outlook", response_model=schemas.CapacityOutlook)
def capacity_outlook(db: Session = Depends(get_db)):
    """Prediction view for Understand Me: the causes behind a persistent low state and the
    likely consequences if the pattern continues (supportive, non-clinical)."""
    return schemas.CapacityOutlook(**outlook.analyze(db))


@app.get("/recharge/today", response_model=list[schemas.RechargeActionOut])
def recharge_today(db: Session = Depends(get_db)):
    """Today's recovery actions, chosen from the *cause* of the capacity drop (the check-in's
    main driver) and scaled to how much capacity is actually left."""
    latest = db.query(models.Checkin).order_by(models.Checkin.created_at.desc()).first()
    driver = latest.main_driver if latest else None
    capacity = latest.capacity_score if latest else None
    plan = recharge.plan_for(driver, capacity)
    actions = recharge.actions_for_today(db, driver, capacity)
    return [recharge.to_dict(a, why=plan["why"]) for a in actions]


@app.post("/recharge/{action_id}/status", response_model=schemas.RechargeActionOut)
def set_recharge_status(action_id: int, body: schemas.RechargeStatusUpdate, db: Session = Depends(get_db)):
    action = db.query(models.RechargeAction).filter(models.RechargeAction.id == action_id).first()
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    action.status = body.status
    action.completed_at = datetime.datetime.utcnow() if body.status == "done" else None
    db.commit()
    db.refresh(action)
    latest = db.query(models.Checkin).order_by(models.Checkin.created_at.desc()).first()
    plan = recharge.plan_for(
        latest.main_driver if latest else None, latest.capacity_score if latest else None
    )
    return recharge.to_dict(action, why=plan["why"])


@app.get("/progress", response_model=schemas.ProgressOut)
def progress_evidence(db: Session = Depends(get_db)):
    return schemas.ProgressOut(**capprogress.build(db))


@app.get("/companion/opening", response_model=schemas.OpeningLine)
def companion_opening(db: Session = Depends(get_db)):
    """Proactive opening. Carries the register the companion chose and, when capacity is low,
    a suggested action that *reduces* what's being asked of the caregiver."""
    return schemas.OpeningLine(**companion.opening_line(db))


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


@app.post("/journal", response_model=schemas.JournalEntryOut)
def create_journal_entry(body: schemas.JournalEntryCreate, db: Session = Depends(get_db)):
    entry = models.JournalEntry(text=body.text, mood=body.mood)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@app.get("/journal", response_model=list[schemas.JournalEntryOut])
def list_journal_entries(limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(models.JournalEntry)
        .order_by(models.JournalEntry.created_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/journal/summary", response_model=schemas.JournalSummary)
def journal_summary(db: Session = Depends(get_db)):
    entries = list(reversed(db.query(models.JournalEntry).order_by(models.JournalEntry.created_at.desc()).limit(journal.SUMMARY_WINDOW).all()))
    summary, source = journal.generate_summary(entries)
    return schemas.JournalSummary(summary=summary, source=source, entry_count=len(entries))


# ---------------------------------------------------------------------------
# AI Companion
# ---------------------------------------------------------------------------


@app.post("/companion/chat", response_model=schemas.ChatReply)
def companion_chat(body: schemas.ChatMessageCreate, db: Session = Depends(get_db)):
    user_message = models.ChatMessage(role="user", content=body.content)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    text, source = companion.reply(db, body.content)

    assistant_message = models.ChatMessage(role="assistant", content=text)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return schemas.ChatReply(
        user_message=user_message, assistant_message=assistant_message, source=source
    )


@app.get("/companion/messages", response_model=list[schemas.ChatMessageOut])
def companion_messages(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(models.ChatMessage)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


# ---------------------------------------------------------------------------
# Resource Finder
# ---------------------------------------------------------------------------


@app.get("/resources", response_model=list[schemas.Resource])
def get_resources(region: str | None = None):
    return resources.list_resources(region)


# ---------------------------------------------------------------------------
# AI brain: threshold detection
# ---------------------------------------------------------------------------


@app.get("/threshold/check", response_model=schemas.ThresholdResult)
def threshold_check(db: Session = Depends(get_db)):
    decision = scoring.check_threshold(db)
    return schemas.ThresholdResult(
        intervene=decision.intervene,
        combined_score=decision.combined_score,
        behavioral_score=decision.behavioral_score,
        physiological_score=decision.physiological_score,
        reasoning=decision.reasoning,
        reasoning_source=decision.reasoning_source,
    )


# ---------------------------------------------------------------------------
# Proactive intervention / guided recovery
# ---------------------------------------------------------------------------


@app.post("/intervention/start", response_model=schemas.SessionOut)
def start_session(body: schemas.SessionStart, db: Session = Depends(get_db)):
    reading = scoring.latest_reading(db)
    session = models.CareSession(
        trigger_score=body.trigger_score,
        trigger_reasoning=body.trigger_reasoning,
        start_stress_score=reading.stress_score if reading else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.get("/intervention/{session_id}/pace", response_model=schemas.BreathingPace)
def get_pace(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.CareSession).filter(models.CareSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    reading = scoring.latest_reading(db)
    physiological = scoring.physiological_score(reading)
    respiration_rate = reading.respiration_rate_bpm if reading else None
    pace = scoring.breathing_pace(physiological, respiration_rate)

    if respiration_rate is not None:
        trend = scoring.recent_stress_trend(db)
        llm_guidance = scoring.generate_breathing_guidance(physiological, respiration_rate, trend)
        if llm_guidance:
            pace["guidance"] = llm_guidance
            pace["guidance_source"] = "llm"

    return pace


@app.post("/intervention/{session_id}/end", response_model=schemas.SessionOut)
def end_session(session_id: int, body: schemas.SessionEnd, db: Session = Depends(get_db)):
    session = db.query(models.CareSession).filter(models.CareSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    reading = scoring.latest_reading(db)
    session.end_stress_score = (
        body.end_stress_score if body.end_stress_score is not None
        else (reading.stress_score if reading else None)
    )
    session.ended_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Gentle reflection
# ---------------------------------------------------------------------------


@app.post("/reflection/{session_id}", response_model=schemas.ReflectionOut)
def generate_reflection(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.CareSession).filter(models.CareSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = db.query(models.Reflection).filter(models.Reflection.session_id == session_id).first()
    if existing:
        return existing

    message, generated_by = reflection.generate(session)
    db_reflection = models.Reflection(
        session_id=session_id, message=message, generated_by=generated_by
    )
    db.add(db_reflection)
    db.commit()
    db.refresh(db_reflection)
    return db_reflection