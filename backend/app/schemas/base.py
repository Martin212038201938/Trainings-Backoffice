from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BrandBase(BaseModel):
    name: str
    slug: str
    default_sender_name: Optional[str] = None
    default_sender_email: Optional[str] = None
    default_timezone: str | None = "Europe/Berlin"
    default_language: str | None = "de"
    color: str | None = "#000000"


class BrandCreate(BrandBase):
    pass


class BrandRead(BrandBase):
    id: int

    class Config:
        from_attributes = True


class CustomerBase(BaseModel):
    company_name: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    status: str = "lead"
    brand_ids: List[int] = Field(default_factory=list)


class CustomerCreate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    id: int

    class Config:
        from_attributes = True


class TrainerBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    default_day_rate: Optional[float] = None
    preferred_topics: Optional[str] = None
    tags: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None
    brand_ids: List[int] = Field(default_factory=list)


class TrainerCreate(TrainerBase):
    pass


class TrainerRead(TrainerBase):
    id: int

    class Config:
        from_attributes = True


class TrainingCatalogBase(BaseModel):
    title: str
    short_description: Optional[str] = None
    duration_days: int = 1
    training_type: str
    default_format: str
    default_language: str = "de"
    checklist_template: str = "standard"


class TrainingCatalogCreate(TrainingCatalogBase):
    pass


class TrainingCatalogRead(TrainingCatalogBase):
    id: int

    class Config:
        from_attributes = True


class TrainingTaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    is_required: bool = True
    due_date: Optional[date] = None
    assignee: Optional[str] = None
    status: str = "open"
    reminder_offset_days: int = 0


class TrainingTaskCreate(TrainingTaskBase):
    pass


class TrainingTaskRead(TrainingTaskBase):
    id: int

    class Config:
        from_attributes = True


class TrainingBase(BaseModel):
    title: str
    training_type: str
    training_format: str
    duration_days: int = 1
    brand_id: int
    customer_id: int
    trainer_id: Optional[int] = None
    status: str = "lead"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    location_details: Optional[str] = None
    online_link: Optional[str] = None
    max_participants: Optional[int] = None
    language: str = "de"
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    contact_person: Optional[str] = None
    billing_details: Optional[str] = None
    internal_customer_reference: Optional[str] = None
    logistics_notes: Optional[str] = None
    communication_notes: Optional[str] = None
    finance_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    internal_priority: Optional[str] = None
    pipeline_status: Optional[str] = None
    tagessatz: Optional[float] = None
    travel_rules: Optional[str] = None
    payment_terms: Optional[str] = None
    lexoffice_id: Optional[str] = None
    price_external: Optional[float] = None
    price_internal: Optional[float] = None
    margin: Optional[float] = None
    checklist_template: str = "standard"
    tasks: List[TrainingTaskCreate] = Field(default_factory=list)


class TrainingCreate(TrainingBase):
    generate_checklist: bool = True


class TrainingRead(TrainingBase):
    id: int
    tasks: List[TrainingTaskRead] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ActivityLogRead(BaseModel):
    id: int
    message: str
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class EmailTemplateBase(BaseModel):
    brand_id: Optional[int] = None
    template_type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    description: Optional[str] = None


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateRead(EmailTemplateBase):
    id: int

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    customers: list[CustomerRead] = Field(default_factory=list)
    trainers: list[TrainerRead] = Field(default_factory=list)
    trainings: list[TrainingRead] = Field(default_factory=list)
