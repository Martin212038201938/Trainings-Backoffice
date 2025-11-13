from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine
from .models import ActivityLog, Brand, Customer, EmailTemplate, Trainer, Training, TrainingCatalogEntry, TrainingTask
from .routers import brands, catalog, customers, search, tasks, trainers, trainings

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def db_session_middleware(request, call_next):
    response = await call_next(request)
    return response


def get_db():  # Dependency for routers
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name}


app.include_router(brands.router, prefix="/brands", tags=["brands"])
app.include_router(customers.router, prefix="/customers", tags=["customers"])
app.include_router(trainers.router, prefix="/trainers", tags=["trainers"])
app.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
app.include_router(trainings.router, prefix="/trainings", tags=["trainings"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(search.router, prefix="/search", tags=["search"])
