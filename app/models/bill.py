"""Bill models: bill header, lines, and payments.

Bills post to the ledger on creation (Dr Expense per line / Dr Tax
Recoverable / Cr AP) and on payment (Dr AP / Cr Cash) through the single
journal posting path. Each line names its own expense account. Money is
integer cents.
"""

import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.party import Vendor


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="ck_bill_subtotal_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_bill_tax_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_bill_total_non_negative"),
        CheckConstraint("paid_cents >= 0", name="ck_bill_paid_non_negative"),
        CheckConstraint("tax_rate >= 0", name="ck_bill_tax_rate_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    paid_cents: Mapped[int] = mapped_column(Integer, default=0)
    is_voided: Mapped[bool] = mapped_column(Boolean, default=False)
    # Nullable only transiently: the bill is flushed (to get its id) before
    # its posting entry exists, and entry_id is set in the same transaction.
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    voided_by_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vendor: Mapped["Vendor"] = relationship()
    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillLine.id",
    )
    payments: Mapped[list["BillPayment"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillPayment.id",
    )

    @property
    def status(self) -> str:
        if self.is_voided:
            return "void"
        if self.paid_cents >= self.total_cents:
            return "paid"
        if self.paid_cents > 0:
            return "partially_paid"
        return "open"

    @property
    def vendor_name(self) -> str:
        return self.vendor.name


class BillLine(Base):
    __tablename__ = "bill_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_bill_line_quantity_positive"),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_bill_line_price_non_negative"
        ),
        CheckConstraint(
            "amount_cents >= 0", name="ck_bill_line_amount_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    expense_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))

    bill: Mapped["Bill"] = relationship(back_populates="lines")


class BillPayment(Base):
    __tablename__ = "bill_payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_bill_payment_amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bill: Mapped["Bill"] = relationship(back_populates="payments")
