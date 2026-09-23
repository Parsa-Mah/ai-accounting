"""Tests for the invoices API (AR posting, payments, voids)."""


def _account_id(client, number: str) -> int:
    accounts = {a["number"]: a for a in client.get("/api/accounts").json()}
    return accounts[number]["id"]


def _create_customer(client, name="Acme Corp") -> int:
    response = client.post("/api/customers", json={"name": name})
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


def _entry_by_number(client, entry_id):
    entry = client.get(f"/api/journal/{entry_id}").json()
    return {line["account_number"]: line for line in entry["lines"]}, entry


def test_create_invoice_posts_to_ledger(client):
    invoice = _create_invoice(client, tax_rate=10.0)
    assert invoice["subtotal_cents"] == 20000
    assert invoice["tax_cents"] == 2000
    assert invoice["total_cents"] == 22000
    assert invoice["status"] == "open"
    assert invoice["paid_cents"] == 0

    lines, entry = _entry_by_number(client, invoice["entry_id"])
    assert entry["source_type"] == "invoice"
    assert entry["source_id"] == invoice["id"]
    assert entry["is_voided"] is False
    assert lines["1100"]["debit"] == 22000 and lines["1100"]["credit"] == 0
    assert lines["4000"]["debit"] == 0 and lines["4000"]["credit"] == 20000
    assert lines["2200"]["debit"] == 0 and lines["2200"]["credit"] == 2000


def test_create_invoice_zero_tax_omits_tax_line(client):
    invoice = _create_invoice(client, tax_rate=0.0)
    lines, _ = _entry_by_number(client, invoice["entry_id"])
    assert set(lines) == {"1100", "4000"}
    assert invoice["total_cents"] == invoice["subtotal_cents"]


def test_create_invoice_tax_rounds_half_up(client):
    # 1005 cents @ 10% = 100.5 -> 101 (half-up)
    invoice = _create_invoice(
        client,
        tax_rate=10.0,
        lines=[{"description": "X", "quantity": 1, "unit_price_cents": 1005}],
    )
    assert invoice["tax_cents"] == 101
    assert invoice["total_cents"] == 1106


def test_create_invoice_unknown_customer(client):
    response = client.post(
        "/api/invoices",
        json={
            "customer_id": 9999,
            "date": "2026-03-01",
            "lines": [{"description": "X", "unit_price_cents": 100}],
        },
    )
    assert response.status_code == 404


def test_create_invoice_line_needs_description_or_item(client):
    customer_id = _create_customer(client)
    response = client.post(
        "/api/invoices",
        json={
            "customer_id": customer_id,
            "date": "2026-03-01",
            "lines": [{"quantity": 1, "unit_price_cents": 100}],
        },
    )
    assert response.status_code == 422


def test_create_invoice_with_item_snapshots_name(client):
    customer_id = _create_customer(client)
    item = client.post(
        "/api/items", json={"name": "Consulting", "unit_price_cents": 15000}
    ).json()
    invoice = _create_invoice(
        client,
        customer_id=customer_id,
        lines=[{"item_id": item["id"], "quantity": 3, "unit_price_cents": 15000}],
    )
    line = invoice["lines"][0]
    assert line["item_id"] == item["id"]
    assert line["description"] == "Consulting"
    assert line["amount_cents"] == 45000


def test_create_invoice_unknown_item(client):
    customer_id = _create_customer(client)
    response = client.post(
        "/api/invoices",
        json={
            "customer_id": customer_id,
            "date": "2026-03-01",
            "lines": [{"item_id": 9999, "quantity": 1, "unit_price_cents": 100}],
        },
    )
    assert response.status_code == 404


def test_create_invoice_zero_total_rejected(client):
    customer_id = _create_customer(client)
    response = client.post(
        "/api/invoices",
        json={
            "customer_id": customer_id,
            "date": "2026-03-01",
            "lines": [{"description": "Free", "quantity": 1, "unit_price_cents": 0}],
        },
    )
    assert response.status_code == 422


