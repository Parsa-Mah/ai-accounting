"""Audit trail tests: actor identity + the centralized Session hook.

Every committed write lands in the append-only ``audit_log`` table:
who acted (``user:<id>`` web, ``ai:<client>`` MCP, ``system`` seed),
what action (create/update/delete), which model + record, when.
"""

import datetime

import pytest
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.mcp.server import build_server
from app.models.audit import AuditLog
from app.seed.demo import seed_demo_data
from mcp import Client

_SKIP_MODELS = ("JournalLine", "InvoiceLine", "BillLine", "EstimateLine")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def write_server(monkeypatch):
    """MCP server against a fresh demo-seeded DB with MCP_ALLOW_WRITE=1."""
    monkeypatch.setenv("MCP_ALLOW_WRITE", "1")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_demo_data()
    return build_server()


def _audit_rows(**filters):
    """Audit rows matching the given column values, oldest first.

    Always filter: every fresh test DB already holds ``system``/
    ``create``/``Account`` rows from COA seeding (plus a
    ``system``/``create``/``User`` row from the ``client`` fixture's
    ``/api/auth/setup``, and many more from ``seed_demo_data``).
    """
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


def test_web_write_is_audited_as_user(client) -> None:
    """Gate test: a web write produces exactly one audit row as user:1."""
    accounts = _account_ids(client)
    response = client.post(
        "/api/journal",
        json={
            "date": datetime.date.today().isoformat(),
            "description": "Audit gate entry",
            "lines": [
                {"account_id": accounts["5100"], "debit": 10000, "credit": 0},
                {"account_id": accounts["1000"], "debit": 0, "credit": 10000},
            ],
        },
    )
    assert response.status_code == 201
    entry_id = response.json()["id"]

    rows = _audit_rows(model="JournalEntry", record_id=entry_id, action="create")
    assert len(rows) == 1
    assert rows[0].actor == "user:1"


@pytest.mark.anyio
async def test_mcp_write_is_audited_as_ai(write_server, monkeypatch) -> None:
    """MCP writes are audited as ai:<client>, with the env read at call time."""
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_journal_entry",
            {
                "date": "2026-09-01",
                "description": "MCP audit entry",
                "lines": [
                    {"account": "5100", "debit_cents": 10000, "credit_cents": 0},
                    {"account": "1000", "debit_cents": 0, "credit_cents": 10000},
                ],
            },
        )
        assert result.is_error is False
        entry_id = result.structured_content["entry_id"]

        rows = _audit_rows(model="JournalEntry", record_id=entry_id, action="create")
        assert len(rows) == 1
        assert rows[0].actor == "ai:mcp"

        # Env is read at call time, so patching after build_server() works.
        monkeypatch.setenv("MCP_CLIENT_NAME", "opencode")
        result = await client.call_tool(
            "create_journal_entry",
            {
                "date": "2026-09-02",
                "description": "MCP audit entry two",
                "lines": [
                    {"account": "5100", "debit_cents": 10000, "credit_cents": 0},
                    {"account": "1000", "debit_cents": 0, "credit_cents": 10000},
                ],
            },
        )
        assert result.is_error is False
        entry_id = result.structured_content["entry_id"]

    rows = _audit_rows(model="JournalEntry", record_id=entry_id, action="create")
    assert len(rows) == 1
    assert rows[0].actor == "ai:opencode"


def test_budget_lifecycle_create_update_delete(client) -> None:
    """A create/update/delete lifecycle yields exactly those three rows, in order."""
    accounts = _account_ids(client)
    response = client.post(
        "/api/budgets",
        json={
            "account_id": accounts["5100"],
            "budget_start": "2026-10-01",
            "budget_end": "2026-10-31",
            "budget_cents": 200000,
        },
    )
    assert response.status_code == 201
    budget_id = response.json()["id"]

    response = client.patch(
        f"/api/budgets/{budget_id}", json={"budget_cents": 250000}
    )
    assert response.status_code == 200

    response = client.delete(f"/api/budgets/{budget_id}")
    assert response.status_code == 204

    rows = _audit_rows(model="Budget", record_id=budget_id)
    assert [row.action for row in rows] == ["create", "update", "delete"]
    assert all(row.actor == "user:1" for row in rows)


