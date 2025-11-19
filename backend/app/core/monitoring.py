"""Monitoring and health check utilities."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_git_revision() -> str:
    """Get the current Git revision hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_git_branch() -> str:
    """Get the current Git branch."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def check_database_health(db: Session) -> dict[str, Any]:
    """Check database connection health."""
    try:
        # Simple query to check database connectivity
        result = db.execute(text("SELECT 1"))
        result.scalar()

        # Try to get database version
        try:
            version_result = db.execute(text("SELECT version()"))
            db_version = version_result.scalar()
        except Exception:
            db_version = "unknown"

        return {
            "status": "healthy",
            "connected": True,
            "version": db_version,
            "response_time_ms": 0  # Could add timing here
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e)
        }


def get_system_info() -> dict[str, Any]:
    """Get system information."""
    return {
        "python_version": os.sys.version,
        "platform": os.sys.platform,
        "cwd": os.getcwd(),
        "pid": os.getpid(),
    }


def get_version_info() -> dict[str, Any]:
    """Get application version information."""
    return {
        "git_commit": get_git_revision(),
        "git_branch": get_git_branch(),
        "build_date": datetime.utcnow().isoformat(),
        "version": "1.0.0",  # Could read from pyproject.toml
    }
