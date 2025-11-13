from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Brand, Trainer
from ..schemas.base import TrainerCreate, TrainerRead

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[TrainerRead])
def list_trainers(search: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Trainer)
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(
            (func.lower(Trainer.last_name).like(like))
            | (func.lower(Trainer.first_name).like(like))
            | (func.lower(Trainer.tags).like(like))
            | (func.lower(Trainer.email).like(like))
        )
    return query.order_by(Trainer.last_name).all()


@router.post("", response_model=TrainerRead)
def create_trainer(payload: TrainerCreate, db: Session = Depends(get_db)):
    trainer = Trainer(**payload.dict(exclude={"brand_ids"}))
    if payload.brand_ids:
        trainer.brands = db.query(Brand).filter(Brand.id.in_(payload.brand_ids)).all()
    db.add(trainer)
    db.commit()
    db.refresh(trainer)
    return trainer


@router.get("/{trainer_id}", response_model=TrainerRead)
def get_trainer(trainer_id: int, db: Session = Depends(get_db)):
    trainer = db.get(Trainer, trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return trainer


@router.put("/{trainer_id}", response_model=TrainerRead)
def update_trainer(trainer_id: int, payload: TrainerCreate, db: Session = Depends(get_db)):
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
def delete_trainer(trainer_id: int, db: Session = Depends(get_db)):
    trainer = db.get(Trainer, trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    db.delete(trainer)
    db.commit()
    return {"status": "deleted"}
