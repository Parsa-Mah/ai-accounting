"""Demo data seed, invoked by ``python main.py --seed``.

Creates a demo user (only if none exists) plus a small but complete set of
customers, vendors, items, invoices, bills, an estimate, budgets, manual
journal entries, and a balanced bank reconciliation. Idempotent: if the
marker customer already exists, the seed prints a message and exits.
"""

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models.journal import JournalEntry, JournalLine
from app.models.party import Customer
from app.services.accounts import get_account_by_number
from app.services.auth import get_user, setup_user
from app.services.bills import create_bill, pay_bill
from app.services.budgets import create_budget
from app.services.estimates import create_estimate
from app.services.invoices import create_invoice, pay_invoice, void_invoice
from app.services.items import create_item
from app.services.journal import create_journal_entry
from app.services.parties import create_customer, create_vendor
from app.services.reconciliation import create_reconciliation
from app.schemas.bill import BillLineCreate
from app.schemas.budget import BudgetCreate
from app.schemas.invoice import InvoiceLineCreate
from app.schemas.item import ItemCreate
from app.schemas.journal import JournalLineCreate
from app.schemas.party import CustomerCreate, VendorCreate

MARKER_CUSTOMER = "Acme Corporation"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"

TODAY = datetime.date.today()


def _first_of_month(offset: int) -> datetime.date:
    index = TODAY.year * 12 + (TODAY.month - 1) + offset
    year, month = divmod(index, 12)
    return datetime.date(year, month + 1, 1)


def _end_of_month(offset: int) -> datetime.date:
    return _first_of_month(offset + 1) - datetime.timedelta(days=1)


def _on(month_offset: int, day: int) -> datetime.date:
    return min(_first_of_month(month_offset) + datetime.timedelta(days=day - 1), TODAY)


def _seed_parties(db: Session) -> tuple[dict[str, int], dict[str, int]]:
    customers: dict[str, int] = {}
    for name, email in [
        ("Acme Corporation", "billing@acme.example"),
        ("Globex Inc", "accounts@globex.example"),
        ("Initech LLC", "ap@initech.example"),
    ]:
        customers[name] = create_customer(db, CustomerCreate(name=name, email=email)).id
    vendors: dict[str, int] = {}
    for name, email in [
        ("CloudHost Inc", "billing@cloudhost.example"),
        ("City Power & Light", "billing@citypower.example"),
        ("OfficeMax Supplies", "accounts@officemax.example"),
    ]:
        vendors[name] = create_vendor(db, VendorCreate(name=name, email=email)).id
    return customers, vendors


def _seed_items(db: Session) -> dict[str, int]:
    items: dict[str, int] = {}
    for name, price, description in [
        ("Consulting (day)", 25000, "Consulting service, billed per day"),
        ("Website Design", 500000, "Full website design and build"),
        ("Logo Design", 150000, "Brand logo design package"),
        ("Office Supplies", 0, "Assorted office supplies"),
        ("Cloud Hosting (monthly)", 9900, "Managed cloud hosting, monthly"),
    ]:
        items[name] = create_item(
            db, ItemCreate(name=name, unit_price_cents=price, description=description)
        ).id
    return items


def _seed_manual_entries(db: Session) -> None:
    cash = get_account_by_number(db, "1000")
    capital = get_account_by_number(db, "3000")
    equipment = get_account_by_number(db, "1500")
    rent = get_account_by_number(db, "5100")

    create_journal_entry(
        db,
        date=_on(-2, 3),
        description="Owner capital injection",
        lines=[
            JournalLineCreate(account_id=cash.id, description="Cash", debit=2500000, credit=0),
            JournalLineCreate(account_id=capital.id, description="Owner's capital", debit=0, credit=2500000),
        ],
    )
    create_journal_entry(
        db,
        date=_on(-2, 10),
        description="Purchased office equipment",
        lines=[
            JournalLineCreate(account_id=equipment.id, description="Equipment", debit=800000, credit=0),
            JournalLineCreate(account_id=cash.id, description="Cash", debit=0, credit=800000),
        ],
    )
    for month_offset in (-1, 0):
        create_journal_entry(
            db,
            date=_on(month_offset, 5),
            description="Monthly rent",
            lines=[
                JournalLineCreate(account_id=rent.id, description="Rent", debit=200000, credit=0),
                JournalLineCreate(account_id=cash.id, description="Cash", debit=0, credit=200000),
            ],
        )


