from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.deps import get_current_active_user, get_db, require_backoffice
from ..database import SessionLocal
from ..models import ActivityLog, Brand, Customer, Trainer, Training, TrainingCatalogEntry, TrainingTask, User, UserRole
from ..schemas.base import TrainingCreate, TrainingRead
from ..services import checklist

router = APIRouter()


def _log_activity(db: Session, training: Training, message: str, actor: str = "system"):
    log = ActivityLog(training=training, message=message, created_by=actor)
    db.add(log)


@router.get("", response_model=list[TrainingRead])
def list_trainings(
    brand_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List trainings. Trainers can only see their own trainings."""
    query = db.query(Training)

    # Trainers can only see their own trainings
    if UserRole(current_user.role) == UserRole.TRAINER:
        # Find trainer associated with this user (by email matching)
        trainer = db.query(Trainer).filter(Trainer.email == current_user.email).first()
        if trainer:
            query = query.filter(Training.trainer_id == trainer.id)
        else:
            # If no trainer found, return empty list
            return []

    if brand_id:
        query = query.filter(Training.brand_id == brand_id)
    if status:
        query = query.filter(Training.status == status)
    return query.order_by(Training.start_date.desc().nullslast()).all()


@router.post("", response_model=TrainingRead)
def create_training(
    payload: TrainingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Create a new training. Requires backoffice or admin role."""
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

    _log_activity(db, training, f"Training angelegt von {current_user.username}", current_user.username)
    db.commit()
    db.refresh(training)
    return training


@router.get("/{training_id}", response_model=TrainingRead)
def get_training(
    training_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific training. Trainers can only see their own trainings."""
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # Trainers can only see their own trainings
    if UserRole(current_user.role) == UserRole.TRAINER:
        trainer = db.query(Trainer).filter(Trainer.email == current_user.email).first()
        if not trainer or training.trainer_id != trainer.id:
            raise HTTPException(status_code=403, detail="Access denied")

    return training


@router.put("/{training_id}", response_model=TrainingRead)
def update_training(
    training_id: int,
    payload: TrainingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Update a training. Requires backoffice or admin role."""
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    for key, value in payload.dict(exclude={"tasks", "generate_checklist"}).items():
        setattr(training, key, value)
    if payload.tasks:
        training.tasks = [TrainingTask(**task.dict()) for task in payload.tasks]
    elif payload.generate_checklist:
        training.tasks = checklist.generate_tasks(training)
    _log_activity(db, training, f"Training aktualisiert von {current_user.username}", current_user.username)
    db.commit()
    db.refresh(training)
    return training


@router.post("/{training_id}/status")
def update_status(
    training_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Update training status. Requires backoffice or admin role."""
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    training.status = status
    _log_activity(db, training, f"Status auf {status} gesetzt von {current_user.username}", current_user.username)
    db.commit()
    return {"status": status}


@router.delete("/{training_id}")
def delete_training(
    training_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Delete a training. Requires backoffice or admin role."""
    training = db.get(Training, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    db.delete(training)
    db.commit()
    return {"status": "deleted"}
