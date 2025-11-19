from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class UserRole(str, Enum):
    """User role enumeration for role-based access control."""
    ADMIN = "admin"
    BACKOFFICE_USER = "backoffice_user"
    TRAINER = "trainer"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.BACKOFFICE_USER.value)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Optional: Relationship to Trainer if user is a trainer
    # This would require adding a user_id foreign key to the Trainer model
    # trainer = relationship("Trainer", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
