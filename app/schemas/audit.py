"""Pydantic schemas for the audit trail."""

import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime.datetime
    actor: str
    action: str
    model: str
    record_id: int | None
