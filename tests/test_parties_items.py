"""Tests for the customers/vendors and items APIs."""


def _create_customer(client, name="Acme Corp", **extra):
    response = client.post("/api/customers", json={"name": name, **extra})
    assert response.status_code == 201
    return response.json()


def test_create_customer(client):
    body = _create_customer(
        client, email="a@acme.com", phone="555-0100", address="1 Main St"
    )
    assert body["id"] >= 1
    assert body["name"] == "Acme Corp"
    assert body["email"] == "a@acme.com"
    assert body["phone"] == "555-0100"
    assert body["address"] == "1 Main St"


def test_create_customer_requires_name(client):
    response = client.post("/api/customers", json={})
    assert response.status_code == 422


def test_list_customers(client):
    _create_customer(client, "Acme Corp")
    _create_customer(client, "Globex")
    body = client.get("/api/customers").json()
    assert [c["name"] for c in body] == ["Acme Corp", "Globex"]


def test_get_customer(client):
    created = _create_customer(client)
    body = client.get(f"/api/customers/{created['id']}").json()
    assert body["id"] == created["id"]
    assert body["name"] == "Acme Corp"


def test_get_customer_not_found(client):
    assert client.get("/api/customers/9999").status_code == 404


def test_create_vendor(client):
    response = client.post("/api/vendors", json={"name": "Inkwell Supplies"})
    assert response.status_code == 201
    assert response.json()["name"] == "Inkwell Supplies"


def test_list_vendors(client):
    client.post("/api/vendors", json={"name": "Inkwell Supplies"})
    body = client.get("/api/vendors").json()
    assert [v["name"] for v in body] == ["Inkwell Supplies"]


def test_get_vendor_not_found(client):
    assert client.get("/api/vendors/9999").status_code == 404


def test_create_item(client):
    response = client.post(
        "/api/items", json={"name": "Consulting", "unit_price_cents": 15000}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Consulting"
    assert body["unit_price_cents"] == 15000
    assert body["is_active"] is True


def test_create_item_negative_price_rejected(client):
    response = client.post("/api/items", json={"name": "X", "unit_price_cents": -1})
    assert response.status_code == 422


def test_update_item(client):
    created = client.post(
        "/api/items", json={"name": "Consulting", "unit_price_cents": 15000}
    ).json()
    response = client.patch(
        f"/api/items/{created['id']}", json={"unit_price_cents": 20000}
    )
    assert response.status_code == 200
    assert response.json()["unit_price_cents"] == 20000


def test_deactivate_item_hidden_from_list(client):
    created = client.post("/api/items", json={"name": "Consulting"}).json()
    response = client.post(f"/api/items/{created['id']}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert client.get("/api/items").json() == []
    assert len(client.get("/api/items", params={"include_inactive": "true"}).json()) == 1


def test_get_item_not_found(client):
    assert client.get("/api/items/9999").status_code == 404
