from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import get_current_active_user, get_db, require_backoffice
from ..models import TrainingTask, User
from ..schemas.base import TrainingTaskCreate, TrainingTaskRead

router = APIRouter()


@router.get("", response_model=list[TrainingTaskRead])
def list_tasks(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all tasks."""
    query = db.query(TrainingTask)
    if status:
        query = query.filter(TrainingTask.status == status)
    return query.order_by(TrainingTask.due_date).all()


@router.post("", response_model=TrainingTaskRead)
def create_task(
    payload: TrainingTaskCreate,
    training_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Create a new task. Requires backoffice or admin role."""
    task = TrainingTask(**payload.dict(), training_id=training_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=TrainingTaskRead)
def update_task(
    task_id: int,
    payload: TrainingTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Update a task. Requires backoffice or admin role."""
    task = db.get(TrainingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in payload.dict().items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/complete", response_model=TrainingTaskRead)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Complete a task. Requires backoffice or admin role."""
    task = db.get(TrainingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "done"
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """Delete a task. Requires backoffice or admin role."""
    task = db.get(TrainingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"status": "deleted"}
