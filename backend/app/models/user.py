from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
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

    # Platform email address (lastname@yellow-boat.org)
    platform_email = Column(String(255), unique=True, nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Email relationships
    mailbox_emails = relationship("MailboxEmail", back_populates="owner", foreign_keys="MailboxEmail.owner_id")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


# Email/Mailbox related models
EMAIL_FOLDERS = ("inbox", "sent", "drafts", "trash", "archive")


class MailboxEmail(Base):
    """Email messages in user mailboxes."""
    __tablename__ = "mailbox_emails"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Email metadata
    message_id = Column(String(255), unique=True, index=True)  # Unique message ID for threading
    in_reply_to = Column(String(255), nullable=True, index=True)  # Parent message ID for threading
    thread_id = Column(String(255), nullable=True, index=True)  # Thread/conversation ID

    # Sender/Recipients
    from_address = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=True)
    to_addresses = Column(Text, nullable=False)  # JSON array of addresses
    cc_addresses = Column(Text, nullable=True)  # JSON array
    bcc_addresses = Column(Text, nullable=True)  # JSON array

    # Content
    subject = Column(String(500), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)

    # Status
    folder = Column(String(50), default="inbox", index=True)
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    is_draft = Column(Boolean, default=False)

    # Direction: 'inbound' or 'outbound'
    direction = Column(String(20), default="inbound")

    # Timestamps
    sent_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="mailbox_emails", foreign_keys=[owner_id])
    attachments = relationship("EmailAttachment", back_populates="email", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MailboxEmail {self.id} - {self.subject[:30] if self.subject else 'No subject'}>"


class EmailAttachment(Base):
    """Email attachments."""
    __tablename__ = "email_attachments"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("mailbox_emails.id", ondelete="CASCADE"), nullable=False)

    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    file_path = Column(String(500), nullable=True)  # Path to stored file

    created_at = Column(DateTime, default=datetime.utcnow)

    email = relationship("MailboxEmail", back_populates="attachments")


class EmailNotification(Base):
    """Notifications sent to users when they receive emails."""
    __tablename__ = "email_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email_id = Column(Integer, ForeignKey("mailbox_emails.id", ondelete="CASCADE"), nullable=False)

    notification_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    deep_link = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    email = relationship("MailboxEmail")
