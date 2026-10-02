from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.services.normalization import (
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_source,
)


class ContactCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    source: str | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        return normalize_name(value) if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_contact_email(cls, value: object) -> object:
        return normalize_email(value) if isinstance(value, str) else value

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_contact_phone(cls, value: object) -> object:
        return normalize_phone(value) if isinstance(value, str) else value

    @field_validator("source", mode="before")
    @classmethod
    def normalize_contact_source(cls, value: object) -> object:
        return normalize_source(value) if isinstance(value, str) else value


class ContactResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str
    source: str | None
    address: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactListItem(ContactResponse):
    has_ai_summary: bool


class ContactListResponse(BaseModel):
    items: list[ContactListItem]
    page: int
    page_size: int
    total: int
    pages: int