def test_pay_invoice_posts_cash_and_ar(client):
    invoice = _create_invoice(client)
    response = client.post(
        f"/api/invoices/{invoice['id']}/pay",
        json={"amount_cents": 10000, "note": "half now"},
    )
    assert response.status_code == 201
    payment = response.json()
    assert payment["amount_cents"] == 10000

    lines, entry = _entry_by_number(client, payment["entry_id"])
    assert entry["source_type"] == "invoice_payment"
    assert entry["source_id"] == invoice["id"]
    assert lines["1000"]["debit"] == 10000 and lines["1000"]["credit"] == 0
    assert lines["1100"]["debit"] == 0 and lines["1100"]["credit"] == 10000

    refreshed = client.get(f"/api/invoices/{invoice['id']}").json()
    assert refreshed["paid_cents"] == 10000
    assert refreshed["status"] == "partially_paid"
    assert len(refreshed["payments"]) == 1


def test_pay_invoice_full_marks_paid(client):
    invoice = _create_invoice(client)
    client.post(
        f"/api/invoices/{invoice['id']}/pay",
        json={"amount_cents": invoice["total_cents"]},
    )
    refreshed = client.get(f"/api/invoices/{invoice['id']}").json()
    assert refreshed["status"] == "paid"


def test_pay_invoice_overpay_rejected(client):
    invoice = _create_invoice(client)
    response = client.post(
        f"/api/invoices/{invoice['id']}/pay",
        json={"amount_cents": invoice["total_cents"] + 1},
    )
    assert response.status_code == 422


def test_pay_voided_invoice_rejected(client):
    invoice = _create_invoice(client)
    client.post(f"/api/invoices/{invoice['id']}/void")
    response = client.post(
        f"/api/invoices/{invoice['id']}/pay", json={"amount_cents": 100}
    )
    assert response.status_code == 409


def test_void_invoice_reverses_posting(client):
    ar_id = _account_id(client, "1100")
    invoice = _create_invoice(client, tax_rate=10.0)
    response = client.post(f"/api/invoices/{invoice['id']}/void")
    assert response.status_code == 200
    body = response.json()
    assert body["is_voided"] is True
    assert body["status"] == "void"
    assert body["voided_by_entry_id"] is not None

    lines, reversal = _entry_by_number(client, body["voided_by_entry_id"])
    assert reversal["description"].startswith("VOID:")
    assert reversal["source_type"] == "void"
    assert lines["1100"]["credit"] == 22000
    assert lines["4000"]["debit"] == 20000
    assert lines["2200"]["debit"] == 2000

    ledger = client.get(f"/api/ledger/accounts/{ar_id}/transactions").json()
    assert ledger["closing_balance"] == 0


def test_void_invoice_twice_rejected(client):
    invoice = _create_invoice(client)
    client.post(f"/api/invoices/{invoice['id']}/void")
    response = client.post(f"/api/invoices/{invoice['id']}/void")
    assert response.status_code == 409


def test_void_paid_invoice_rejected(client):
    invoice = _create_invoice(client)
    client.post(f"/api/invoices/{invoice['id']}/pay", json={"amount_cents": 1000})
    response = client.post(f"/api/invoices/{invoice['id']}/void")
    assert response.status_code == 409


def test_get_invoice_not_found(client):
    assert client.get("/api/invoices/9999").status_code == 404


def test_list_invoices_filters_customer_and_voided(client):
    c1 = _create_customer(client, "Acme Corp")
    c2 = _create_customer(client, "Globex")
    inv1 = _create_invoice(client, customer_id=c1)
    inv2 = _create_invoice(client, customer_id=c2)
    client.post(f"/api/invoices/{inv1['id']}/void")

    assert len(client.get("/api/invoices").json()) == 2
    assert len(client.get("/api/invoices", params={"customer_id": c2}).json()) == 1
    active = client.get("/api/invoices", params={"include_voided": "false"}).json()
    assert [i["id"] for i in active] == [inv2["id"]]


def test_trial_balance_balanced_after_invoice_activity(client):
    invoice = _create_invoice(client, tax_rate=10.0)
    client.post(
        f"/api/invoices/{invoice['id']}/pay", json={"amount_cents": 10000}
    )
    body = client.get("/api/ledger/trial-balance").json()
    assert body["balanced"] is True


def test_balance_sheet_identity_after_invoice_activity(client):
    invoice = _create_invoice(client, tax_rate=10.0)
    client.post(
        f"/api/invoices/{invoice['id']}/pay", json={"amount_cents": 10000}
    )
    body = client.get("/api/reports/balance-sheet").json()
    assert body["balanced"] is True
    assert body["total_assets"] == body["total_liabilities"] + body["total_equity"]
