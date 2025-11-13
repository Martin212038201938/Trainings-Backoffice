from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..schemas.base import SearchResponse
from ..utils.search import search_everywhere

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=SearchResponse)
def search(query: str = Query(min_length=2), db: Session = Depends(get_db)):
    customers, trainers, trainings = search_everywhere(db, query)
    return SearchResponse(customers=customers, trainers=trainers, trainings=trainings)
