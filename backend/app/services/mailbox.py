"""Mailbox service for managing user emails and platform email addresses."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..models.user import User, MailboxEmail, EmailAttachment, EmailNotification
from .email import send_email

logger = logging.getLogger(__name__)


def generate_platform_email(db: Session, last_name: str) -> str:
    """
    Generate a unique platform email address in format lastname@yellow-boat.org.
    If lastname is already taken, append incrementing numbers (1, 2, 3, etc.)
    """
    domain = settings.platform_email_domain
    base_email = f"{last_name.lower().replace(' ', '-')}@{domain}"

    # Check if base email is available
    existing = db.query(User).filter(User.platform_email == base_email).first()
    if not existing:
        return base_email

    # Find next available number
    counter = 1
    while True:
        numbered_email = f"{last_name.lower().replace(' ', '-')}{counter}@{domain}"
        existing = db.query(User).filter(User.platform_email == numbered_email).first()
        if not existing:
            return numbered_email
        counter += 1
        if counter > 1000:  # Safety limit
            raise ValueError(f"Could not generate unique email for {last_name}")


def assign_platform_email_to_user(db: Session, user: User, last_name: str) -> str:
    """Assign a platform email address to a user."""
    if user.platform_email:
        return user.platform_email

    platform_email = generate_platform_email(db, last_name)
    user.platform_email = platform_email
    user.last_name = last_name
    db.commit()
    db.refresh(user)

    logger.info(f"Assigned platform email {platform_email} to user {user.username}")
    return platform_email


def get_user_by_platform_email(db: Session, platform_email: str) -> Optional[User]:
    """Find user by their platform email address."""
    return db.query(User).filter(User.platform_email == platform_email).first()


def generate_message_id() -> str:
    """Generate a unique message ID for email threading."""
    return f"<{uuid.uuid4()}@{settings.platform_email_domain}>"


def create_email(
    db: Session,
    owner_id: int,
    from_address: str,
    to_addresses: list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    cc_addresses: Optional[list[str]] = None,
    bcc_addresses: Optional[list[str]] = None,
    from_name: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    thread_id: Optional[str] = None,
    direction: str = "outbound",
    folder: str = "sent",
    is_draft: bool = False,
) -> MailboxEmail:
    """Create a new email in the mailbox."""
    message_id = generate_message_id()

    # If replying, use same thread_id, otherwise generate new one
    if not thread_id and in_reply_to:
        # Try to find parent email to get thread_id
        parent = db.query(MailboxEmail).filter(MailboxEmail.message_id == in_reply_to).first()
        if parent:
            thread_id = parent.thread_id
    if not thread_id:
        thread_id = message_id

    email = MailboxEmail(
        owner_id=owner_id,
        message_id=message_id,
        in_reply_to=in_reply_to,
        thread_id=thread_id,
        from_address=from_address,
        from_name=from_name,
        to_addresses=json.dumps(to_addresses),
        cc_addresses=json.dumps(cc_addresses) if cc_addresses else None,
        bcc_addresses=json.dumps(bcc_addresses) if bcc_addresses else None,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        folder=folder,
        direction=direction,
        is_draft=is_draft,
        sent_at=datetime.utcnow() if not is_draft else None,
    )

    db.add(email)
    db.commit()
    db.refresh(email)

    return email


def send_platform_email(
    db: Session,
    sender_user: User,
    to_addresses: list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    cc_addresses: Optional[list[str]] = None,
    in_reply_to: Optional[str] = None,
) -> tuple[bool, Optional[MailboxEmail]]:
    """
    Send an email from user's platform email and store it in their mailbox.
    Also delivers to recipients who are platform users.
    """
    if not sender_user.platform_email:
        logger.error(f"User {sender_user.username} has no platform email")
        return False, None

    # Create outbound email in sender's mailbox
    outbound_email = create_email(
        db=db,
        owner_id=sender_user.id,
        from_address=sender_user.platform_email,
        from_name=f"{sender_user.first_name or ''} {sender_user.last_name or ''}".strip() or sender_user.username,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        in_reply_to=in_reply_to,
        direction="outbound",
        folder="sent",
    )

    # Deliver to platform users (create inbound copy in their mailbox)
    all_recipients = to_addresses + (cc_addresses or [])
    for recipient_address in all_recipients:
        recipient_user = get_user_by_platform_email(db, recipient_address)
        if recipient_user:
            # Create inbound copy for platform user
            inbound_email = create_email(
                db=db,
                owner_id=recipient_user.id,
                from_address=sender_user.platform_email,
                from_name=f"{sender_user.first_name or ''} {sender_user.last_name or ''}".strip() or sender_user.username,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                in_reply_to=in_reply_to,
                thread_id=outbound_email.thread_id,
                direction="inbound",
                folder="inbox",
            )

            # Create notification and send to user's personal email
            send_email_notification(db, recipient_user, inbound_email)

    # Also try to send via SMTP to external addresses
    for recipient_address in all_recipients:
        if not recipient_address.endswith(f"@{settings.platform_email_domain}"):
            # External recipient - send via SMTP
            send_email(recipient_address, subject, body_text)

    return True, outbound_email


def send_email_notification(db: Session, user: User, email: MailboxEmail) -> bool:
    """Send notification to user's personal email about new platform email."""
    if not user.email:
        return False

    deep_link = f"{settings.frontend_base_url}/mailbox/{email.id}"

    # Create notification record
    notification = EmailNotification(
        user_id=user.id,
        email_id=email.id,
        deep_link=deep_link,
    )
    db.add(notification)

    # Send notification email
    subject = f"Neue E-Mail: {email.subject or '(Kein Betreff)'}"
    body = f"""Hallo {user.first_name or user.username},

du hast eine neue E-Mail in deinem Yellow-Boat Academy Postfach erhalten.

Von: {email.from_name or email.from_address}
Betreff: {email.subject or '(Kein Betreff)'}

Klicke hier, um die E-Mail zu lesen:
{deep_link}

Viele Gruesse,
Yellow-Boat Academy
"""

    success = send_email(user.email, subject, body)

    if success:
        notification.notification_sent = True
        notification.sent_at = datetime.utcnow()

    db.commit()
    return success


