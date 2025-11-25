"""Email/Mailbox endpoints for the platform email system."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import get_current_active_user, get_db, require_admin, require_backoffice
from ..models.user import User, MailboxEmail, EMAIL_FOLDERS
from ..services import mailbox as mailbox_service

router = APIRouter()


# Pydantic schemas for email endpoints
class EmailAddressInfo(BaseModel):
    address: str
    name: Optional[str] = None


class EmailCreate(BaseModel):
    to_addresses: list[str]
    cc_addresses: Optional[list[str]] = None
    subject: str
    body_text: str
    body_html: Optional[str] = None
    in_reply_to: Optional[str] = None
    is_draft: bool = False


class EmailResponse(BaseModel):
    id: int
    message_id: Optional[str]
    thread_id: Optional[str]
    from_address: str
    from_name: Optional[str]
    to_addresses: list[str]
    cc_addresses: Optional[list[str]]
    subject: Optional[str]
    body_text: Optional[str]
    body_html: Optional[str]
    folder: str
    is_read: bool
    is_starred: bool
    is_draft: bool
    direction: str
    sent_at: Optional[str]
    received_at: Optional[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_email(cls, email: MailboxEmail) -> "EmailResponse":
        return cls(
            id=email.id,
            message_id=email.message_id,
            thread_id=email.thread_id,
            from_address=email.from_address,
            from_name=email.from_name,
            to_addresses=json.loads(email.to_addresses) if email.to_addresses else [],
            cc_addresses=json.loads(email.cc_addresses) if email.cc_addresses else None,
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            folder=email.folder,
            is_read=email.is_read,
            is_starred=email.is_starred,
            is_draft=email.is_draft,
            direction=email.direction,
            sent_at=email.sent_at.isoformat() if email.sent_at else None,
            received_at=email.received_at.isoformat() if email.received_at else None,
        )


class EmailListResponse(BaseModel):
    emails: list[EmailResponse]
    total: int
    unread: int


class EmailStatsResponse(BaseModel):
    unread: int
    inbox: int
    sent: int


class PlatformEmailResponse(BaseModel):
    platform_email: str
    user_id: int
    username: str


class MoveEmailRequest(BaseModel):
    folder: str


# Platform email management endpoints
@router.post("/platform-email/assign", response_model=PlatformEmailResponse)
async def assign_platform_email(
    last_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Assign a platform email address to the current user.
    Format: lastname@yellow-boat.org (with numbers for duplicates)
    """
    if current_user.platform_email:
        return PlatformEmailResponse(
            platform_email=current_user.platform_email,
            user_id=current_user.id,
            username=current_user.username,
        )

    platform_email = mailbox_service.assign_platform_email_to_user(db, current_user, last_name)

    return PlatformEmailResponse(
        platform_email=platform_email,
        user_id=current_user.id,
        username=current_user.username,
    )


@router.get("/platform-email/me", response_model=PlatformEmailResponse)
async def get_my_platform_email(
    current_user: User = Depends(get_current_active_user),
):
    """Get the current user's platform email address."""
    if not current_user.platform_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No platform email assigned. Use POST /platform-email/assign to get one.",
        )

    return PlatformEmailResponse(
        platform_email=current_user.platform_email,
        user_id=current_user.id,
        username=current_user.username,
    )


