"""Period locking tests: model, service, and the posting/void/reconciliation guards.

Phase 2 batch 1 — the lock/unlock REST endpoints and the MCP tools land in
later batches, so lock/unlock are exercised here at the service level and
the guards are exercised through the existing endpoints (the real paths).
"""

import datetime

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.audit import AuditLog
from app.services import periods as periods_service
from app.services.errors import ConflictError, NotFoundError


def _lock_month(year: int, month: int) -> None:
    db = SessionLocal()
    try:
        periods_service.lock_period(db, year=year, month=month)
    finally:
        db.close()


def _unlock_month(year: int, month: int) -> None:
    db = SessionLocal()
    try:
        periods_service.unlock_period(db, year=year, month=month)
    finally:
        db.close()


def _last_month() -> tuple[int, int]:
    """(year, month) of the month before the current one."""
    prev = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    return prev.year, prev.month


def _last_month_date() -> datetime.date:
    """A date inside last month (its last day)."""
    return datetime.date.today().replace(day=1) - datetime.timedelta(days=1)


def _audit_rows(**filters):
    """Audit rows matching the given column values, oldest first."""
    db = SessionLocal()
    try:
        stmt = select(AuditLog)
        for column, value in filters.items():
            stmt = stmt.where(getattr(AuditLog, column) == value)
        return list(db.execute(stmt.order_by(AuditLog.id)).scalars())
    finally:
        db.close()


def _account_ids(client) -> dict[str, int]:
    """Map account number -> id from the seeded chart of accounts."""
    response = client.get("/api/accounts")
    assert response.status_code == 200
    return {account["number"]: account["id"] for account in response.json()}


def _post_journal(client, accounts, date, description="Period test entry"):
    return client.post(
        "/api/journal",
        json={
            "date": date.isoformat(),
            "description": description,
            "lines": [
                {"account_id": accounts["5100"], "debit": 10000, "credit": 0},
                {"account_id": accounts["1000"], "debit": 0, "credit": 10000},
            ],
        },
    )


def _cash_line_id(client, entry_id: int) -> int:
    """The Cash (1000) line id of a journal entry (Cash is the bank account)."""
    response = client.get(f"/api/journal/{entry_id}")
    assert response.status_code == 200
    lines = response.json()["lines"]
    return next(line["id"] for line in lines if line["account_number"] == "1000")


def test_lock_creates_period_and_is_idempotent(client) -> None:
    db = SessionLocal()
    try:
        period = periods_service.lock_period(db, year=2030, month=2)
        assert period.is_locked is True
        assert period.locked_at is not None

        again = periods_service.lock_period(db, year=2030, month=2)
        assert again.id == period.id
        assert again.is_locked is True
    finally:
        db.close()


def test_unlock_semantics(client) -> None:
    db = SessionLocal()
    try:
        with pytest.raises(NotFoundError):
            periods_service.unlock_period(db, year=2031, month=1)

        periods_service.lock_period(db, year=2031, month=1)
        period = periods_service.unlock_period(db, year=2031, month=1)
        assert period.is_locked is False
        assert period.locked_at is None

        with pytest.raises(ConflictError):
            periods_service.unlock_period(db, year=2031, month=1)
    finally:
        db.close()


def test_list_periods_ordered(client) -> None:
    _lock_month(2030, 5)
    _lock_month(2029, 11)
    _lock_month(2030, 1)
    db = SessionLocal()
    try:
        periods = periods_service.list_periods(db)
        assert [(p.year, p.month) for p in periods] == [
            (2029, 11),
            (2030, 1),
            (2030, 5),
        ]
    finally:
        db.close()


def test_journal_entry_in_locked_month_rejected(client) -> None:
    accounts = _account_ids(client)
    today = datetime.date.today()
    _lock_month(today.year, today.month)

    response = _post_journal(client, accounts, today)
    assert response.status_code == 409
    assert "locked" in response.json()["detail"]

    _unlock_month(today.year, today.month)
    response = _post_journal(client, accounts, today)
    assert response.status_code == 201


def test_journal_entry_outside_locked_month_allowed(client) -> None:
    accounts = _account_ids(client)
    year, month = _last_month()
    _lock_month(year, month)

    response = _post_journal(client, accounts, datetime.date.today())
    assert response.status_code == 201


def test_invoice_in_locked_month_rejected(client) -> None:
    response = client.post("/api/customers", json={"name": "Period Customer"})
    assert response.status_code == 201
    customer_id = response.json()["id"]
    today = datetime.date.today()
    _lock_month(today.year, today.month)

    response = client.post(
        "/api/invoices",
        json={
            "customer_id": customer_id,
            "date": today.isoformat(),
            "tax_rate": 0,
            "lines": [
                {"description": "Consulting", "quantity": 1, "unit_price_cents": 10000}
            ],
        },
    )
    assert response.status_code == 409
    assert "locked" in response.json()["detail"]


