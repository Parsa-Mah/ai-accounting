"""Period model: a calendar month that can be locked.

A locked period is immutable: the single posting path, the void path,
and bank reconciliation all refuse to touch entries dated in a locked
month (409). The row is created on first lock and kept after an unlock
(``is_locked`` flips back to False), so the list of periods doubles as
the history of months that have been locked.
"""

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Period(Base):
    __tablename__ = "periods"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_period_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
