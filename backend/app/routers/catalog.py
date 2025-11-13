from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import TrainingCatalogEntry
from ..schemas.base import TrainingCatalogCreate, TrainingCatalogRead

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[TrainingCatalogRead])
def list_entries(db: Session = Depends(get_db)):
    return db.query(TrainingCatalogEntry).order_by(TrainingCatalogEntry.title).all()


@router.post("", response_model=TrainingCatalogRead)
def create_entry(payload: TrainingCatalogCreate, db: Session = Depends(get_db)):
    entry = TrainingCatalogEntry(**payload.dict())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=TrainingCatalogRead)
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(TrainingCatalogEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.put("/{entry_id}", response_model=TrainingCatalogRead)
def update_entry(entry_id: int, payload: TrainingCatalogCreate, db: Session = Depends(get_db)):
    entry = db.get(TrainingCatalogEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    for key, value in payload.dict().items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(TrainingCatalogEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"status": "deleted"}
