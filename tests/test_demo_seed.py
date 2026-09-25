"""Tests for the demo data seed (app/seed/demo.py)."""

from sqlalchemy import select

from app.database import Base, SessionLocal, engine, init_db
from app.models.bill import Bill
from app.models.budget import Budget
from app.models.estimate import Estimate
from app.models.invoice import Invoice
from app.models.item import Item
from app.models.journal import JournalEntry
from app.models.party import Customer, Vendor
from app.models.reconciliation import Reconciliation
from app.models.user import User
from app.seed.demo import seed_demo_data
from app.services.auth import setup_user
from app.services.ledger import trial_balance
from app.services.reports import balance_sheet


def _fresh_db():
    Base.metadata.drop_all(engine)


def _open_db():
    return SessionLocal()


def test_seed_demo_data_populates_every_page():
    _fresh_db()
    seed_demo_data()
    db = _open_db()
    try:
        user = db.scalar(select(User).limit(1))
        assert user is not None
        assert user.username == "demo"

        assert len(db.scalars(select(Customer)).all()) == 3
        assert len(db.scalars(select(Vendor)).all()) == 3
        assert len(db.scalars(select(Item)).all()) == 5

        invoices = db.scalars(select(Invoice)).all()
        assert len(invoices) == 5
        statuses = sorted(invoice.status for invoice in invoices)
        assert statuses == ["open", "paid", "paid", "partially_paid", "void"]

        bills = db.scalars(select(Bill)).all()
        assert len(bills) == 4
        assert sorted(bill.status for bill in bills) == ["open", "open", "paid", "paid"]

        estimates = db.scalars(select(Estimate)).all()
        assert len(estimates) == 1
        assert estimates[0].status == "open"

        assert len(db.scalars(select(Budget)).all()) == 4
        assert len(db.scalars(select(JournalEntry)).all()) >= 10
    finally:
        db.close()


def test_seed_demo_data_keeps_the_books_balanced():
    _fresh_db()
    seed_demo_data()
    db = _open_db()
    try:
        tb = trial_balance(db)
        assert tb["balanced"] is True
        assert tb["totals"]["debit"] == tb["totals"]["credit"] > 0

        bs = balance_sheet(db)
        assert bs["balanced"] is True
        assert bs["total_assets"] == bs["total_liabilities"] + bs["total_equity"]
    finally:
        db.close()


def test_seed_demo_data_creates_a_balanced_reconciliation():
    _fresh_db()
    seed_demo_data()
    db = _open_db()
    try:
        recon = db.scalar(select(Reconciliation).limit(1))
        assert recon is not None
        assert recon.difference_cents == 0
        assert recon.is_balanced is True
        assert recon.cleared_total_cents != 0
        assert len(recon.lines) >= 5
    finally:
        db.close()


def test_seed_demo_data_is_idempotent():
    _fresh_db()
    seed_demo_data()
    seed_demo_data()
    db = _open_db()
    try:
        assert len(db.scalars(select(Customer)).all()) == 3
        assert len(db.scalars(select(Invoice)).all()) == 5
        assert len(db.scalars(select(Bill)).all()) == 4
        assert len(db.scalars(select(Reconciliation)).all()) == 1
    finally:
        db.close()


def test_seed_demo_data_keeps_an_existing_user():
    _fresh_db()
    init_db()
    db = _open_db()
    try:
        setup_user(db, "admin", "admin123")
    finally:
        db.close()

    seed_demo_data()

    db = _open_db()
    try:
        user = db.scalar(select(User).limit(1))
        assert user is not None
        assert user.username == "admin"
        assert len(db.scalars(select(Invoice)).all()) == 5
    finally:
        db.close()
