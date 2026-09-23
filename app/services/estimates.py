"""Estimate service — quotes that post nothing until converted to an invoice."""

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.estimate import Estimate, EstimateLine
from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceLineCreate
from app.services.errors import ConflictError, NotFoundError
from app.services.invoices import _resolve_lines, _tax_cents, create_invoice
from app.services.parties import get_customer


def create_estimate(
    db: Session,
    *,
    customer_id: int,
    date: datetime.date,
    tax_rate: float = 0.0,
    lines: list[InvoiceLineCreate],
) -> Estimate:
    customer = get_customer(db, customer_id)
    resolved = _resolve_lines(db, lines)

    estimate = Estimate(customer_id=customer.id, date=date, tax_rate=tax_rate)
    subtotal = 0
    for item_id, description, quantity, unit_price_cents, amount in resolved:
        estimate.lines.append(
            EstimateLine(
                item_id=item_id,
                description=description,
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                amount_cents=amount,
            )
        )
        subtotal += amount
    estimate.subtotal_cents = subtotal
    estimate.tax_cents = _tax_cents(subtotal, tax_rate)
    estimate.total_cents = estimate.subtotal_cents + estimate.tax_cents
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate


def get_estimate(db: Session, estimate_id: int) -> Estimate:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise NotFoundError(f"Estimate {estimate_id} not found")
    return estimate


def list_estimates(
    db: Session,
    *,
    customer_id: int | None = None,
    include_converted: bool = True,
) -> list[Estimate]:
    stmt = select(Estimate)
    if customer_id is not None:
        stmt = stmt.where(Estimate.customer_id == customer_id)
    if not include_converted:
        stmt = stmt.where(Estimate.status == "open")
    stmt = stmt.order_by(Estimate.date.desc(), Estimate.id.desc())
    return list(db.scalars(stmt))


def convert_estimate(db: Session, estimate_id: int) -> Invoice:
    estimate = get_estimate(db, estimate_id)
    if estimate.status != "open":
        raise ConflictError(f"Estimate {estimate_id} has already been converted")
    invoice = create_invoice(
        db,
        customer_id=estimate.customer_id,
        date=datetime.date.today(),
        tax_rate=estimate.tax_rate,
        lines=[
            InvoiceLineCreate(
                item_id=line.item_id,
                description=line.description,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
            )
            for line in estimate.lines
        ],
    )
    estimate.status = "converted"
    estimate.converted_invoice_id = invoice.id
    db.commit()
    db.refresh(estimate)
    return invoice
