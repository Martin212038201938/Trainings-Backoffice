from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Table, Text, JSON
from sqlalchemy.orm import relationship

from ..database import Base

TRAINING_STATUSES = (
    "lead",
    "appointment_scheduled",
    "initial_contact",
    "proposal_sent",
    "trainer_outreach",
    "trainer_confirmed",
    "planning",
    "delivered",
    "invoiced",
)

TRAINING_TYPES = ("online", "classroom")
TRAINING_FORMATS = ("inhouse", "public")

# Define allowed status transitions
# Key = current status, Value = list of allowed next statuses
ALLOWED_STATUS_TRANSITIONS = {
    "lead": ["appointment_scheduled", "initial_contact", "proposal_sent"],
    "appointment_scheduled": ["initial_contact", "proposal_sent", "lead"],
    "initial_contact": ["proposal_sent", "lead"],
    "proposal_sent": ["trainer_outreach", "lead"],
    "trainer_outreach": ["trainer_confirmed", "proposal_sent"],
    "trainer_confirmed": ["planning", "trainer_outreach"],
    "planning": ["delivered", "trainer_confirmed"],
    "delivered": ["invoiced", "planning"],
    "invoiced": ["delivered"],  # Can go back to delivered if correction needed
}


def validate_status_transition(current_status: str, new_status: str) -> tuple[bool, str]:
    """
    Validate if a status transition is allowed.

    Returns:
        tuple: (is_valid, error_message)
    """
    if new_status not in TRAINING_STATUSES:
        return False, f"Ungültiger Status: {new_status}. Erlaubt: {', '.join(TRAINING_STATUSES)}"

    if current_status == new_status:
        return True, ""

    if current_status not in ALLOWED_STATUS_TRANSITIONS:
        return False, f"Ungültiger aktueller Status: {current_status}"

    allowed = ALLOWED_STATUS_TRANSITIONS[current_status]
    if new_status not in allowed:
        return False, f"Status-Übergang von '{current_status}' zu '{new_status}' nicht erlaubt. Erlaubt: {', '.join(allowed)}"

    return True, ""


def validate_training_type(training_type: str) -> tuple[bool, str]:
    """Validate training type."""
    if training_type and training_type not in TRAINING_TYPES:
        return False, f"Ungültiger Trainingstyp: {training_type}. Erlaubt: {', '.join(TRAINING_TYPES)}"
    return True, ""


def validate_training_format(training_format: str) -> tuple[bool, str]:
    """Validate training format."""
    if training_format and training_format not in TRAINING_FORMATS:
        return False, f"Ungültiges Trainingsformat: {training_format}. Erlaubt: {', '.join(TRAINING_FORMATS)}"
    return True, ""

customer_brands = Table(
    "customer_brands",
    Base.metadata,
    Column("customer_id", ForeignKey("customers.id"), primary_key=True),
    Column("brand_id", ForeignKey("brands.id"), primary_key=True),
)

trainer_brands = Table(
    "trainer_brands",
    Base.metadata,
    Column("trainer_id", ForeignKey("trainers.id"), primary_key=True),
    Column("brand_id", ForeignKey("brands.id"), primary_key=True),
)


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Brand(Base, TimestampMixin):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    default_sender_name = Column(String(255))
    default_sender_email = Column(String(255))
    default_timezone = Column(String(64), default="Europe/Berlin")
    default_language = Column(String(32), default="de")
    color = Column(String(16), default="#000000")

    trainings = relationship("Training", back_populates="brand")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    salutation = Column(String(20))  # Frau, Herr, ---
    contact_email = Column(String(255))
    contact_phone = Column(String(100))
    vat_number = Column(String(100))
    # Billing address fields
    street = Column(String(255))
    street_number = Column(String(20))
    postal_code = Column(String(20))
    city = Column(String(100))
    billing_address = Column(Text)  # Legacy field
    conditions = Column(Text)  # Konditionen
    comment = Column(Text)  # Kommentar
    tags = Column(String(255))
    notes = Column(Text)
    status = Column(String(50), default="lead")

    @property
    def contact_name(self):
        """Legacy property for backwards compatibility."""
        parts = [self.first_name or '', self.last_name or '']
        return ' '.join(p for p in parts if p).strip() or None

    brands = relationship("Brand", secondary=customer_brands, backref="customers")
    trainings = relationship("Training", back_populates="customer")