def _seed_documents(
    db: Session,
    customers: dict[str, int],
    vendors: dict[str, int],
    items: dict[str, int],
) -> None:
    consulting = items["Consulting (day)"]
    website = items["Website Design"]
    logo = items["Logo Design"]
    supplies = items["Office Supplies"]
    hosting = items["Cloud Hosting (monthly)"]
    software = get_account_by_number(db, "5700")
    utilities = get_account_by_number(db, "5300")
    supplies_account = get_account_by_number(db, "5400")

    create_estimate(
        db,
        customer_id=customers["Globex Inc"],
        date=_on(0, 5),
        lines=[
            InvoiceLineCreate(item_id=website, quantity=1, unit_price_cents=500000),
            InvoiceLineCreate(item_id=consulting, quantity=10, unit_price_cents=25000),
        ],
    )

    inv1 = create_invoice(
        db,
        customer_id=customers["Acme Corporation"],
        date=_on(-2, 15),
        due_date=_on(-2, 28),
        tax_rate=8.0,
        lines=[InvoiceLineCreate(item_id=consulting, quantity=10, unit_price_cents=25000)],
    )
    pay_invoice(db, inv1.id, amount_cents=inv1.total_cents, date=_on(-1, 5), note="Bank transfer")

    inv2 = create_invoice(
        db,
        customer_id=customers["Globex Inc"],
        date=_on(-1, 8),
        due_date=_on(-1, 28),
        lines=[InvoiceLineCreate(item_id=logo, quantity=1, unit_price_cents=150000)],
    )
    pay_invoice(db, inv2.id, amount_cents=80000, date=_on(-1, 20), note="Partial payment")

    create_invoice(
        db,
        customer_id=customers["Initech LLC"],
        date=_on(-1, 25),
        due_date=_on(0, 10),
        tax_rate=8.0,
        lines=[
            InvoiceLineCreate(item_id=website, quantity=1, unit_price_cents=500000),
            InvoiceLineCreate(item_id=consulting, quantity=20, unit_price_cents=25000),
        ],
    )

    inv4 = create_invoice(
        db,
        customer_id=customers["Acme Corporation"],
        date=_on(0, 10),
        lines=[InvoiceLineCreate(item_id=consulting, quantity=5, unit_price_cents=25000)],
    )
    void_invoice(db, inv4.id)

    inv5 = create_invoice(
        db,
        customer_id=customers["Initech LLC"],
        date=_on(0, 12),
        lines=[InvoiceLineCreate(item_id=consulting, quantity=4, unit_price_cents=25000)],
    )
    pay_invoice(db, inv5.id, amount_cents=inv5.total_cents, date=_on(0, 15), note="Bank transfer")

    bill1 = create_bill(
        db,
        vendor_id=vendors["CloudHost Inc"],
        date=_on(-2, 20),
        lines=[
            BillLineCreate(
                item_id=hosting, quantity=3, unit_price_cents=9900, expense_account_id=software.id
            )
        ],
    )
    pay_bill(db, bill1.id, amount_cents=bill1.total_cents, date=_on(-1, 3), note="Card payment")

    bill2 = create_bill(
        db,
        vendor_id=vendors["City Power & Light"],
        date=_on(-1, 12),
        lines=[
            BillLineCreate(
                description="Electricity",
                quantity=1,
                unit_price_cents=45000,
                expense_account_id=utilities.id,
            )
        ],
    )
    pay_bill(db, bill2.id, amount_cents=bill2.total_cents, date=_on(-1, 25), note="Auto-pay")

    create_bill(
        db,
        vendor_id=vendors["OfficeMax Supplies"],
        date=_on(0, 8),
        lines=[
            BillLineCreate(
                item_id=supplies, quantity=1, unit_price_cents=32500, expense_account_id=supplies_account.id
            )
        ],
    )
    create_bill(
        db,
        vendor_id=vendors["CloudHost Inc"],
        date=_on(0, 15),
        lines=[
            BillLineCreate(
                item_id=hosting, quantity=1, unit_price_cents=9900, expense_account_id=software.id
            )
        ],
    )


def _seed_budgets(db: Session) -> None:
    rent = get_account_by_number(db, "5100")
    software = get_account_by_number(db, "5700")
    marketing = get_account_by_number(db, "5500")

    create_budget(
        db,
        BudgetCreate(
            account_id=rent.id,
            budget_start=_first_of_month(0),
            budget_end=_end_of_month(0),
            budget_cents=200000,
            note="Monthly rent",
        ),
    )
    create_budget(
        db,
        BudgetCreate(
            account_id=software.id,
            budget_start=_first_of_month(0),
            budget_end=_end_of_month(0),
            budget_cents=15000,
            note="Hosting and subscriptions",
        ),
    )
    create_budget(
        db,
        BudgetCreate(
            account_id=marketing.id,
            budget_start=_first_of_month(0),
            budget_end=_end_of_month(0),
            budget_cents=50000,
            note="Advertising and events",
        ),
    )
    create_budget(
        db,
        BudgetCreate(
            account_id=rent.id,
            budget_start=_first_of_month(-1),
            budget_end=_end_of_month(-1),
            budget_cents=200000,
            note="Monthly rent",
        ),
    )


def _seed_reconciliation(db: Session) -> None:
    cash = get_account_by_number(db, "1000")
    statement_date = _end_of_month(-1)
    rows = db.execute(
        select(JournalLine.id, JournalLine.debit, JournalLine.credit)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == cash.id, JournalEntry.date <= statement_date)
        .order_by(JournalLine.id)
    ).all()
    if not rows:
        return
    balance = sum(row[1] - row[2] for row in rows)
    create_reconciliation(
        db,
        account_id=cash.id,
        statement_date=statement_date,
        statement_balance_cents=balance,
        line_ids=[row[0] for row in rows],
        note=f"{statement_date:%B %Y} bank statement",
    )


def seed_demo_data() -> None:
    init_db()
    db = SessionLocal()
    try:
        marker = db.scalar(select(Customer).where(Customer.name == MARKER_CUSTOMER))
        if marker is not None:
            print("Demo data already present — nothing to seed.")
            return

        if get_user(db) is None:
            setup_user(db, DEMO_USERNAME, DEMO_PASSWORD)

        customers, vendors = _seed_parties(db)
        items = _seed_items(db)
        _seed_manual_entries(db)
        _seed_documents(db, customers, vendors, items)
        _seed_budgets(db)
        _seed_reconciliation(db)

        print("Demo data seeded successfully.")
        print(f"  Login: {DEMO_USERNAME} / {DEMO_PASSWORD}")
        print("  3 customers, 3 vendors, 5 items, 5 invoices, 4 bills,")
        print("  1 estimate, 4 budgets, 4 manual journal entries,")
        print("  1 balanced bank reconciliation.")
    finally:
        db.close()
