#!/usr/bin/env python3
"""Script to create initial admin user."""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import User
from app.core.security import get_password_hash

def create_user():
    db = SessionLocal()

    # Check if user already exists
    existing = db.query(User).filter(User.email == "martin@yellow-boat.com").first()
    if existing:
        print(f"User already exists: {existing.username}")
        db.close()
        return

    # Create new admin user
    user = User(
        username="martin",
        email="martin@yellow-boat.com",
        hashed_password=get_password_hash("hoschi88"),
        role="admin",
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"Created admin user: {user.username} ({user.email})")
    db.close()

if __name__ == "__main__":
    create_user()
