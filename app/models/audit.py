"""Append-only audit trail model.

Every committed write to the books lands here as one row — who acted
(``user:<id>`` web, ``ai:<client>`` MCP, ``system`` seed), what action
(create/update/delete), which model and record, when. Rows are written by
the centralized Session hook in ``app/services/audit.py`` and are never
updated or deleted.
"""

import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(16), index=True)
    model: Mapped[str] = mapped_column(String(50), index=True)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
