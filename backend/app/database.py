from __future__ import annotations

import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from .config import settings

logger = logging.getLogger(__name__)

# Configure database connection arguments based on database type
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create engine with connection pooling for production
try:
    if settings.database_url.startswith("sqlite"):
        engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            echo=False
        )
    else:
        # PostgreSQL or other databases
        engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=False
        )
    logger.info(f"Database engine created successfully for {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'sqlite'}")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


@contextmanager
def get_session() -> Session:
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
