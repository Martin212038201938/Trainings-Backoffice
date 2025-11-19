#!/usr/bin/env python3
"""
Script to create the initial admin user.

Usage:
    python scripts/create_admin_user.py

Environment variables:
    ADMIN_USERNAME: Admin username (default: admin)
    ADMIN_EMAIL: Admin email (default: admin@trainings-backoffice.local)
    ADMIN_PASSWORD: Admin password (default: admin123456)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.models.user import User, UserRole


def create_admin_user():
    """Create the initial admin user if it doesn't exist."""
    db = SessionLocal()

    try:
        # Get admin credentials from environment or use defaults
        username = os.getenv("ADMIN_USERNAME", "admin")
        email = os.getenv("ADMIN_EMAIL", "admin@trainings-backoffice.local")
        password = os.getenv("ADMIN_PASSWORD", "admin123456")

        # Check if admin already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"❌ User '{username}' already exists!")
            return

        # Create admin user
        hashed_password = get_password_hash(password)
        admin_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=UserRole.ADMIN.value,
            is_active=True
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print("✅ Admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print("\n⚠️  IMPORTANT: Change the default password immediately after first login!")

    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_admin_user()
