"""Tests for the budgets API (CRUD + actual-vs-budget report)."""


def _account_id(client, number: str) -> int:
    accounts = {a["number"]: a for a in client.get("/api/accounts").json()}
    return accounts[number]["id"]


def _create_budget(client, account_id=None, start="2026-03-01", end="2026-03-31",
                   budget_cents=25000, **overrides):
    if account_id is None:
        account_id = _account_id(client, "5100")
    payload = {
        "account_id": account_id,
        "budget_start": start,
        "budget_end": end,
        "budget_cents": budget_cents,
    }
    payload.update(overrides)
    response = client.post("/api/budgets", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_vendor(client, name="Acme Suppliers") -> int:
    response = client.post("/api/vendors", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_bill(client, date="2026-03-15", amount_cents=20000,
                 expense_number="5100"):
    vendor_id = _create_vendor(client)
    response = client.post(
        "/api/bills",
        json={
            "vendor_id": vendor_id,
            "date": date,
            "tax_rate": 0.0,
            "lines": [
                {
                    "description": "Rent",
                    "quantity": 1,
                    "unit_price_cents": amount_cents,
                    "expense_account_id": _account_id(client, expense_number),
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_invoice(client, date="2026-03-15", amount_cents=20000):
    customer = client.post("/api/customers", json={"name": "Acme Corp"}).json()
    response = client.post(
        "/api/invoices",
        json={
            "customer_id": customer["id"],
            "date": date,
            "tax_rate": 0.0,
            "lines": [
                {
                    "description": "Consulting",
                    "quantity": 1,
                    "unit_price_cents": amount_cents,
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _report(client, start="2026-03-01", end="2026-03-31", account_id=None):
    params = {"start": start, "end": end}
    if account_id is not None:
        params["account_id"] = account_id
    response = client.get("/api/budgets/report", params=params)
    assert response.status_code == 200
    return response.json()


def test_create_budget(client):
    rent_id = _account_id(client, "5100")
    budget = _create_budget(client, account_id=rent_id, budget_cents=30000,
                            note="monthly rent")
    assert budget["account_id"] == rent_id
    assert budget["account_number"] == "5100"
    assert budget["account_name"] == "Rent Expense"
    assert budget["account_type"] == "expense"
    assert budget["budget_start"] == "2026-03-01"
    assert budget["budget_end"] == "2026-03-31"
    assert budget["budget_cents"] == 30000
    assert budget["note"] == "monthly rent"


def test_create_budget_unknown_account(client):
    response = client.post(
        "/api/budgets",
        json={
            "account_id": 9999,
            "budget_start": "2026-03-01",
            "budget_end": "2026-03-31",
            "budget_cents": 100,
        },
    )
    assert response.status_code == 404


def test_create_budget_start_after_end(client):
    response = client.post(
        "/api/budgets",
        json={
            "account_id": _account_id(client, "5100"),
            "budget_start": "2026-03-31",
            "budget_end": "2026-03-01",
            "budget_cents": 100,
        },
    )
    assert response.status_code == 422


def test_create_budget_negative_cents(client):
    response = client.post(
        "/api/budgets",
        json={
            "account_id": _account_id(client, "5100"),
            "budget_start": "2026-03-01",
            "budget_end": "2026-03-31",
            "budget_cents": -1,
        },
    )
    assert response.status_code == 422


def test_get_budget(client):
    budget = _create_budget(client)
    response = client.get(f"/api/budgets/{budget['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == budget["id"]


def test_get_budget_not_found(client):
    assert client.get("/api/budgets/9999").status_code == 404


def test_list_budgets_filter_account(client):
    rent_id = _account_id(client, "5100")
    utilities_id = _account_id(client, "5300")
    _create_budget(client, account_id=rent_id)
    _create_budget(client, account_id=utilities_id)

    assert len(client.get("/api/budgets").json()) == 2
    filtered = client.get("/api/budgets", params={"account_id": rent_id}).json()
    assert len(filtered) == 1
    assert filtered[0]["account_id"] == rent_id


def test_update_budget_cents(client):
    budget = _create_budget(client, budget_cents=10000)
    response = client.patch(
        f"/api/budgets/{budget['id']}", json={"budget_cents": 15000}
    )
    assert response.status_code == 200
    assert response.json()["budget_cents"] == 15000


def test_update_budget_range_validation(client):
    budget = _create_budget(client, start="2026-03-01", end="2026-03-31")
    response = client.patch(
        f"/api/budgets/{budget['id']}", json={"budget_start": "2026-04-01"}
    )
    assert response.status_code == 422


def test_delete_budget(client):
    budget = _create_budget(client)
    response = client.delete(f"/api/budgets/{budget['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/budgets/{budget['id']}").status_code == 404


def test_budget_report_expense_actual_and_variance(client):
    _create_bill(client, date="2026-03-15", amount_cents=20000)
    rent_id = _account_id(client, "5100")
    _create_budget(client, account_id=rent_id, budget_cents=25000)

    body = _report(client)
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["account_number"] == "5100"
    assert row["budget_cents"] == 25000
    assert row["actual_cents"] == 20000
    assert row["variance_cents"] == 5000
    assert row["within_budget"] is True
    assert body["totals"]["budget_cents"] == 25000
    assert body["totals"]["actual_cents"] == 20000
    assert body["totals"]["variance_cents"] == 5000


def test_budget_report_no_activity(client):
    rent_id = _account_id(client, "5100")
    _create_budget(client, account_id=rent_id, budget_cents=25000)

    body = _report(client)
    row = body["rows"][0]
    assert row["actual_cents"] == 0
    assert row["variance_cents"] == 25000
    assert row["within_budget"] is True


def test_budget_report_revenue_direction(client):
    _create_invoice(client, date="2026-03-15", amount_cents=20000)
    revenue_id = _account_id(client, "4000")
    _create_budget(client, account_id=revenue_id, budget_cents=15000)

    body = _report(client)
    row = body["rows"][0]
    assert row["account_number"] == "4000"
    assert row["account_type"] == "revenue"
    assert row["actual_cents"] == 20000
    assert row["variance_cents"] == -5000
    assert row["within_budget"] is False


def test_budget_report_only_fully_contained(client):
    rent_id = _account_id(client, "5100")
    utilities_id = _account_id(client, "5300")
    supplies_id = _account_id(client, "5400")
    contained = _create_budget(client, account_id=rent_id,
                               start="2026-03-01", end="2026-03-31")
    # Extends past the report end.
    _create_budget(client, account_id=utilities_id,
                   start="2026-03-15", end="2026-04-15")
    # Starts before the report start.
    _create_budget(client, account_id=supplies_id,
                   start="2026-02-15", end="2026-03-10")

    body = _report(client)
    assert [r["budget_id"] for r in body["rows"]] == [contained["id"]]


def test_budget_report_totals_sum_rows(client):
    rent_id = _account_id(client, "5100")
    utilities_id = _account_id(client, "5300")
    _create_bill(client, date="2026-03-15", amount_cents=10000)
    _create_budget(client, account_id=rent_id, budget_cents=20000)
    _create_budget(client, account_id=utilities_id, budget_cents=5000)

    body = _report(client)
    assert len(body["rows"]) == 2
    assert body["totals"]["budget_cents"] == 25000
    assert body["totals"]["actual_cents"] == 10000
    assert body["totals"]["variance_cents"] == 15000
