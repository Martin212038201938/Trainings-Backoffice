from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Brand
from ..schemas.base import BrandCreate, BrandRead

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[BrandRead])
def list_brands(db: Session = Depends(get_db)):
    return db.query(Brand).all()


@router.post("", response_model=BrandRead)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    brand = Brand(**payload.dict())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


@router.get("/{brand_id}", response_model=BrandRead)
def get_brand(brand_id: int, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.put("/{brand_id}", response_model=BrandRead)
def update_brand(brand_id: int, payload: BrandCreate, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    for key, value in payload.dict().items():
        setattr(brand, key, value)
    db.commit()
    db.refresh(brand)
    return brand


@router.delete("/{brand_id}")
def delete_brand(brand_id: int, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    db.delete(brand)
    db.commit()
    return {"status": "deleted"}