def test_one_row_per_change_no_line_items(client) -> None:
    """An invoice posts one row per distinct change; line items are skipped.

    ``create_invoice`` flushes mid-creation (to assign ``invoice.id``
    before posting) and then sets ``entry_id`` on commit, so the invoice
    legitimately yields a ``create`` and an ``update`` — one row each.
    """
    response = client.post("/api/customers", json={"name": "Audit Customer"})
    assert response.status_code == 201
    customer_id = response.json()["id"]

    response = client.post(
        "/api/invoices",
        json={
            "customer_id": customer_id,
            "date": "2026-10-01",
            "tax_rate": 10,
            "lines": [
                {"description": "Consulting", "quantity": 2, "unit_price_cents": 10000},
                {"description": "Hosting", "quantity": 1, "unit_price_cents": 5000},
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    invoice_id = body["id"]
    entry_id = body["entry_id"]

    assert [row.action for row in _audit_rows(model="Invoice", record_id=invoice_id)] == [
        "create",
        "update",
    ]
    assert (
        len(_audit_rows(model="JournalEntry", record_id=entry_id, action="create"))
        == 1
    )
    for model in _SKIP_MODELS:
        assert _audit_rows(model=model) == []

    # No duplicate (model, record_id, action) rows anywhere in the log.
    db = SessionLocal()
    try:
        rows = list(db.execute(select(AuditLog)).scalars())
    finally:
        db.close()
    keys = [(row.model, row.record_id, row.action) for row in rows]
    assert len(keys) == len(set(keys))


def test_seed_audited_as_system(app_client) -> None:
    """The COA seed (26 accounts) is audited as the system actor."""
    rows = _audit_rows(model="Account", actor="system", action="create")
    assert len(rows) == 26


def test_audit_list_requires_auth(app_client) -> None:
    assert app_client.get("/api/audit").status_code == 401


def test_audit_list_newest_first(client) -> None:
    """Rows come back newest-first (id desc) with the full field set."""
    response = client.get("/api/audit")
    assert response.status_code == 200
    rows = response.json()
    assert rows, "the COA seed must have produced audit rows"
    ids = [row["id"] for row in rows]
    assert ids == sorted(ids, reverse=True)
    assert set(rows[0]) == {
        "id",
        "timestamp",
        "actor",
        "action",
        "model",
        "record_id",
    }


def test_audit_list_filters(client) -> None:
    """Exact-match actor/model/action filters + inclusive day range + limit."""
    accounts = _account_ids(client)
    response = client.post(
        "/api/journal",
        json={
            "date": "2026-10-01",
            "description": "Audit list entry",
            "lines": [
                {"account_id": accounts["5100"], "debit": 10000, "credit": 0},
                {"account_id": accounts["1000"], "debit": 0, "credit": 10000},
            ],
        },
    )
    assert response.status_code == 201
    entry_id = response.json()["id"]

    rows = client.get(
        "/api/audit",
        params={"actor": "user:1", "model": "JournalEntry", "action": "create"},
    ).json()
    assert [row["record_id"] for row in rows] == [entry_id]

    # An unknown actor matches nothing.
    assert client.get("/api/audit", params={"actor": "user:999"}).json() == []

    # The write committed "now" (UTC timestamp), so a range on the newest
    # row's own date contains it and a past range does not. (Local "today"
    # can differ from the UTC date near midnight.)
    newest_day = client.get("/api/audit").json()[0]["timestamp"][:10]
    assert client.get(
        "/api/audit", params={"date_from": newest_day, "date_to": newest_day}
    ).json()
    assert (
        client.get(
            "/api/audit", params={"date_from": "2020-01-01", "date_to": "2020-01-31"}
        ).json()
        == []
    )

    assert len(client.get("/api/audit", params={"limit": 1}).json()) == 1
    assert client.get("/api/audit", params={"limit": 0}).status_code == 422
