import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import delegation, models, reflection, schemas, scoring
from .database import Base, engine, get_db

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Group-26 Caregiver Support API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


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
    return scoring.breathing_pace(physiological)


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