def test_void_original_in_locked_month_rejected(client) -> None:
    accounts = _account_ids(client)
    year, month = _last_month()
    response = _post_journal(client, accounts, _last_month_date())
    assert response.status_code == 201
    entry_id = response.json()["id"]
    _lock_month(year, month)

    response = client.post(f"/api/journal/{entry_id}/void")
    assert response.status_code == 409
    assert "locked" in response.json()["detail"]


def test_void_reversal_in_locked_month_rejected(client) -> None:
    """The original month is open, but the reversal is dated today."""
    accounts = _account_ids(client)
    response = _post_journal(client, accounts, _last_month_date())
    assert response.status_code == 201
    entry_id = response.json()["id"]
    today = datetime.date.today()
    _lock_month(today.year, today.month)

    response = client.post(f"/api/journal/{entry_id}/void")
    assert response.status_code == 409
    assert "locked" in response.json()["detail"]


def test_reconciliation_in_locked_month_rejected(client) -> None:
    accounts = _account_ids(client)
    year, month = _last_month()
    date = _last_month_date()
    response = _post_journal(client, accounts, date)
    assert response.status_code == 201
    line_id = _cash_line_id(client, response.json()["id"])
    _lock_month(year, month)

    response = client.post(
        "/api/reconciliation",
        json={
            "account_id": accounts["1000"],
            "statement_date": date.isoformat(),
            "statement_balance_cents": 0,
            "line_ids": [line_id],
        },
    )
    assert response.status_code == 409
    assert "locked" in response.json()["detail"]


def test_delete_reconciliation_in_locked_month_rejected(client) -> None:
    accounts = _account_ids(client)
    year, month = _last_month()
    date = _last_month_date()
    response = _post_journal(client, accounts, date)
    assert response.status_code == 201
    line_id = _cash_line_id(client, response.json()["id"])

    response = client.post(
        "/api/reconciliation",
        json={
            "account_id": accounts["1000"],
            "statement_date": date.isoformat(),
            "statement_balance_cents": 0,
            "line_ids": [line_id],
        },
    )
    assert response.status_code == 201
    recon_id = response.json()["id"]
    _lock_month(year, month)

    response = client.delete(f"/api/reconciliation/{recon_id}")
    assert response.status_code == 409


def test_lock_endpoint_creates_and_is_idempotent(client) -> None:
    response = client.post("/api/periods/2030/2/lock")
    assert response.status_code == 201
    body = response.json()
    assert (body["year"], body["month"]) == (2030, 2)
    assert body["is_locked"] is True
    assert body["locked_at"] is not None
    period_id = body["id"]

    response = client.post("/api/periods/2030/2/lock")
    assert response.status_code == 201
    assert response.json()["id"] == period_id


def test_unlock_endpoint(client) -> None:
    client.post("/api/periods/2030/3/lock")

    response = client.post("/api/periods/2030/3/unlock")
    assert response.status_code == 200
    body = response.json()
    assert body["is_locked"] is False
    assert body["locked_at"] is None

    # The row is kept after unlock; unlocking again is a 409.
    response = client.post("/api/periods/2030/3/unlock")
    assert response.status_code == 409


def test_unlock_unknown_period_404(client) -> None:
    response = client.post("/api/periods/2031/7/unlock")
    assert response.status_code == 404


def test_invalid_month_422(client) -> None:
    assert client.post("/api/periods/2030/0/lock").status_code == 422
    assert client.post("/api/periods/2030/13/lock").status_code == 422
    assert client.post("/api/periods/2030/13/unlock").status_code == 422


def test_list_periods_endpoint(client) -> None:
    client.post("/api/periods/2030/5/lock")
    client.post("/api/periods/2029/11/lock")

    response = client.get("/api/periods")
    assert response.status_code == 200
    assert [(p["year"], p["month"]) for p in response.json()] == [
        (2029, 11),
        (2030, 5),
    ]


def test_periods_require_auth(app_client) -> None:
    assert app_client.get("/api/periods").status_code == 401
    assert app_client.post("/api/periods/2030/1/lock").status_code == 401
    assert app_client.post("/api/periods/2030/1/unlock").status_code == 401


def test_lock_unlock_audited_as_user(client) -> None:
    """Lock (create) and unlock (update) land in the audit trail as the user."""
    client.post("/api/periods/2030/4/lock")
    client.post("/api/periods/2030/4/unlock")

    rows = _audit_rows(model="Period", actor="user:1")
    assert [row.action for row in rows] == ["create", "update"]
