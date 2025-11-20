from __future__ import annotations

import logging
import sys
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

from .config import settings
from .database import Base, SessionLocal, engine
from .models import ActivityLog, Brand, Customer, EmailTemplate, Trainer, Training, TrainingCatalogEntry, TrainingTask, User
from .routers import auth, brands, catalog, customers, search, tasks, trainers, trainings

# Create tables with error handling
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified successfully")
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")
    # Don't raise - allow app to start for health checks

app = FastAPI(
    title=settings.app_name,
    description="Trainings Backoffice API with Authentication",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def db_session_middleware(request, call_next):
    response = await call_next(request)
    return response


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add security headers to responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def get_db():  # Dependency for routers
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    """
    Root endpoint - returns basic application info.
    """
    return {
        "app": settings.app_name,
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/ping")
async def ping():
    """
    Simple ping endpoint - always returns pong.
    Use this for basic availability checks.
    """
    return {"ping": "pong", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health")
async def health_check():
    """
    Health check endpoint with database connectivity test.

    Returns:
        Health status including database connectivity
    """
    from .core.monitoring import check_database_health

    # Try to get a database session
    db_health = {"status": "unknown", "connected": False}
    try:
        db = SessionLocal()
        try:
            db_health = check_database_health(db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_health = {
            "status": "unhealthy",
            "connected": False,
            "error": str(e)
        }

    return {
        "status": "ok" if db_health.get("connected") else "degraded",
        "app": settings.app_name,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "database": db_health
    }


@app.get("/version")
async def version_info():
    """
    Version information endpoint.

    Returns:
        Application version and build information
    """
    from .core.monitoring import get_version_info

    return get_version_info()


# Authentication routes (no auth required)
app.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Protected routes
app.include_router(brands.router, prefix="/brands", tags=["brands"])
app.include_router(customers.router, prefix="/customers", tags=["customers"])
app.include_router(trainers.router, prefix="/trainers", tags=["trainers"])
app.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
app.include_router(trainings.router, prefix="/trainings", tags=["trainings"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(search.router, prefix="/search", tags=["search"])

# Database credentials updated with correct password - Deployment #8
