"""Tests for the financial statements API (income statement, balance sheet)."""


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


def _seed_statements(client):
    """Capital 1_000_000, loan 200_000, sale 400_000, rent 100_000."""
    capital = _post(
        client, "2026-01-05", "Owner investment", [("1000", 1000000, 0), ("3000", 0, 1000000)]
    )
    loan = _post(
        client, "2026-01-20", "Take loan", [("1000", 200000, 0), ("2500", 0, 200000)]
    )
    sale = _post(
        client, "2026-02-10", "Sale", [("1000", 400000, 0), ("4000", 0, 400000)]
    )
    rent = _post(
        client, "2026-03-05", "Pay rent", [("5100", 100000, 0), ("1000", 0, 100000)]
    )
    return capital, loan, sale, rent


def test_income_statement_totals(client):
    _seed_statements(client)
    response = client.get("/api/reports/income-statement")
    assert response.status_code == 200
    body = response.json()
    assert body["total_revenue"] == 400000
    assert body["total_expenses"] == 100000
    assert body["net_income"] == 300000
    assert [row["number"] for row in body["revenue"]] == ["4000"]
    assert body["revenue"][0]["amount"] == 400000
    assert [row["number"] for row in body["expenses"]] == ["5100"]
    assert body["expenses"][0]["amount"] == 100000


def test_income_statement_date_range(client):
    _seed_statements(client)
    response = client.get(
        "/api/reports/income-statement",
        params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_revenue"] == 400000
    assert body["total_expenses"] == 0
    assert body["net_income"] == 400000
    assert body["expenses"] == []


def test_balance_sheet_identity(client):
    _seed_statements(client)
    response = client.get("/api/reports/balance-sheet")
    assert response.status_code == 200
    body = response.json()
    assert body["balanced"] is True
    assert body["total_assets"] == body["total_liabilities"] + body["total_equity"]
    assert body["total_assets"] == 1500000
    assert body["total_liabilities"] == 200000
    assert body["total_equity"] == 1300000
    assert [row["number"] for row in body["assets"]] == ["1000"]
    assert body["assets"][0]["amount"] == 1500000
    assert [row["number"] for row in body["liabilities"]] == ["2500"]
    assert body["liabilities"][0]["amount"] == 200000
    equity_by_name = {row["name"]: row for row in body["equity"]}
    assert equity_by_name["Owner's Capital"]["amount"] == 1000000
    assert equity_by_name["Net Income (unclosed)"]["amount"] == 300000


def test_balance_sheet_as_of(client):
    _seed_statements(client)
    response = client.get("/api/reports/balance-sheet", params={"as_of": "2026-01-31"})
    assert response.status_code == 200
    body = response.json()
    assert body["balanced"] is True
    assert body["total_assets"] == 1200000
    assert body["total_liabilities"] == 200000
    assert body["total_equity"] == 1000000
    assert all(row["name"] != "Net Income (unclosed)" for row in body["equity"])


def test_voided_entry_offsets_statements(client):
    _, _, sale, _ = _seed_statements(client)
    response = client.post(f"/api/journal/{sale['id']}/void")
    assert response.status_code == 201

    income = client.get("/api/reports/income-statement").json()
    assert income["total_revenue"] == 0
    assert income["total_expenses"] == 100000
    assert income["net_income"] == -100000

    sheet = client.get("/api/reports/balance-sheet").json()
    assert sheet["balanced"] is True
    assert sheet["total_assets"] == 1100000
    assert sheet["total_liabilities"] == 200000
    assert sheet["total_equity"] == 900000
    assert sheet["total_assets"] == sheet["total_liabilities"] + sheet["total_equity"]
