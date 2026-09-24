"""Budget model: a planned amount for an account over a date range.

Budgets are planning data — they post nothing to the ledger. Actual
activity for the range is computed from journal lines when the budget
report is requested. Money is integer cents.
"""

import datetime

from sqlalchemy import (
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


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("budget_cents >= 0", name="ck_budget_cents_non_negative"),
        CheckConstraint("budget_start <= budget_end", name="ck_budget_range_ordered"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    budget_start: Mapped[datetime.date] = mapped_column(Date, index=True)
    budget_end: Mapped[datetime.date] = mapped_column(Date, index=True)
    budget_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship()

    @property
    def account_number(self) -> str:
        return self.account.number

    @property
    def account_name(self) -> str:
        return self.account.name

    @property
    def account_type(self) -> str:
        return self.account.type.value
