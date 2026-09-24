"""Tests for the bills API (AP posting, payments, voids)."""


def _account_id(client, number: str) -> int:
    accounts = {a["number"]: a for a in client.get("/api/accounts").json()}
    return accounts[number]["id"]


def _create_vendor(client, name="Acme Suppliers") -> int:
    response = client.post("/api/vendors", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


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
        "date": "2026-03-01",
        "tax_rate": tax_rate,
        "lines": lines,
    }
    payload.update(overrides)
    response = client.post("/api/bills", json=payload)
    assert response.status_code == 201
    return response.json()


def _entry_by_number(client, entry_id):
    entry = client.get(f"/api/journal/{entry_id}").json()
    return {line["account_number"]: line for line in entry["lines"]}, entry


def test_create_bill_posts_to_ledger(client):
    bill = _create_bill(client, tax_rate=10.0)
    assert bill["subtotal_cents"] == 20000
    assert bill["tax_cents"] == 2000
    assert bill["total_cents"] == 22000
    assert bill["status"] == "open"
    assert bill["paid_cents"] == 0

    lines, entry = _entry_by_number(client, bill["entry_id"])
    assert entry["source_type"] == "bill"
    assert entry["source_id"] == bill["id"]
    assert entry["is_voided"] is False
    assert lines["5100"]["debit"] == 20000 and lines["5100"]["credit"] == 0
    assert lines["2210"]["debit"] == 2000 and lines["2210"]["credit"] == 0
    assert lines["2000"]["debit"] == 0 and lines["2000"]["credit"] == 22000


def test_create_bill_zero_tax_omits_tax_line(client):
    bill = _create_bill(client, tax_rate=0.0)
    lines, _ = _entry_by_number(client, bill["entry_id"])
    assert set(lines) == {"5100", "2000"}
    assert bill["total_cents"] == bill["subtotal_cents"]


def test_create_bill_tax_rounds_half_up(client):
    # 1005 cents @ 10% = 100.5 -> 101 (half-up)
    bill = _create_bill(
        client,
        tax_rate=10.0,
        lines=[
            {
                "description": "X",
                "quantity": 1,
                "unit_price_cents": 1005,
                "expense_account_id": _account_id(client, "5100"),
            }
        ],
    )
    assert bill["tax_cents"] == 101
    assert bill["total_cents"] == 1106


def test_create_bill_multiple_expense_lines(client):
    rent_id = _account_id(client, "5100")
    utilities_id = _account_id(client, "5300")
    bill = _create_bill(
        client,
        lines=[
            {
                "description": "Rent",
                "quantity": 1,
                "unit_price_cents": 10000,
                "expense_account_id": rent_id,
            },
            {
                "description": "Utilities",
                "quantity": 2,
                "unit_price_cents": 5000,
                "expense_account_id": utilities_id,
            },
        ],
    )
    assert bill["subtotal_cents"] == 20000
    lines, _ = _entry_by_number(client, bill["entry_id"])
    assert lines["5100"]["debit"] == 10000
    assert lines["5300"]["debit"] == 10000
    assert lines["2000"]["credit"] == 20000


def test_create_bill_unknown_vendor(client):
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": 9999,
            "date": "2026-03-01",
            "lines": [
                {
                    "description": "X",
                    "unit_price_cents": 100,
                    "expense_account_id": _account_id(client, "5100"),
                }
            ],
        },
    )
    assert response.status_code == 404


def test_create_bill_line_needs_description_or_item(client):
    vendor_id = _create_vendor(client)
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": "2026-03-01",
            "lines": [
                {"quantity": 1, "unit_price_cents": 100, "expense_account_id": 1}
            ],
        },
    )
    assert response.status_code == 422


def test_create_bill_line_requires_expense_account(client):
    vendor_id = _create_vendor(client)
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": "2026-03-01",
            "lines": [{"description": "X", "quantity": 1, "unit_price_cents": 100}],
        },
    )
    assert response.status_code == 422


def test_create_bill_with_item_snapshots_name(client):
    vendor_id = _create_vendor(client)
    item = client.post(
        "/api/items", json={"name": "Office Supplies", "unit_price_cents": 15000}
    ).json()
    bill = _create_bill(
        client,
        vendor_id=vendor_id,
        lines=[
            {
                "item_id": item["id"],
                "quantity": 3,
                "unit_price_cents": 15000,
                "expense_account_id": _account_id(client, "5400"),
            }
        ],
    )
    line = bill["lines"][0]
    assert line["item_id"] == item["id"]
    assert line["description"] == "Office Supplies"
    assert line["amount_cents"] == 45000


def test_create_bill_unknown_item(client):
    vendor_id = _create_vendor(client)
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": "2026-03-01",
            "lines": [
                {
                    "item_id": 9999,
                    "quantity": 1,
                    "unit_price_cents": 100,
                    "expense_account_id": _account_id(client, "5100"),
                }
            ],
        },
    )
    assert response.status_code == 404


def test_create_bill_unknown_expense_account(client):
    vendor_id = _create_vendor(client)
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": "2026-03-01",
            "lines": [
                {
                    "description": "X",
                    "quantity": 1,
                    "unit_price_cents": 100,
                    "expense_account_id": 9999,
                }
            ],
        },
    )
    assert response.status_code == 404


def test_create_bill_non_expense_account_rejected(client):
    vendor_id = _create_vendor(client)
    cash_id = _account_id(client, "1000")
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": "2026-03-01",
            "lines": [
                {
                    "description": "X",
                    "quantity": 1,
                    "unit_price_cents": 100,
                    "expense_account_id": cash_id,
                }
            ],
        },
    )
    assert response.status_code == 422


