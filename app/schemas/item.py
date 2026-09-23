"""Pydantic schemas for the item catalog. Money is integer cents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    unit_price_cents: int = Field(default=0, ge=0)
    is_active: bool = True


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    unit_price_cents: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    unit_price_cents: int
    is_active: bool
    created_at: datetime
