"""Reconciliation model: a bank statement matched against cleared journal lines.

A reconciliation records a bank account's statement balance as of a date,
the set of journal lines cleared against it, and the computed difference
(non-zero = outstanding items). The opening/cleared totals are stored so
the record is an immutable snapshot. Money is integer cents.
"""

import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.account import Account
from app.models.journal import JournalLine


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    statement_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    statement_balance_cents: Mapped[int] = mapped_column(Integer)
    opening_balance_cents: Mapped[int] = mapped_column(Integer)
    cleared_total_cents: Mapped[int] = mapped_column(Integer)
    difference_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    account: Mapped["Account"] = relationship()
    lines: Mapped[list["JournalLine"]] = relationship()

    @property
    def is_balanced(self) -> bool:
        return self.difference_cents == 0

    @property
    def account_number(self) -> str:
        return self.account.number

    @property
    def account_name(self) -> str:
        return self.account.name
