"""Tests for the chart of accounts API."""


def test_list_accounts_returns_seeded_coa(client):
    response = client.get("/api/accounts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 20
    numbers = [a["number"] for a in data]
    assert "1000" in numbers
    assert "4000" in numbers


def test_list_accounts_filter_by_type(client):
    response = client.get("/api/accounts", params={"type": "revenue"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert all(a["type"] == "revenue" for a in data)


def test_create_account(client):
    response = client.post(
        "/api/accounts",
        json={"number": "1600", "name": "Vehicles", "type": "asset", "subtype": "fixed_asset"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["number"] == "1600"
    assert body["is_system"] is False
    assert body["is_active"] is True


def test_create_account_duplicate_number_conflict(client):
    response = client.post(
        "/api/accounts",
        json={"number": "1000", "name": "Cash Copy", "type": "asset"},
    )
    assert response.status_code == 409


def test_create_account_invalid_number(client):
    response = client.post(
        "/api/accounts",
        json={"number": "abc", "name": "Bad Number", "type": "asset"},
    )
    assert response.status_code == 422


def test_get_account_not_found(client):
    response = client.get("/api/accounts/9999")
    assert response.status_code == 404


def test_update_account(client):
    created = client.post(
        "/api/accounts",
        json={"number": "1610", "name": "Furniture", "type": "asset"},
    ).json()
    response = client.patch(f"/api/accounts/{created['id']}", json={"description": "Office furniture"})
    assert response.status_code == 200
    assert response.json()["description"] == "Office furniture"


def test_deactivate_account(client):
    created = client.post(
        "/api/accounts",
        json={"number": "1620", "name": "Leases", "type": "asset"},
    ).json()
    response = client.post(f"/api/accounts/{created['id']}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    listing = client.get("/api/accounts").json()
    assert all(a["id"] != created["id"] for a in listing)


def test_deactivate_system_account_rejected(client):
    cash = next(a for a in client.get("/api/accounts").json() if a["number"] == "1000")
    response = client.post(f"/api/accounts/{cash['id']}/deactivate")
    assert response.status_code == 409