class Trainer(Base, TimestampMixin):
    __tablename__ = "trainers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)  # Link to user account
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(100))
    address = Column(Text)
    vat_number = Column(String(100))
    linkedin_url = Column(String(500))
    website = Column(String(500))
    photo_path = Column(String(500))
    default_day_rate = Column(Float)
    preferred_topics = Column(Text)
    specializations = Column(JSON)  # {"selected": ["topic1", "topic2"], "custom": ["custom1"]}
    tags = Column(String(255))
    region = Column(String(100))
    bio = Column(Text)
    notes = Column(Text)

    user = relationship("User", backref="trainer")
    brands = relationship("Brand", secondary=trainer_brands, backref="trainers")
    trainings = relationship("Training", back_populates="trainer")

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()


class TrainingCatalogEntry(Base, TimestampMixin):
    __tablename__ = "training_catalog"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    short_description = Column(Text)
    duration_days = Column(Integer, default=1)
    training_type = Column(Enum(*TRAINING_TYPES, name="training_type_enum"))
    default_format = Column(Enum(*TRAINING_FORMATS, name="training_format_enum"))
    default_language = Column(String(32), default="de")
    checklist_template = Column(String(50), default="standard")


class Training(Base, TimestampMixin):
    __tablename__ = "trainings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    training_type = Column(Enum(*TRAINING_TYPES, name="training_type_enum", create_constraint=False))
    training_format = Column(Enum(*TRAINING_FORMATS, name="training_format_enum", create_constraint=False))
    duration_days = Column(Integer, default=1)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("trainers.id"), nullable=True)
    status = Column(Enum(*TRAINING_STATUSES, name="training_status_enum"))
    start_date = Column(Date)
    end_date = Column(Date)
    timezone = Column(String(64))
    location = Column(String(255))
    location_details = Column(Text)
    online_link = Column(String(500))
    max_participants = Column(Integer)
    language = Column(String(32), default="de")
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(255))
    contact_person = Column(String(255))
    billing_details = Column(Text)
    internal_customer_reference = Column(String(255))
    logistics_notes = Column(Text)
    communication_notes = Column(Text)
    finance_notes = Column(Text)
    internal_notes = Column(Text)
    internal_priority = Column(String(50))
    pipeline_status = Column(String(50))
    tagessatz = Column(Float)
    travel_rules = Column(Text)
    payment_terms = Column(String(100))
    lexoffice_id = Column(String(100))
    price_external = Column(Float)
    price_internal = Column(Float)
    margin = Column(Float)
    checklist_template = Column(String(50), default="standard")

    brand = relationship("Brand", back_populates="trainings")
    customer = relationship("Customer", back_populates="trainings")
    trainer = relationship("Trainer", back_populates="trainings")
    tasks = relationship("TrainingTask", back_populates="training", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="training", cascade="all, delete-orphan")


