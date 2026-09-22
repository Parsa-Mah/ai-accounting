"""Pydantic schemas for accounts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.account import AccountType


class AccountCreate(BaseModel):
    number: str = Field(min_length=1, max_length=10, pattern=r"^\d+$")
    name: str = Field(min_length=1, max_length=100)
    type: AccountType
    subtype: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    bank_kind: str | None = Field(default=None, max_length=20)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    bank_kind: str | None = Field(default=None, max_length=20)


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    name: str
    type: AccountType
    subtype: str | None
    description: str | None
    bank_kind: str | None
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