def get_user_emails(
    db: Session,
    user_id: int,
    folder: str = "inbox",
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
) -> list[MailboxEmail]:
    """Get emails for a user in a specific folder."""
    query = db.query(MailboxEmail).filter(
        MailboxEmail.owner_id == user_id,
        MailboxEmail.folder == folder,
    )

    if unread_only:
        query = query.filter(MailboxEmail.is_read == False)

    return query.order_by(MailboxEmail.received_at.desc()).offset(skip).limit(limit).all()


def get_email_by_id(db: Session, email_id: int, user_id: int) -> Optional[MailboxEmail]:
    """Get a specific email by ID, ensuring it belongs to the user."""
    return db.query(MailboxEmail).filter(
        MailboxEmail.id == email_id,
        MailboxEmail.owner_id == user_id,
    ).first()


def mark_email_as_read(db: Session, email: MailboxEmail) -> MailboxEmail:
    """Mark an email as read."""
    email.is_read = True
    db.commit()
    db.refresh(email)
    return email


def move_email_to_folder(db: Session, email: MailboxEmail, folder: str) -> MailboxEmail:
    """Move an email to a different folder."""
    email.folder = folder
    db.commit()
    db.refresh(email)
    return email


def delete_email(db: Session, email: MailboxEmail, permanent: bool = False) -> bool:
    """Delete an email (move to trash or permanently delete)."""
    if permanent or email.folder == "trash":
        db.delete(email)
    else:
        email.folder = "trash"
    db.commit()
    return True


def get_email_thread(db: Session, thread_id: str, user_id: int) -> list[MailboxEmail]:
    """Get all emails in a thread for a user."""
    return db.query(MailboxEmail).filter(
        MailboxEmail.thread_id == thread_id,
        MailboxEmail.owner_id == user_id,
    ).order_by(MailboxEmail.sent_at.asc()).all()


def get_all_emails_for_admin(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    user_id_filter: Optional[int] = None,
) -> list[MailboxEmail]:
    """Get all emails for admin/backoffice view (excluding the viewer's own emails)."""
    query = db.query(MailboxEmail)

    if user_id_filter:
        query = query.filter(MailboxEmail.owner_id != user_id_filter)

    return query.order_by(MailboxEmail.received_at.desc()).offset(skip).limit(limit).all()


def get_email_stats(db: Session, user_id: int) -> dict:
    """Get email statistics for a user."""
    unread_count = db.query(func.count(MailboxEmail.id)).filter(
        MailboxEmail.owner_id == user_id,
        MailboxEmail.folder == "inbox",
        MailboxEmail.is_read == False,
    ).scalar()

    inbox_count = db.query(func.count(MailboxEmail.id)).filter(
        MailboxEmail.owner_id == user_id,
        MailboxEmail.folder == "inbox",
    ).scalar()

    sent_count = db.query(func.count(MailboxEmail.id)).filter(
        MailboxEmail.owner_id == user_id,
        MailboxEmail.folder == "sent",
    ).scalar()

    return {
        "unread": unread_count,
        "inbox": inbox_count,
        "sent": sent_count,
    }
