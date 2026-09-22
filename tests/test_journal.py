"""Tests for the journal API (the double-entry core)."""


def _account_id(client, number: str) -> int:
    accounts = {a["number"]: a for a in client.get("/api/accounts").json()}
    return accounts[number]["id"]


def _balanced_payload(client, **overrides):
    cash = _account_id(client, "1000")
    rent = _account_id(client, "5100")
    payload = {
        "date": "2026-01-15",
        "description": "Pay rent",
        "lines": [
            {"account_id": rent, "debit": 100000, "credit": 0},
            {"account_id": cash, "debit": 0, "credit": 100000},
        ],
    }
    payload.update(overrides)
    return payload


def test_create_journal_entry_success(client):
    response = client.post("/api/journal", json=_balanced_payload(client))
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "manual"
    assert body["source_id"] is None
    assert body["is_voided"] is False
    assert len(body["lines"]) == 2
    debits = sum(l["debit"] for l in body["lines"])
    credits = sum(l["credit"] for l in body["lines"])
    assert debits == credits == 100000
    assert {l["account_number"] for l in body["lines"]} == {"1000", "5100"}


def test_create_journal_entry_imbalanced_rejected(client):
    payload = _balanced_payload(client)
    payload["lines"][1]["credit"] = 200000
    response = client.post("/api/journal", json=payload)
    assert response.status_code == 422


def test_create_journal_entry_line_both_debit_credit_rejected(client):
    payload = _balanced_payload(client)
    payload["lines"][0]["credit"] = 100000
    response = client.post("/api/journal", json=payload)
    assert response.status_code == 422


def test_create_journal_entry_line_zero_rejected(client):
    rent = _account_id(client, "5100")
    cash = _account_id(client, "1000")
    response = client.post(
        "/api/journal",
        json={
            "date": "2026-01-15",
            "description": "Zero line",
            "lines": [
                {"account_id": rent, "debit": 0, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": 0},
            ],
        },
    )
    assert response.status_code == 422


def test_create_journal_entry_no_lines_rejected(client):
    response = client.post(
        "/api/journal",
        json={"date": "2026-01-15", "description": "No lines", "lines": []},
    )
    assert response.status_code == 422


def test_create_journal_entry_missing_account(client):
    payload = _balanced_payload(client)
    payload["lines"][0]["account_id"] = 999999
    response = client.post("/api/journal", json=payload)
    assert response.status_code == 404


def test_create_journal_entry_inactive_account_rejected(client):
    created = client.post(
        "/api/accounts",
        json={"number": "7000", "name": "Temp Expense", "type": "expense"},
    ).json()
    assert client.post(f"/api/accounts/{created['id']}/deactivate").status_code == 200
    cash = _account_id(client, "1000")
    response = client.post(
        "/api/journal",
        json={
            "date": "2026-01-15",
            "description": "Use inactive",
            "lines": [
                {"account_id": created["id"], "debit": 500, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": 500},
            ],
        },
    )
    assert response.status_code == 409


def test_get_journal_entry(client):
    created = client.post("/api/journal", json=_balanced_payload(client)).json()
    response = client.get(f"/api/journal/{created['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert len(body["lines"]) == 2


def test_get_journal_entry_not_found(client):
    response = client.get("/api/journal/999999")
    assert response.status_code == 404


def test_list_journal_entries(client):
    client.post("/api/journal", json=_balanced_payload(client))
    client.post("/api/journal", json=_balanced_payload(client, description="Second"))
    response = client.get("/api/journal")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_journal_entries_filter_by_date(client):
    rent = _account_id(client, "5100")
    cash = _account_id(client, "1000")
    client.post(
        "/api/journal",
        json={
            "date": "2026-01-15",
            "description": "Jan entry",
            "lines": [
                {"account_id": rent, "debit": 100, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": 100},
            ],
        },
    )
    client.post(
        "/api/journal",
        json={
            "date": "2026-03-15",
            "description": "Mar entry",
            "lines": [
                {"account_id": rent, "debit": 200, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": 200},
            ],
        },
    )
    response = client.get(
        "/api/journal", params={"date_from": "2026-02-01", "date_to": "2026-04-01"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["description"] == "Mar entry"


def test_list_journal_entries_filter_by_account(client):
    cash = _account_id(client, "1000")
    rent = _account_id(client, "5100")
    supplies = _account_id(client, "5400")
    client.post(
        "/api/journal",
        json={
            "date": "2026-01-15",
            "description": "Rent",
            "lines": [
                {"account_id": rent, "debit": 100, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": 100},
            ],
        },
    )
    client.post(
        "/api/journal",
        json={
            "date": "2026-01-16",
            "description": "Supplies",
            "lines": [
                {"account_id": supplies, "debit": 200, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": 200},
            ],
        },
    )
    response = client.get("/api/journal", params={"account_id": supplies})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["description"] == "Supplies"


def test_list_journal_entries_exclude_voided(client):
    created = client.post("/api/journal", json=_balanced_payload(client)).json()
    reversal = client.post(f"/api/journal/{created['id']}/void").json()
    assert len(client.get("/api/journal").json()) == 2
    active = client.get("/api/journal", params={"include_voided": "false"}).json()
    assert len(active) == 1
    assert active[0]["id"] == reversal["id"]


def test_void_journal_entry(client):
    created = client.post("/api/journal", json=_balanced_payload(client)).json()
    response = client.post(f"/api/journal/{created['id']}/void")
    assert response.status_code == 201
    reversal = response.json()
    assert reversal["description"].startswith("VOID: ")
    assert reversal["source_type"] == "void"
    assert reversal["source_id"] == created["id"]
    original_lines = {l["account_id"]: l for l in created["lines"]}
    for l in reversal["lines"]:
        orig = original_lines[l["account_id"]]
        assert l["debit"] == orig["credit"]
        assert l["credit"] == orig["debit"]
    original = client.get(f"/api/journal/{created['id']}").json()
    assert original["is_voided"] is True
    assert original["voided_by_id"] == reversal["id"]
    all_debits = sum(l["debit"] for l in created["lines"]) + sum(
        l["debit"] for l in reversal["lines"]
    )
    all_credits = sum(l["credit"] for l in created["lines"]) + sum(
        l["credit"] for l in reversal["lines"]
    )
    assert all_debits == all_credits


def test_void_journal_entry_already_voided(client):
    created = client.post("/api/journal", json=_balanced_payload(client)).json()
    client.post(f"/api/journal/{created['id']}/void")
    response = client.post(f"/api/journal/{created['id']}/void")
    assert response.status_code == 409


def test_void_journal_entry_not_found(client):
    response = client.post("/api/journal/999999/void")
    assert response.status_code == 404