def test_create_bill_inactive_expense_account_rejected(client):
    vendor_id = _create_vendor(client)
    expense_id = _account_id(client, "5100")
    client.post(f"/api/accounts/{expense_id}/deactivate")
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": "2026-03-01",
            "lines": [
                {
                    "description": "X",
                    "quantity": 1,
                    "unit_price_cents": 100,
                    "expense_account_id": expense_id,
                }
            ],
        },
    )
    assert response.status_code == 409


def test_create_bill_zero_total_rejected(client):
    vendor_id = _create_vendor(client)
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": "2026-03-01",
            "lines": [
                {
                    "description": "Free",
                    "quantity": 1,
                    "unit_price_cents": 0,
                    "expense_account_id": _account_id(client, "5100"),
                }
            ],
        },
    )
    assert response.status_code == 422


def test_pay_bill_posts_ap_and_cash(client):
    bill = _create_bill(client)
    response = client.post(
        f"/api/bills/{bill['id']}/pay",
        json={"amount_cents": 10000, "note": "half now"},
    )
    assert response.status_code == 201
    payment = response.json()
    assert payment["amount_cents"] == 10000

    lines, entry = _entry_by_number(client, payment["entry_id"])
    assert entry["source_type"] == "bill_payment"
    assert entry["source_id"] == bill["id"]
    assert lines["2000"]["debit"] == 10000 and lines["2000"]["credit"] == 0
    assert lines["1000"]["debit"] == 0 and lines["1000"]["credit"] == 10000

    refreshed = client.get(f"/api/bills/{bill['id']}").json()
    assert refreshed["paid_cents"] == 10000
    assert refreshed["status"] == "partially_paid"
    assert len(refreshed["payments"]) == 1


def test_pay_bill_full_marks_paid(client):
    bill = _create_bill(client)
    client.post(
        f"/api/bills/{bill['id']}/pay",
        json={"amount_cents": bill["total_cents"]},
    )
    refreshed = client.get(f"/api/bills/{bill['id']}").json()
    assert refreshed["status"] == "paid"


def test_pay_bill_overpay_rejected(client):
    bill = _create_bill(client)
    response = client.post(
        f"/api/bills/{bill['id']}/pay",
        json={"amount_cents": bill["total_cents"] + 1},
    )
    assert response.status_code == 422


def test_pay_voided_bill_rejected(client):
    bill = _create_bill(client)
    client.post(f"/api/bills/{bill['id']}/void")
    response = client.post(
        f"/api/bills/{bill['id']}/pay", json={"amount_cents": 100}
    )
    assert response.status_code == 409


def test_void_bill_reverses_posting(client):
    ap_id = _account_id(client, "2000")
    bill = _create_bill(client, tax_rate=10.0)
    response = client.post(f"/api/bills/{bill['id']}/void")
    assert response.status_code == 200
    body = response.json()
    assert body["is_voided"] is True
    assert body["status"] == "void"
    assert body["voided_by_entry_id"] is not None

    lines, reversal = _entry_by_number(client, body["voided_by_entry_id"])
    assert reversal["description"].startswith("VOID:")
    assert reversal["source_type"] == "void"
    assert lines["5100"]["credit"] == 20000
    assert lines["2210"]["credit"] == 2000
    assert lines["2000"]["debit"] == 22000

    ledger = client.get(f"/api/ledger/accounts/{ap_id}/transactions").json()
    assert ledger["closing_balance"] == 0


def test_void_bill_twice_rejected(client):
    bill = _create_bill(client)
    client.post(f"/api/bills/{bill['id']}/void")
    response = client.post(f"/api/bills/{bill['id']}/void")
    assert response.status_code == 409


def test_void_paid_bill_rejected(client):
    bill = _create_bill(client)
    client.post(f"/api/bills/{bill['id']}/pay", json={"amount_cents": 1000})
    response = client.post(f"/api/bills/{bill['id']}/void")
    assert response.status_code == 409


def test_get_bill_not_found(client):
    assert client.get("/api/bills/9999").status_code == 404


def test_list_bills_filters_vendor_and_voided(client):
    v1 = _create_vendor(client, "Acme Suppliers")
    v2 = _create_vendor(client, "Globex Parts")
    bill1 = _create_bill(client, vendor_id=v1)
    bill2 = _create_bill(client, vendor_id=v2)
    client.post(f"/api/bills/{bill1['id']}/void")

    assert len(client.get("/api/bills").json()) == 2
    assert len(client.get("/api/bills", params={"vendor_id": v2}).json()) == 1
    active = client.get("/api/bills", params={"include_voided": "false"}).json()
    assert [b["id"] for b in active] == [bill2["id"]]


def test_trial_balance_balanced_after_bill_activity(client):
    bill = _create_bill(client, tax_rate=10.0)
    client.post(
        f"/api/bills/{bill['id']}/pay", json={"amount_cents": 10000}
    )
    body = client.get("/api/ledger/trial-balance").json()
    assert body["balanced"] is True


def test_balance_sheet_identity_after_bill_activity(client):
    bill = _create_bill(client, tax_rate=10.0)
    client.post(
        f"/api/bills/{bill['id']}/pay", json={"amount_cents": 10000}
    )
    body = client.get("/api/reports/balance-sheet").json()
    assert body["balanced"] is True
    assert body["total_assets"] == body["total_liabilities"] + body["total_equity"]
