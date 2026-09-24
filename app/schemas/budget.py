"""Pydantic schemas for budgets. Money is integer cents.

Date fields are annotated as ``datetime.date`` (not bare ``date``): in a
class body, ``date: date | None = None`` evaluates the default first,
binding ``date = None`` before the annotation is evaluated.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BudgetCreate(BaseModel):
    account_id: int
    budget_start: datetime.date
    budget_end: datetime.date
    budget_cents: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check_range(self):
        if self.budget_start > self.budget_end:
            raise ValueError("budget_start must be on or before budget_end")
        return self


class BudgetUpdate(BaseModel):
    budget_start: datetime.date | None = None
    budget_end: datetime.date | None = None
    budget_cents: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=255)


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    account_number: str
    account_name: str
    account_type: str
    budget_start: datetime.date
    budget_end: datetime.date
    budget_cents: int
    note: str | None
    created_at: datetime.datetime


class BudgetReportRow(BaseModel):
    budget_id: int
    account_id: int
    account_number: str
    account_name: str
    account_type: str
    budget_start: datetime.date
    budget_end: datetime.date
    budget_cents: int
    actual_cents: int
    variance_cents: int
    within_budget: bool


class BudgetReportTotals(BaseModel):
    budget_cents: int
    actual_cents: int
    variance_cents: int


class BudgetReportRead(BaseModel):
    start: datetime.date
    end: datetime.date
    rows: list[BudgetReportRow]
    totals: BudgetReportTotals
