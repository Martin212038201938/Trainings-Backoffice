"""Authentication endpoints."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import get_current_active_user, get_db, require_admin
from ..core.security import create_access_token, get_password_hash, verify_password
from ..models.user import User, UserRole
from ..models.core import Trainer
from ..schemas.auth import Token, UserCreate, UserResponse, UserUpdate
from ..services.email import send_trainer_welcome_email

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token login endpoint.

    Args:
        form_data: Username and password from form
        db: Database session

    Returns:
        Access token

    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Register a new user (admin only).

    Args:
        user_data: User registration data
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        Created user

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email already exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role.value,
        is_active=user_data.is_active
    )

    db.add(db_user)
    db.flush()  # Get the user ID before commit

    # Auto-link to trainer if exists with same email
    trainer = db.query(Trainer).filter(Trainer.email == user_data.email).first()
    if trainer and trainer.user_id is None:
        trainer.user_id = db_user.id
        logger.info(f"Auto-linked user {db_user.id} to trainer {trainer.id} by email {user_data.email}")

    db.commit()
    db.refresh(db_user)

    # Send welcome email to trainers
    if user_data.role == UserRole.TRAINER:
        trainer_name = user_data.username
        # Try to get trainer name if linked
        if trainer:
            trainer_name = f"{trainer.first_name} {trainer.last_name}" if trainer.first_name else trainer.name or user_data.username
        send_trainer_welcome_email(user_data.email, trainer_name)
        logger.info(f"Sent welcome email to trainer {user_data.email}")

    return db_user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user data
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update current user information (admin only for role changes).

    Args:
        user_update: Updated user data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user

    Raises:
        HTTPException: If email already exists or unauthorized role change
    """
    # Check if email is being changed and if it's already taken
    if user_update.email and user_update.email != current_user.email:
        if db.query(User).filter(User.email == user_update.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = user_update.email

    # Only admins can change roles and active status
    if user_update.role and user_update.role.value != current_user.role:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change user roles"
            )
        current_user.role = user_update.role.value

    if user_update.is_active is not None and user_update.is_active != current_user.is_active:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change user active status"
            )
        current_user.is_active = user_update.is_active

    db.commit()
    db.refresh(current_user)

    return current_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100
):
    """
    List all users (admin only).

    Args:
        db: Database session
        current_user: Current authenticated admin user
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of users
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a user (admin only).

    Args:
        user_id: ID of user to delete
        db: Database session
        current_user: Current authenticated admin user

    Raises:
        HTTPException: If user not found or trying to delete self
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """
    Logout endpoint (for client-side token removal).

    Note: Since we're using stateless JWT tokens, the actual logout
    happens on the client side by removing the token.

    Args:
        current_user: Current authenticated user

    Returns:
        Success message
    """
    return {"message": "Successfully logged out"}
