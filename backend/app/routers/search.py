from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.deps import get_current_active_user, get_db
from ..models import User
from ..schemas.base import SearchResponse
from ..utils.search import search_everywhere

router = APIRouter()


@router.get("", response_model=SearchResponse)
def search(
    query: str = Query(min_length=2),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Search across all entities. Requires authentication."""
    customers, trainers, trainings = search_everywhere(db, query)
    return SearchResponse(customers=customers, trainers=trainers, trainings=trainings)
