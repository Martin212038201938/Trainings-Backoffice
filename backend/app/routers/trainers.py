from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import get_current_active_user, get_db, require_backoffice
from ..database import SessionLocal
from ..models import Brand, Trainer, Training, User
from ..models.core import TrainerApplication
from ..schemas.base import TrainerCreate, TrainerRead
from ..utils.search import escape_like_wildcards

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[TrainerRead])
def list_trainers(
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all trainers."""
    query = db.query(Trainer)
    if search:
        # Escape LIKE wildcards to prevent injection
        escaped_search = escape_like_wildcards(search.lower())
        like = f"%{escaped_search}%"
        query = query.filter(
            (func.lower(Trainer.last_name).like(like))
            | (func.lower(Trainer.first_name).like(like))
            | (func.lower(Trainer.tags).like(like))
            | (func.lower(Trainer.email).like(like))
        )
    return query.order_by(Trainer.last_name).all()


@router.post("", response_model=TrainerRead)
def create_trainer(
    payload: TrainerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Create a new trainer. Requires backoffice or admin role."""
    trainer = Trainer(**payload.dict(exclude={"brand_ids"}))
    if payload.brand_ids:
        trainer.brands = db.query(Brand).filter(Brand.id.in_(payload.brand_ids)).all()

    # Auto-link to user if exists with same email
    if trainer.email:
        user = db.query(User).filter(User.email == trainer.email).first()
        if user and not db.query(Trainer).filter(Trainer.user_id == user.id).first():
            trainer.user_id = user.id
            logger.info(f"Auto-linked trainer to user {user.id} by email {trainer.email}")

    db.add(trainer)
    db.commit()
    db.refresh(trainer)
    return trainer


@router.get("/{trainer_id}", response_model=TrainerRead)
def get_trainer(
    trainer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific trainer."""
    trainer = db.get(Trainer, trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return trainer


@router.put("/{trainer_id}", response_model=TrainerRead)
def update_trainer(
    trainer_id: int,
    payload: TrainerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Update a trainer. Requires backoffice or admin role."""
    trainer = db.get(Trainer, trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    for key, value in payload.dict(exclude={"brand_ids"}).items():
        setattr(trainer, key, value)
    if payload.brand_ids:
        trainer.brands = db.query(Brand).filter(Brand.id.in_(payload.brand_ids)).all()
    db.commit()
    db.refresh(trainer)
    return trainer


@router.delete("/{trainer_id}")
def delete_trainer(
    trainer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Delete a trainer. Requires backoffice or admin role."""
    trainer = db.get(Trainer, trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    db.delete(trainer)
    db.commit()
    return {"status": "deleted"}


@router.get("/{trainer_id}/applications")
def get_trainer_applications(
    trainer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Get all training applications for a specific trainer. Requires backoffice or admin role."""
    trainer = db.get(Trainer, trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    applications = (
        db.query(TrainerApplication)
        .filter(TrainerApplication.trainer_id == trainer_id)
        .order_by(TrainerApplication.created_at.desc())
        .all()
    )

    result = []
    for app in applications:
        training = db.get(Training, app.training_id)
        result.append({
            "id": app.id,
            "training_id": app.training_id,
            "training_title": training.title if training else None,
            "training_status": training.status if training else None,
            "status": app.status,
            "message": app.message,
            "proposed_rate": app.proposed_rate,
            "agreed_rate": training.trainer_daily_rate if training and app.status == "accepted" else None,
            "admin_notes": app.admin_notes,
            "created_at": app.created_at.isoformat() if app.created_at else None,
        })

    return result
