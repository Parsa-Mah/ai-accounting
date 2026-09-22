"""Pydantic schemas for journal entries and lines.

Money values are integer cents. Each line must be debit-only or credit-only.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JournalLineCreate(BaseModel):
    account_id: int
    description: str | None = Field(default=None, max_length=255)
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _check_exclusivity(self):
        # Exactly one of debit/credit must be positive (never both, never neither).
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError(
                "each line must be debit-only or credit-only "
                "(exactly one of debit/credit must be positive)"
            )
        return self


class JournalEntryCreate(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=255)
    lines: list[JournalLineCreate] = Field(min_length=1)


class JournalLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    account_number: str
    account_name: str
    description: str | None
    debit: int
    credit: int


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    description: str
    source_type: str
    source_id: int | None
    is_voided: bool
    voided_by_id: int | None
    created_at: datetime
    lines: list[JournalLineRead]
