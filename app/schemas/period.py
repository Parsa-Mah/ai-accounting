"""Pydantic schemas for periods (calendar-month locking)."""

import datetime

from pydantic import BaseModel, ConfigDict


class PeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    month: int
    is_locked: bool
    locked_at: datetime.datetime | None
    created_at: datetime.datetime
