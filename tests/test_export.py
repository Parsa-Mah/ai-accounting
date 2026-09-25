"""Tests for the export API (CSV and PDF report downloads)."""

import csv
import io


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


def _create_customer(client, name="Acme Corp") -> int:
    response = client.post("/api/customers", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_vendor(client, name="Widget Co") -> int:
    response = client.post("/api/vendors", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_invoice(client, customer_id=None, tax_rate=0.0, lines=None, **overrides):
    if customer_id is None:
        customer_id = _create_customer(client)
    if lines is None:
        lines = [{"description": "Consulting", "quantity": 2, "unit_price_cents": 10000}]
    payload = {
        "customer_id": customer_id,
        "date": "2026-03-01",
        "tax_rate": tax_rate,
        "lines": lines,
    }
    payload.update(overrides)
    response = client.post("/api/invoices", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_bill(client, vendor_id=None, tax_rate=0.0, lines=None, **overrides):
    if vendor_id is None:
        vendor_id = _create_vendor(client)
    if lines is None:
        lines = [
            {
                "description": "Rent",
                "quantity": 1,
                "unit_price_cents": 20000,
                "expense_account_id": _account_id(client, "5100"),
            }
        ]
    payload = {
        "vendor_id": vendor_id,
        "date": "2026-03-05",
        "tax_rate": tax_rate,
        "lines": lines,
    }
    payload.update(overrides)
    response = client.post("/api/bills", json=payload)
    assert response.status_code == 201
    return response.json()


def _seed(client):
    """Three journal entries, one invoice (10% tax), one bill (no tax).

    Revenue = 4000.00 (sale) + 200.00 (invoice) = 4200.00.
    Expenses = 1000.00 (rent) + 200.00 (bill) = 1200.00.
    Cash = 10000.00 + 4000.00 - 1000.00 = 13000.00.
    """
    _post(client, "2026-01-05", "Owner investment", [("1000", 1000000, 0), ("3000", 0, 1000000)])
    _post(client, "2026-02-10", "Sale", [("1000", 400000, 0), ("4000", 0, 400000)])
    _post(client, "2026-03-05", "Pay rent", [("5100", 100000, 0), ("1000", 0, 100000)])
    invoice = _create_invoice(client, tax_rate=10.0)
    bill = _create_bill(client)
    return invoice, bill


def _csv_rows(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(response.text)))


def _assert_pdf(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:4] == b"%PDF"
    return response


# --- general ledger ---


def test_general_ledger_csv(client):
    _seed(client)
    cash = _account_id(client, "1000")
    rows = _csv_rows(client.get("/api/export/general-ledger", params={"account_id": cash}))
    assert rows[0] == [
        "date",
        "entry",
        "description",
        "line_description",
        "debit",
        "credit",
        "balance",
        "cleared",
    ]
    assert rows[1][2] == "Opening balance"
    assert rows[-1][2] == "Closing balance"
    assert rows[-1][6] == "13000.00"


def test_general_ledger_requires_account(client):
    _seed(client)
    response = client.get("/api/export/general-ledger")
    assert response.status_code == 422


def test_general_ledger_pdf(client):
    _seed(client)
    cash = _account_id(client, "1000")
    _assert_pdf(
        client.get(
            "/api/export/general-ledger", params={"account_id": cash, "format": "pdf"}
        )
    )


# --- trial balance ---


def test_trial_balance_csv(client):
    _seed(client)
    rows = _csv_rows(client.get("/api/export/trial-balance"))
    assert rows[0] == ["number", "name", "type", "debit", "credit"]
    by_number = {r[0]: r for r in rows[1:] if r[0]}
    assert by_number["1000"][3] == "13000.00"
    total = [r for r in rows if r[2] == "Total"][0]
    assert total[3] == total[4] == "14420.00"


def test_trial_balance_pdf(client):
    _seed(client)
    _assert_pdf(client.get("/api/export/trial-balance", params={"format": "pdf"}))


# --- income statement ---


def test_income_statement_csv(client):
    _seed(client)
    rows = _csv_rows(client.get("/api/export/income-statement"))
    assert rows[0] == ["section", "number", "name", "amount"]
    by_name = {r[2]: r for r in rows[1:]}
    assert by_name["Total revenue"][3] == "4200.00"
    assert by_name["Total expenses"][3] == "1200.00"
    assert by_name["Net income"][3] == "3000.00"


def test_income_statement_csv_date_range(client):
    _seed(client)
    rows = _csv_rows(
        client.get(
            "/api/export/income-statement",
            params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
        )
    )
    by_name = {r[2]: r for r in rows[1:]}
    assert by_name["Total revenue"][3] == "4000.00"
    assert by_name["Total expenses"][3] == "0.00"
    assert by_name["Net income"][3] == "4000.00"


def test_income_statement_pdf(client):
    _seed(client)
    _assert_pdf(client.get("/api/export/income-statement", params={"format": "pdf"}))


# --- balance sheet ---


def test_balance_sheet_csv(client):
    _seed(client)
    rows = _csv_rows(client.get("/api/export/balance-sheet"))
    assert rows[0] == ["section", "number", "name", "amount"]
    by_name = {r[2]: r for r in rows[1:]}
    assert by_name["Total assets"][3] == "13220.00"
    assert by_name["Total liabilities"][3] == "220.00"
    assert by_name["Total equity"][3] == "13000.00"
    assert by_name["Total assets"][3] == "13220.00"


def test_balance_sheet_pdf(client):
    _seed(client)
    _assert_pdf(client.get("/api/export/balance-sheet", params={"format": "pdf"}))


# --- journal ---


def test_journal_csv(client):
    _seed(client)
    rows = _csv_rows(client.get("/api/export/journal"))
    assert rows[0] == [
        "entry",
        "date",
        "description",
        "account_number",
        "account_name",
        "debit",
        "credit",
    ]
    # 3 manual entries (2 lines each) + invoice (3 lines) + bill (2 lines) = 11
    assert len(rows) - 1 == 11
    by_account = {r[3] for r in rows[1:]}
    assert "1000" in by_account and "4000" in by_account


def test_journal_csv_date_range(client):
    _seed(client)
    rows = _csv_rows(
        client.get(
            "/api/export/journal",
            params={"date_from": "2026-03-01", "date_to": "2026-03-31"},
        )
    )
    dates = {r[1] for r in rows[1:]}
    assert dates <= {"2026-03-01", "2026-03-05"}


def test_journal_pdf(client):
    _seed(client)
    _assert_pdf(client.get("/api/export/journal", params={"format": "pdf"}))


# --- invoices ---


def test_invoices_csv(client):
    _seed(client)
    rows = _csv_rows(client.get("/api/export/invoices"))
    assert rows[0] == [
        "id",
        "date",
        "due_date",
        "customer",
        "subtotal",
        "tax",
        "total",
        "paid",
        "balance",
        "status",
    ]
    assert len(rows) - 1 == 1
    row = rows[1]
    assert row[3] == "Acme Corp"
    assert row[4] == "200.00"  # subtotal
    assert row[5] == "20.00"  # tax
    assert row[6] == "220.00"  # total
    assert row[8] == "220.00"  # balance
    assert row[9] == "open"


def test_invoices_pdf(client):
    _seed(client)
    _assert_pdf(client.get("/api/export/invoices", params={"format": "pdf"}))


# --- bills ---


def test_bills_csv(client):
    _seed(client)
    rows = _csv_rows(client.get("/api/export/bills"))
    assert rows[0] == [
        "id",
        "date",
        "due_date",
        "vendor",
        "subtotal",
        "tax",
        "total",
        "paid",
        "balance",
        "status",
    ]
    assert len(rows) - 1 == 1
    row = rows[1]
    assert row[3] == "Widget Co"
    assert row[4] == "200.00"  # subtotal
    assert row[5] == "0.00"  # tax
    assert row[6] == "200.00"  # total
    assert row[9] == "open"


def test_bills_pdf(client):
    _seed(client)
    _assert_pdf(client.get("/api/export/bills", params={"format": "pdf"}))


# --- cross-cutting ---


def test_export_filename_header(client):
    _seed(client)
    response = client.get("/api/export/trial-balance", params={"as_of": "2026-03-31"})
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="trial-balance-2026-03-31.csv"'
    )


def test_export_invalid_format(client):
    _seed(client)
    response = client.get("/api/export/trial-balance", params={"format": "xlsx"})
    assert response.status_code == 422


def test_export_requires_auth(app_client):
    response = app_client.get("/api/export/trial-balance")
    assert response.status_code == 401
