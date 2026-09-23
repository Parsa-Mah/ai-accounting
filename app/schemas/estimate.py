"""Pydantic schemas for estimates. Money is integer cents.

Date fields are annotated as ``datetime.date`` (see schemas/invoice.py for
why a bare ``date`` annotation breaks in class bodies).
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.invoice import InvoiceLineCreate, InvoiceLineRead


class EstimateCreate(BaseModel):
    customer_id: int
    date: datetime.date
    tax_rate: float = Field(default=0.0, ge=0, le=100)
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class EstimateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    customer_name: str
    date: datetime.date
    tax_rate: float
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    status: str
    converted_invoice_id: int | None
    created_at: datetime.datetime
    lines: list[InvoiceLineRead]
