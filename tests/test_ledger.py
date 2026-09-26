"""Tests for the ledger API (general ledger and trial balance)."""

from datetime import date

from app.database import SessionLocal
from app.services import ledger as ledger_service


def _account_id(client, number: str) -> int:
    accounts = {a["number"]: a for a in client.get("/api/accounts").json()}
    return accounts[number]["id"]


def _post(client, date: str, description: str, lines: list[tuple[str, int, int]]):
    payload = {
        "date": date,
        "description": description,
        "lines": [
            {"account_id": _account_id(client, number), "debit": debit, "credit": credit}
            for number, debit, credit in lines
        ],
    }
    response = client.post("/api/journal", json=payload)
    assert response.status_code == 201
    return response.json()


def _seed_basic(client):
    """Capital 1_000_000, rent 100_000, sale 400_000 (all touching Cash)."""
    capital = _post(
        client, "2026-01-05", "Owner investment", [("1000", 1000000, 0), ("3000", 0, 1000000)]
    )
    rent = _post(
        client, "2026-01-15", "Pay rent", [("5100", 100000, 0), ("1000", 0, 100000)]
    )
    sale = _post(
        client, "2026-02-10", "Sale", [("1000", 400000, 0), ("4000", 0, 400000)]
    )
    return capital, rent, sale


def test_general_ledger_running_balance(client):
    _seed_basic(client)
    cash = _account_id(client, "1000")
    response = client.get(f"/api/ledger/accounts/{cash}/transactions")
    assert response.status_code == 200
    body = response.json()
    assert body["account_number"] == "1000"
    assert body["account_name"] == "Cash"
    assert body["account_type"] == "asset"
    assert body["opening_balance"] == 0
    assert [line["balance"] for line in body["lines"]] == [1000000, 900000, 1300000]
    assert body["closing_balance"] == 1300000
    assert [line["entry_description"] for line in body["lines"]] == [
        "Owner investment",
        "Pay rent",
        "Sale",
    ]


def test_general_ledger_date_range_opening_balance(client):
    _seed_basic(client)
    cash = _account_id(client, "1000")
    response = client.get(
        f"/api/ledger/accounts/{cash}/transactions",
        params={"date_from": "2026-01-15"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["opening_balance"] == 1000000
    assert len(body["lines"]) == 2
    assert [line["balance"] for line in body["lines"]] == [900000, 1300000]
    assert body["closing_balance"] == 1300000


def test_general_ledger_unknown_account(client):
    response = client.get("/api/ledger/accounts/999999/transactions")
    assert response.status_code == 404


def test_trial_balance_balanced(client):
    _seed_basic(client)
    response = client.get("/api/ledger/trial-balance")
    assert response.status_code == 200
    body = response.json()
    assert body["balanced"] is True
    by_number = {row["number"]: row for row in body["rows"]}
    assert by_number["1000"]["debit"] == 1300000
    assert by_number["1000"]["credit"] == 0
    assert by_number["3000"]["debit"] == 0
    assert by_number["3000"]["credit"] == 1000000
    assert by_number["4000"]["credit"] == 400000
    assert by_number["5100"]["debit"] == 100000
    assert body["totals"] == {"debit": 1400000, "credit": 1400000}


def test_trial_balance_as_of(client):
    _seed_basic(client)
    response = client.get("/api/ledger/trial-balance", params={"as_of": "2026-01-31"})
    assert response.status_code == 200
    body = response.json()
    assert body["balanced"] is True
    by_number = {row["number"]: row for row in body["rows"]}
    assert set(by_number) == {"1000", "3000", "5100"}
    assert by_number["1000"]["debit"] == 900000
    assert body["totals"] == {"debit": 1000000, "credit": 1000000}


def test_general_ledger_excludes_voided_when_requested(client):
    _, rent, _ = _seed_basic(client)
    response = client.post(f"/api/journal/{rent['id']}/void")
    assert response.status_code == 201

    cash = _account_id(client, "1000")
    default = client.get(f"/api/ledger/accounts/{cash}/transactions").json()
    assert len(default["lines"]) == 4
    assert [line["balance"] for line in default["lines"]] == [
        1000000,
        900000,
        1300000,
        1400000,
    ]
    assert default["closing_balance"] == 1400000

    filtered = client.get(
        f"/api/ledger/accounts/{cash}/transactions",
        params={"include_voided": "false"},
    ).json()
    # The voided rent entry and its reversal are hidden together.
    assert len(filtered["lines"]) == 2
    assert all(line["is_voided"] is False for line in filtered["lines"])
    assert [line["balance"] for line in filtered["lines"]] == [1000000, 1400000]
    assert filtered["closing_balance"] == 1400000


def test_search_transactions_by_description(client):
    _seed_basic(client)
    with SessionLocal() as db:
        rows = ledger_service.search_transactions(db, query="rent")
    assert len(rows) == 2
    assert all(row["entry_description"] == "Pay rent" for row in rows)
    assert {row["account_number"] for row in rows} == {"5100", "1000"}
    assert sum(row["debit"] for row in rows) == 100000
    assert sum(row["credit"] for row in rows) == 100000


def test_search_transactions_case_insensitive(client):
    _seed_basic(client)
    with SessionLocal() as db:
        rows = ledger_service.search_transactions(db, query="RENT")
    assert len(rows) == 2


def test_search_transactions_account_and_date_filters(client):
    _seed_basic(client)
    cash = _account_id(client, "1000")
    with SessionLocal() as db:
        rows = ledger_service.search_transactions(db, account_id=cash)
    assert len(rows) == 3
    assert all(row["account_number"] == "1000" for row in rows)

    with SessionLocal() as db:
        rows = ledger_service.search_transactions(db, date_from=date(2026, 2, 1))
    assert len(rows) == 2
    assert all(row["entry_description"] == "Sale" for row in rows)

    with SessionLocal() as db:
        rows = ledger_service.search_transactions(
            db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31)
        )
    assert {row["entry_description"] for row in rows} == {"Owner investment", "Pay rent"}


def test_search_transactions_limit_and_order(client):
    _seed_basic(client)
    with SessionLocal() as db:
        rows = ledger_service.search_transactions(db, limit=1)
    assert len(rows) == 1
    assert rows[0]["entry_description"] == "Sale"  # newest first

    with SessionLocal() as db:
        rows = ledger_service.search_transactions(db)
    assert len(rows) == 6
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates, reverse=True)
