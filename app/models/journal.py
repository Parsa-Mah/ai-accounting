"""Journal entry and line models (the double-entry core).

Money is stored as integer cents end-to-end. Each line is debit-only or
credit-only (enforced by a CHECK constraint); an entry must balance.
"""

import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.account import Account


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_voided: Mapped[bool] = mapped_column(Boolean, default=False)
    voided_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.id",
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_line_non_negative"),
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_journal_line_debit_xor_credit",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id"), index=True
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    debit: Mapped[int] = mapped_column(Integer, default=0)
    credit: Mapped[int] = mapped_column(Integer, default=0)
    cleared: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciliation_id: Mapped[int | None] = mapped_column(
        ForeignKey("reconciliations.id"), nullable=True
    )

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["Account"] = relationship()

    @property
    def account_number(self) -> str:
        return self.account.number

    @property
    def account_name(self) -> str:
        return self.account.name
