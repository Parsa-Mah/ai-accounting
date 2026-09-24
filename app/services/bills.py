"""Bill service — AP documents that post through the single journal path.

Create: Dr Expense (per line, each line names its own expense account) /
Dr Tax Recoverable (tax) / Cr Accounts Payable (total incl. tax).
Payment: Dr Accounts Payable / Cr Cash.
Void: reversing entry for the original posting (only while unpaid).
"""

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountType
from app.models.bill import Bill, BillLine, BillPayment
from app.schemas.bill import BillLineCreate
from app.schemas.journal import JournalLineCreate
from app.services.accounts import get_account, get_account_by_number
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.items import get_item
from app.services.invoices import tax_cents
from app.services.journal import create_journal_entry, void_journal_entry
from app.services.parties import get_vendor

AP_NUMBER = "2000"
CASH_NUMBER = "1000"
TAX_RECOVERABLE_NUMBER = "2210"


def _resolve_lines(
    db: Session, lines: list[BillLineCreate]
) -> list[tuple[int | None, str, int, int, int, int]]:
    """Validate lines and return (item_id, description, qty, price, amount, expense_account_id)."""
    resolved = []
    for line in lines:
        description = line.description
        if line.item_id is not None:
            item = get_item(db, line.item_id)
            if description is None:
                description = item.name
        if description is None:
            raise ValidationError("each line needs a description or an item_id")
        account = get_account(db, line.expense_account_id)
        if account.type != AccountType.EXPENSE:
            raise ValidationError(
                f"account '{account.number}' is not an expense account"
            )
        amount = line.quantity * line.unit_price_cents
        resolved.append(
            (
                line.item_id,
                description,
                line.quantity,
                line.unit_price_cents,
                amount,
                account.id,
            )
        )
    return resolved


def create_bill(
    db: Session,
    *,
    vendor_id: int,
    date: datetime.date,
    due_date: datetime.date | None = None,
    tax_rate: float = 0.0,
    lines: list[BillLineCreate],
) -> Bill:
    vendor = get_vendor(db, vendor_id)
    resolved = _resolve_lines(db, lines)

    bill = Bill(
        vendor_id=vendor.id,
        date=date,
        due_date=due_date,
        tax_rate=tax_rate,
    )
    subtotal = 0
    for item_id, description, quantity, unit_price_cents, amount, expense_account_id in resolved:
        bill.lines.append(
            BillLine(
                item_id=item_id,
                description=description,
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                amount_cents=amount,
                expense_account_id=expense_account_id,
            )
        )
        subtotal += amount
    tax = tax_cents(subtotal, tax_rate)
    total = subtotal + tax
    if total == 0:
        raise ValidationError("bill total must be greater than zero")
    bill.subtotal_cents = subtotal
    bill.tax_cents = tax
    bill.total_cents = total
    db.add(bill)
    db.flush()  # assign bill.id before posting

    ap = get_account_by_number(db, AP_NUMBER)
    entry_lines = [
        JournalLineCreate(
            account_id=expense_account_id,
            description=f"{description} (expense)",
            debit=amount,
            credit=0,
        )
        for _, description, _, _, amount, expense_account_id in resolved
    ]
    if tax > 0:
        tax_account = get_account_by_number(db, TAX_RECOVERABLE_NUMBER)
        entry_lines.append(
            JournalLineCreate(
                account_id=tax_account.id,
                description="Tax recoverable",
                debit=tax,
                credit=0,
            )
        )
    entry_lines.append(
        JournalLineCreate(
            account_id=ap.id, description="Accounts payable", debit=0, credit=total
        )
    )
    entry = create_journal_entry(
        db,
        date=date,
        description=f"Bill {bill.id} from {vendor.name}",
        lines=entry_lines,
        source_type="bill",
        source_id=bill.id,
    )
    bill.entry_id = entry.id
    db.commit()
    db.refresh(bill)
    return bill


def get_bill(db: Session, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise NotFoundError(f"Bill {bill_id} not found")
    return bill


def list_bills(
    db: Session,
    *,
    vendor_id: int | None = None,
    include_voided: bool = True,
) -> list[Bill]:
    stmt = select(Bill)
    if vendor_id is not None:
        stmt = stmt.where(Bill.vendor_id == vendor_id)
    if not include_voided:
        stmt = stmt.where(Bill.is_voided.is_(False))
    stmt = stmt.order_by(Bill.date.desc(), Bill.id.desc())
    return list(db.scalars(stmt))


def pay_bill(
    db: Session,
    bill_id: int,
    *,
    amount_cents: int,
    date: datetime.date | None = None,
    note: str | None = None,
) -> BillPayment:
    bill = get_bill(db, bill_id)
    if bill.is_voided:
        raise ConflictError(f"Bill {bill_id} is voided and cannot be paid")
    remaining = bill.total_cents - bill.paid_cents
    if amount_cents > remaining:
        raise ValidationError(
            f"payment of {amount_cents} cents exceeds remaining balance "
            f"of {remaining} cents"
        )

    payment_date = date if date is not None else datetime.date.today()
    ap = get_account_by_number(db, AP_NUMBER)
    cash = get_account_by_number(db, CASH_NUMBER)
    entry = create_journal_entry(
        db,
        date=payment_date,
        description=f"Payment for bill {bill.id}",
        lines=[
            JournalLineCreate(
                account_id=ap.id, description="Accounts payable", debit=amount_cents, credit=0
            ),
            JournalLineCreate(
                account_id=cash.id, description="Cash", debit=0, credit=amount_cents
            ),
        ],
        source_type="bill_payment",
        source_id=bill.id,
    )
    payment = BillPayment(
        bill_id=bill.id,
        date=payment_date,
        amount_cents=amount_cents,
        note=note,
        entry_id=entry.id,
    )
    bill.paid_cents += amount_cents
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def void_bill(db: Session, bill_id: int) -> Bill:
    bill = get_bill(db, bill_id)
    if bill.is_voided:
        raise ConflictError(f"Bill {bill_id} is already voided")
    if bill.paid_cents > 0:
        raise ConflictError(f"Bill {bill_id} has payments and cannot be voided")
    if bill.entry_id is None:
        raise ConflictError(f"Bill {bill_id} has no posting entry")
    reversal = void_journal_entry(db, bill.entry_id)
    bill.is_voided = True
    bill.voided_by_entry_id = reversal.id
    db.commit()
    db.refresh(bill)
    return bill
