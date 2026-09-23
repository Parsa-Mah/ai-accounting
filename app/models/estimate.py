"""Estimate models (pre-invoice quotes; no ledger posting until converted)."""

import datetime

from sqlalchemy import (
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


class Estimate(Base):
    __tablename__ = "estimates"
    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="ck_estimate_subtotal_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_estimate_tax_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_estimate_total_non_negative"),
        CheckConstraint("tax_rate >= 0", name="ck_estimate_tax_rate_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    converted_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped["Customer"] = relationship()
    lines: Mapped[list["EstimateLine"]] = relationship(
        back_populates="estimate",
        cascade="all, delete-orphan",
        order_by="EstimateLine.id",
    )

    @property
    def customer_name(self) -> str:
        return self.customer.name


class EstimateLine(Base):
    __tablename__ = "estimate_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_estimate_line_quantity_positive"),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_estimate_line_price_non_negative"
        ),
        CheckConstraint(
            "amount_cents >= 0", name="ck_estimate_line_amount_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)

    estimate: Mapped["Estimate"] = relationship(back_populates="lines")
