from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import ActivityLog, Brand, Customer, Trainer, Training, TrainingCatalogEntry, TrainingTask
from ..schemas.base import TrainingCreate, TrainingRead
from ..services import checklist

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _log_activity(db: Session, training: Training, message: str, actor: str = "system"):
    log = ActivityLog(training=training, message=message, created_by=actor)
    db.add(log)


@router.get("", response_model=list[TrainingRead])
def list_trainings(
    brand_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Training)
    if brand_id:
        query = query.filter(Training.brand_id == brand_id)
    if status:
        query = query.filter(Training.status == status)
    return query.order_by(Training.start_date.desc().nullslast()).all()


@router.post("", response_model=TrainingRead)
def create_training(payload: TrainingCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, payload.customer_id)
    brand = db.get(Brand, payload.brand_id)
    if not customer or not brand:
        raise HTTPException(status_code=400, detail="Invalid customer or brand")

    training = Training(**payload.dict(exclude={"tasks", "generate_checklist"}))
    db.add(training)

    if payload.generate_checklist and not payload.tasks:
        for task in checklist.generate_tasks(training):
            training.tasks.append(task)
    else:
        for task_payload in payload.tasks:
            training.tasks.append(TrainingTask(**task_payload.dict()))

    _log_activity(db, training, "Training angelegt")
    db.commit()
    db.refresh(training)
    return training


@router.get("/{training_id}", response_model=TrainingRead)
def get_training(training_id: int, db: Session = Depends(get_db)):
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return training


@router.put("/{training_id}", response_model=TrainingRead)
def update_training(training_id: int, payload: TrainingCreate, db: Session = Depends(get_db)):
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    for key, value in payload.dict(exclude={"tasks", "generate_checklist"}).items():
        setattr(training, key, value)
    if payload.tasks:
        training.tasks = [TrainingTask(**task.dict()) for task in payload.tasks]
    elif payload.generate_checklist:
        training.tasks = checklist.generate_tasks(training)
    _log_activity(db, training, "Training aktualisiert")
    db.commit()
    db.refresh(training)
    return training


@router.post("/{training_id}/status")
def update_status(training_id: int, status: str, db: Session = Depends(get_db)):
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    training.status = status
    _log_activity(db, training, f"Status auf {status} gesetzt")
    db.commit()
    return {"status": status}


@router.delete("/{training_id}")
def delete_training(training_id: int, db: Session = Depends(get_db)):
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    db.delete(training)
    db.commit()
    return {"status": "deleted"}