# Email CRUD endpoints
@router.get("/", response_model=EmailListResponse)
async def list_emails(
    folder: str = Query("inbox", description="Email folder"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List emails in a specific folder."""
    if folder not in EMAIL_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid folder. Valid folders: {', '.join(EMAIL_FOLDERS)}",
        )

    emails = mailbox_service.get_user_emails(
        db, current_user.id, folder, skip, limit, unread_only
    )
    stats = mailbox_service.get_email_stats(db, current_user.id)

    return EmailListResponse(
        emails=[EmailResponse.from_orm_email(e) for e in emails],
        total=len(emails),
        unread=stats["unread"],
    )


@router.get("/stats", response_model=EmailStatsResponse)
async def get_email_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get email statistics for the current user."""
    stats = mailbox_service.get_email_stats(db, current_user.id)
    return EmailStatsResponse(**stats)


@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(
    email_id: int,
    mark_as_read: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific email by ID."""
    email = mailbox_service.get_email_by_id(db, email_id, current_user.id)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    if mark_as_read and not email.is_read:
        email = mailbox_service.mark_email_as_read(db, email)

    return EmailResponse.from_orm_email(email)


@router.post("/", response_model=EmailResponse, status_code=status.HTTP_201_CREATED)
async def send_email(
    email_data: EmailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Send a new email from the user's platform mailbox."""
    if not current_user.platform_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No platform email assigned. Use POST /emails/platform-email/assign first.",
        )

    if email_data.is_draft:
        # Save as draft
        email = mailbox_service.create_email(
            db=db,
            owner_id=current_user.id,
            from_address=current_user.platform_email,
            from_name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.username,
            to_addresses=email_data.to_addresses,
            cc_addresses=email_data.cc_addresses,
            subject=email_data.subject,
            body_text=email_data.body_text,
            body_html=email_data.body_html,
            in_reply_to=email_data.in_reply_to,
            direction="outbound",
            folder="drafts",
            is_draft=True,
        )
    else:
        # Send email
        success, email = mailbox_service.send_platform_email(
            db=db,
            sender_user=current_user,
            to_addresses=email_data.to_addresses,
            cc_addresses=email_data.cc_addresses,
            subject=email_data.subject,
            body_text=email_data.body_text,
            body_html=email_data.body_html,
            in_reply_to=email_data.in_reply_to,
        )

        if not success or not email:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email",
            )

    return EmailResponse.from_orm_email(email)


@router.post("/{email_id}/reply", response_model=EmailResponse, status_code=status.HTTP_201_CREATED)
async def reply_to_email(
    email_id: int,
    body_text: str,
    body_html: Optional[str] = None,
    reply_all: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reply to an email."""
    if not current_user.platform_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No platform email assigned.",
        )

    original_email = mailbox_service.get_email_by_id(db, email_id, current_user.id)
    if not original_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original email not found",
        )

    # Determine recipients
    to_addresses = [original_email.from_address]
    cc_addresses = None

    if reply_all:
        original_to = json.loads(original_email.to_addresses) if original_email.to_addresses else []
        original_cc = json.loads(original_email.cc_addresses) if original_email.cc_addresses else []
        # Add all original recipients except self
        cc_addresses = [
            addr for addr in original_to + original_cc
            if addr != current_user.platform_email
        ]

    # Build reply subject
    subject = original_email.subject or ""
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    success, email = mailbox_service.send_platform_email(
        db=db,
        sender_user=current_user,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses if cc_addresses else None,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        in_reply_to=original_email.message_id,
    )

    if not success or not email:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send reply",
        )

    return EmailResponse.from_orm_email(email)


@router.post("/{email_id}/forward", response_model=EmailResponse, status_code=status.HTTP_201_CREATED)
async def forward_email(
    email_id: int,
    to_addresses: list[str],
    additional_message: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Forward an email to other recipients."""
    if not current_user.platform_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No platform email assigned.",
        )

    original_email = mailbox_service.get_email_by_id(db, email_id, current_user.id)
    if not original_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original email not found",
        )

    # Build forwarded subject
    subject = original_email.subject or ""
    if not subject.lower().startswith("fwd:") and not subject.lower().startswith("fw:"):
        subject = f"Fwd: {subject}"

    # Build forwarded body
    forwarded_body = ""
    if additional_message:
        forwarded_body = f"{additional_message}\n\n"

    forwarded_body += f"""---------- Weitergeleitete Nachricht ----------
Von: {original_email.from_name or original_email.from_address} <{original_email.from_address}>
Datum: {original_email.sent_at or original_email.received_at}
Betreff: {original_email.subject or '(Kein Betreff)'}

{original_email.body_text or ''}
"""

    success, email = mailbox_service.send_platform_email(
        db=db,
        sender_user=current_user,
        to_addresses=to_addresses,
        subject=subject,
        body_text=forwarded_body,
    )

    if not success or not email:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to forward email",
        )

    return EmailResponse.from_orm_email(email)


@router.put("/{email_id}/move", response_model=EmailResponse)
async def move_email(
    email_id: int,
    move_request: MoveEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Move an email to a different folder."""
    if move_request.folder not in EMAIL_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid folder. Valid folders: {', '.join(EMAIL_FOLDERS)}",
        )

    email = mailbox_service.get_email_by_id(db, email_id, current_user.id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    email = mailbox_service.move_email_to_folder(db, email, move_request.folder)
    return EmailResponse.from_orm_email(email)


@router.put("/{email_id}/read")
async def mark_as_read(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark an email as read."""
    email = mailbox_service.get_email_by_id(db, email_id, current_user.id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    mailbox_service.mark_email_as_read(db, email)
    return {"status": "ok"}


@router.delete("/{email_id}")
async def delete_email(
    email_id: int,
    permanent: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an email (move to trash or permanently delete)."""
    email = mailbox_service.get_email_by_id(db, email_id, current_user.id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    mailbox_service.delete_email(db, email, permanent)
    return {"status": "deleted"}


@router.get("/thread/{thread_id}", response_model=list[EmailResponse])
async def get_email_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all emails in a conversation thread."""
    emails = mailbox_service.get_email_thread(db, thread_id, current_user.id)
    return [EmailResponse.from_orm_email(e) for e in emails]


# Admin endpoints for viewing all emails
@router.get("/admin/all", response_model=list[EmailResponse])
async def list_all_emails_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_backoffice),
):
    """
    List all emails in the system (admin/backoffice only).
    Excludes the viewer's own emails for privacy.
    """
    emails = mailbox_service.get_all_emails_for_admin(
        db, skip, limit, user_id_filter=current_user.id
    )
    return [EmailResponse.from_orm_email(e) for e in emails]


@router.get("/admin/user/{user_id}", response_model=list[EmailResponse])
async def list_user_emails_admin(
    user_id: int,
    folder: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List emails for a specific user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    emails = mailbox_service.get_user_emails(
        db, user_id, folder or "inbox", skip, limit
    )
    return [EmailResponse.from_orm_email(e) for e in emails]
