from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Brand, Customer
from ..schemas.base import CustomerCreate, CustomerRead
from ..services.ai import summarize_notes

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[CustomerRead])
def list_customers(
    brand_id: int | None = Query(default=None),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Customer)
    if brand_id:
        query = query.filter(Customer.brands.any(Brand.id == brand_id))
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(func.lower(Customer.company_name).like(like))
    return query.order_by(Customer.company_name).all()


@router.post("", response_model=CustomerRead)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = Customer(**payload.dict(exclude={"brand_ids"}))
    if payload.brand_ids:
        brands = db.query(Brand).filter(Brand.id.in_(payload.brand_ids)).all()
        customer.brands = brands
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/summaries")
def summarize_customer_notes(notes: str):
    return {"summary": summarize_notes(notes)}


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(customer_id: int, payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in payload.dict(exclude={"brand_ids"}).items():
        setattr(customer, key, value)
    if payload.brand_ids:
        customer.brands = db.query(Brand).filter(Brand.id.in_(payload.brand_ids)).all()
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(customer)
    db.commit()
    return {"status": "deleted"}
