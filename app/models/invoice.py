"""Invoice models: invoice header, lines, and payments.

Invoices post to the ledger on creation (Dr AR incl. tax / Cr Revenue /
Cr Tax Payable) and on payment (Dr Cash / Cr AR) through the single
journal posting path. Money is integer cents.
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
from app.models.party import Customer


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="ck_invoice_subtotal_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_invoice_tax_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_invoice_total_non_negative"),
        CheckConstraint("paid_cents >= 0", name="ck_invoice_paid_non_negative"),
        CheckConstraint("tax_rate >= 0", name="ck_invoice_tax_rate_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    paid_cents: Mapped[int] = mapped_column(Integer, default=0)
    is_voided: Mapped[bool] = mapped_column(Boolean, default=False)
    # Nullable only transiently: the invoice is flushed (to get its id) before
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

    customer: Mapped["Customer"] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.id",
    )
    payments: Mapped[list["InvoicePayment"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoicePayment.id",
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
    def customer_name(self) -> str:
        return self.customer.name


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_line_quantity_positive"),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_invoice_line_price_non_negative"
        ),
        CheckConstraint(
            "amount_cents >= 0", name="ck_invoice_line_amount_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_invoice_payment_amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
