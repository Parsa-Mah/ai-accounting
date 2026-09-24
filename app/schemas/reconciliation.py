"""Pydantic schemas for bank reconciliation. Money is integer cents.

Date fields are annotated as ``datetime.date`` (not bare ``date``): in a
class body, ``date: date | None = None`` evaluates the default first,
binding ``date = None`` before the annotation is evaluated.
"""

import datetime

from pydantic import BaseModel, Field


class ReconciliationCreate(BaseModel):
    account_id: int
    statement_date: datetime.date
    statement_balance_cents: int
    line_ids: list[int] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=255)


class ReconciliationLineRead(BaseModel):
    id: int
    date: datetime.date
    description: str | None
    debit: int
    credit: int


class ReconciliationRead(BaseModel):
    id: int
    account_id: int
    account_number: str
    account_name: str
    statement_date: datetime.date
    statement_balance_cents: int
    opening_balance_cents: int
    cleared_total_cents: int
    difference_cents: int
    is_balanced: bool
    note: str | None
    created_at: datetime.datetime
    line_count: int
    lines: list[ReconciliationLineRead]


class BankAccountRead(BaseModel):
    id: int
    number: str
    name: str
    bank_kind: str
    balance_cents: int
