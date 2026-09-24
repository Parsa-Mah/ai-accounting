"""Pydantic schemas for bills and payments. Money is integer cents.

Date fields are annotated as ``datetime.date`` (not bare ``date``): in a
class body, ``date: date | None = None`` evaluates the default first,
binding ``date = None`` before the annotation is evaluated.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BillLineCreate(BaseModel):
    item_id: int | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: int = Field(default=1, ge=1)
    unit_price_cents: int = Field(default=0, ge=0)
    expense_account_id: int

    @model_validator(mode="after")
    def _check_description(self):
        if self.description is None and self.item_id is None:
            raise ValueError("each line needs a description or an item_id")
        return self


class BillCreate(BaseModel):
    vendor_id: int
    date: datetime.date
    due_date: datetime.date | None = None
    tax_rate: float = Field(default=0.0, ge=0, le=100)
    lines: list[BillLineCreate] = Field(min_length=1)


class BillPayCreate(BaseModel):
    amount_cents: int = Field(ge=1)
    date: datetime.date | None = None
    note: str | None = Field(default=None, max_length=255)


class BillLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int | None
    description: str
    quantity: int
    unit_price_cents: int
    amount_cents: int
    expense_account_id: int


class BillPaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime.date
    amount_cents: int
    note: str | None
    entry_id: int
    created_at: datetime.datetime


class BillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    vendor_name: str
    date: datetime.date
    due_date: datetime.date | None
    tax_rate: float
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    paid_cents: int
    is_voided: bool
    status: str
    entry_id: int
    voided_by_entry_id: int | None
    created_at: datetime.datetime
    lines: list[BillLineRead]
    payments: list[BillPaymentRead]
