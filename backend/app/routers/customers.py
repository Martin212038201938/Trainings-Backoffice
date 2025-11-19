from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import get_current_active_user, get_db, require_backoffice
from ..database import SessionLocal
from ..models import Brand, Customer, User
from ..schemas.base import CustomerCreate, CustomerRead
from ..services.ai import summarize_notes

router = APIRouter()


@router.get("", response_model=list[CustomerRead])
def list_customers(
    brand_id: int | None = Query(default=None),
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Customer)
    if brand_id:
        query = query.filter(Customer.brands.any(Brand.id == brand_id))
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(func.lower(Customer.company_name).like(like))
    return query.order_by(Customer.company_name).all()


@router.post("", response_model=CustomerRead)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    customer = Customer(**payload.dict(exclude={"brand_ids"}))
    if payload.brand_ids:
        brands = db.query(Brand).filter(Brand.id.in_(payload.brand_ids)).all()
        customer.brands = brands
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/summaries")
def summarize_customer_notes(
    notes: str,
    current_user: User = Depends(get_current_active_user),
):
    return {"summary": summarize_notes(notes)}


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int,
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
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
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(customer)
    db.commit()
    return {"status": "deleted"}