class TrainingTask(Base, TimestampMixin):
    __tablename__ = "training_tasks"

    id = Column(Integer, primary_key=True, index=True)
    training_id = Column(Integer, ForeignKey("trainings.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    is_required = Column(Boolean, default=True)
    due_date = Column(Date)
    assignee = Column(String(255))
    status = Column(String(50), default="open")
    reminder_offset_days = Column(Integer, default=0)
    completed_at = Column(DateTime)

    training = relationship("Training", back_populates="tasks")


class ActivityLog(Base, TimestampMixin):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    training_id = Column(Integer, ForeignKey("trainings.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text)
    created_by = Column(String(255))

    training = relationship("Training", back_populates="activity_logs")


class EmailTemplate(Base, TimestampMixin):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    template_type = Column(String(100), nullable=False)
    subject = Column(String(255))
    body = Column(Text)
    description = Column(Text)


class TrainerApplication(Base, TimestampMixin):
    """Trainer applications for open training positions."""
    __tablename__ = "trainer_applications"

    id = Column(Integer, primary_key=True, index=True)
    training_id = Column(Integer, ForeignKey("trainings.id", ondelete="CASCADE"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending")  # pending, accepted, rejected
    message = Column(Text)  # Optional message from trainer
    proposed_rate = Column(Float)  # Trainer's proposed day rate
    admin_notes = Column(Text)  # Admin notes on application

    training = relationship("Training", backref="applications")
    trainer = relationship("Trainer", backref="applications")


CATERING_OPTIONS = ("yes", "no", "external")
RENTAL_COST_TYPES = ("day", "hour", "total")


class Location(Base, TimestampMixin):
    """Training locations/venues."""
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)

    # Address
    city = Column(String(100))
    street = Column(String(255))
    street_number = Column(String(20))
    postal_code = Column(String(20))

    # Billing address
    billing_street = Column(String(255))
    billing_street_number = Column(String(20))
    billing_postal_code = Column(String(20))
    billing_city = Column(String(100))
    billing_vat = Column(String(100))

    # Contact person
    contact_first_name = Column(String(100))
    contact_last_name = Column(String(100))
    contact_email = Column(String(255))
    contact_phone = Column(String(100))
    contact_notes = Column(Text)  # Hinweise

    # Location details
    description = Column(Text)  # Location Beschreibung
    max_participants = Column(Integer)
    features = Column(Text)  # Features (Freitext)
    website_link = Column(String(500))  # Link zur Location
    catering_available = Column(String(20), default="no")  # yes/no/external
    rental_cost = Column(Float)  # Mietkosten
    rental_cost_type = Column(String(20), default="day")  # day/hour/total
    parking = Column(Text)  # Parken (Freitext)
    directions = Column(Text)  # Anreise (Freitext)
    participant_info = Column(Text)  # Informationen für TN (Freitext)


APPLICATION_STATUSES = ("pending", "approved", "rejected")


class TrainerRegistration(Base, TimestampMixin):
    """Trainer registration applications from prospective trainers."""
    __tablename__ = "trainer_registrations"

    id = Column(Integer, primary_key=True, index=True)

    # Login credentials
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)

    # Personal info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(100))
    address = Column(Text)

    # Professional info
    vat_number = Column(String(100))
    linkedin_url = Column(String(500))
    website = Column(String(500))
    default_day_rate = Column(Float)
    region = Column(String(100))
    bio = Column(Text)
    specializations = Column(Text)  # Comma-separated or JSON

    # Photo
    photo_url = Column(String(500))

    # Application status
    status = Column(String(50), default="pending")
    reviewed_at = Column(DateTime)
    reviewed_by = Column(Integer, ForeignKey("users.id"))

    reviewer = relationship("User", foreign_keys=[reviewed_by])


MESSAGE_TYPES = ("error_report", "message", "trainer_application")
MESSAGE_STATUSES = ("open", "solved", "not_solvable")


class Message(Base, TimestampMixin):
    """Messages and error reports between users."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = to all admins
    parent_id = Column(Integer, ForeignKey("messages.id"), nullable=True)  # For replies

    message_type = Column(String(50), default="message")  # error_report or message
    subject = Column(String(255))
    content = Column(Text, nullable=False)

    # Error report specific fields
    page_url = Column(String(500))  # Page where error occurred
    error_details = Column(Text)  # Automatic error info
    status = Column(String(50), default="open")  # open, solved, not_solvable

    # Read status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)

    sender = relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    recipient = relationship("User", foreign_keys=[recipient_id], backref="received_messages")
    parent = relationship("Message", remote_side=[id], backref="replies")
