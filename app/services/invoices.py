"""Invoice service — AR documents that post through the single journal path.

Create: Dr Accounts Receivable (total incl. tax) / Cr Revenue (subtotal) /
Cr Taxes Payable (tax). Payment: Dr Cash / Cr Accounts Receivable.
Void: reversing entry for the original posting (only while unpaid).
"""

import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLine, InvoicePayment
from app.schemas.invoice import InvoiceLineCreate
from app.schemas.journal import JournalLineCreate
from app.services.accounts import get_account_by_number
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.items import get_item
from app.services.journal import create_journal_entry, void_journal_entry
from app.services.parties import get_customer

AR_NUMBER = "1100"
CASH_NUMBER = "1000"
REVENUE_NUMBER = "4000"
TAX_NUMBER = "2200"


def _tax_cents(subtotal_cents: int, tax_rate: float) -> int:
    if tax_rate == 0:
        return 0
    return int(
        (Decimal(subtotal_cents) * Decimal(str(tax_rate)) / 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _resolve_lines(
    db: Session, lines: list[InvoiceLineCreate]
) -> list[tuple[int | None, str, int, int, int]]:
    """Validate lines and return (item_id, description, qty, unit_price, amount)."""
    resolved = []
    for line in lines:
        description = line.description
        if line.item_id is not None:
            item = get_item(db, line.item_id)
            if description is None:
                description = item.name
        if description is None:
            raise ValidationError("each line needs a description or an item_id")
        amount = line.quantity * line.unit_price_cents
        resolved.append((line.item_id, description, line.quantity, line.unit_price_cents, amount))
    return resolved


def create_invoice(
    db: Session,
    *,
    customer_id: int,
    date: datetime.date,
    due_date: datetime.date | None = None,
    tax_rate: float = 0.0,
    lines: list[InvoiceLineCreate],
) -> Invoice:
    customer = get_customer(db, customer_id)
    resolved = _resolve_lines(db, lines)

    invoice = Invoice(
        customer_id=customer.id,
        date=date,
        due_date=due_date,
        tax_rate=tax_rate,
    )
    subtotal = 0
    for item_id, description, quantity, unit_price_cents, amount in resolved:
        invoice.lines.append(
            InvoiceLine(
                item_id=item_id,
                description=description,
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                amount_cents=amount,
            )
        )
        subtotal += amount
    tax = _tax_cents(subtotal, tax_rate)
    total = subtotal + tax
    if total == 0:
        raise ValidationError("invoice total must be greater than zero")
    invoice.subtotal_cents = subtotal
    invoice.tax_cents = tax
    invoice.total_cents = total
    db.add(invoice)
    db.flush()  # assign invoice.id before posting

    ar = get_account_by_number(db, AR_NUMBER)
    revenue = get_account_by_number(db, REVENUE_NUMBER)
    entry_lines = [
        JournalLineCreate(
            account_id=ar.id, description="Accounts receivable", debit=total, credit=0
        ),
        JournalLineCreate(
            account_id=revenue.id, description="Revenue", debit=0, credit=subtotal
        ),
    ]
    if tax > 0:
        tax_account = get_account_by_number(db, TAX_NUMBER)
        entry_lines.append(
            JournalLineCreate(
                account_id=tax_account.id,
                description="Tax payable",
                debit=0,
                credit=tax,
            )
        )
    entry = create_journal_entry(
        db,
        date=date,
        description=f"Invoice {invoice.id} for {customer.name}",
        lines=entry_lines,
        source_type="invoice",
        source_id=invoice.id,
    )
    invoice.entry_id = entry.id
    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found")
    return invoice


def list_invoices(
    db: Session,
    *,
    customer_id: int | None = None,
    include_voided: bool = True,
) -> list[Invoice]:
    stmt = select(Invoice)
    if customer_id is not None:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if not include_voided:
        stmt = stmt.where(Invoice.is_voided.is_(False))
    stmt = stmt.order_by(Invoice.date.desc(), Invoice.id.desc())
    return list(db.scalars(stmt))


def pay_invoice(
    db: Session,
    invoice_id: int,
    *,
    amount_cents: int,
    date: datetime.date | None = None,
    note: str | None = None,
) -> InvoicePayment:
    invoice = get_invoice(db, invoice_id)
    if invoice.is_voided:
        raise ConflictError(f"Invoice {invoice_id} is voided and cannot be paid")
    remaining = invoice.total_cents - invoice.paid_cents
    if amount_cents > remaining:
        raise ValidationError(
            f"payment of {amount_cents} cents exceeds remaining balance "
            f"of {remaining} cents"
        )

    payment_date = date if date is not None else datetime.date.today()
    cash = get_account_by_number(db, CASH_NUMBER)
    ar = get_account_by_number(db, AR_NUMBER)
    entry = create_journal_entry(
        db,
        date=payment_date,
        description=f"Payment for invoice {invoice.id}",
        lines=[
            JournalLineCreate(
                account_id=cash.id, description="Cash", debit=amount_cents, credit=0
            ),
            JournalLineCreate(
                account_id=ar.id,
                description="Accounts receivable",
                debit=0,
                credit=amount_cents,
            ),
        ],
        source_type="invoice_payment",
        source_id=invoice.id,
    )
    payment = InvoicePayment(
        invoice_id=invoice.id,
        date=payment_date,
        amount_cents=amount_cents,
        note=note,
        entry_id=entry.id,
    )
    invoice.paid_cents += amount_cents
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def void_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    if invoice.is_voided:
        raise ConflictError(f"Invoice {invoice_id} is already voided")
    if invoice.paid_cents > 0:
        raise ConflictError(
            f"Invoice {invoice_id} has payments and cannot be voided"
        )
    if invoice.entry_id is None:
        raise ConflictError(f"Invoice {invoice_id} has no posting entry")
    reversal = void_journal_entry(db, invoice.entry_id)
    invoice.is_voided = True
    invoice.voided_by_entry_id = reversal.id
    db.commit()
    db.refresh(invoice)
    return invoice
