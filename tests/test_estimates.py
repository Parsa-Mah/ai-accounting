"""Tests for the estimates API (quotes + convert-to-invoice)."""


def _create_customer(client, name="Acme Corp") -> int:
    response = client.post("/api/customers", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_estimate(client, customer_id=None, tax_rate=0.0, lines=None, **overrides):
    if customer_id is None:
        customer_id = _create_customer(client)
    if lines is None:
        lines = [{"description": "Website", "quantity": 1, "unit_price_cents": 50000}]
    payload = {
        "customer_id": customer_id,
        "date": "2026-03-01",
        "tax_rate": tax_rate,
        "lines": lines,
    }
    payload.update(overrides)
    response = client.post("/api/estimates", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_estimate_computes_totals(client):
    estimate = _create_estimate(client, tax_rate=10.0)
    assert estimate["subtotal_cents"] == 50000
    assert estimate["tax_cents"] == 5000
    assert estimate["total_cents"] == 55000
    assert estimate["status"] == "open"
    assert estimate["converted_invoice_id"] is None


def test_create_estimate_posts_nothing_to_ledger(client):
    _create_estimate(client)
    assert client.get("/api/journal").json() == []


def test_convert_estimate_creates_invoice(client):
    estimate = _create_estimate(client, tax_rate=10.0)
    response = client.post(f"/api/estimates/{estimate['id']}/convert")
    assert response.status_code == 201
    invoice = response.json()
    assert invoice["customer_id"] == estimate["customer_id"]
    assert invoice["subtotal_cents"] == 50000
    assert invoice["tax_cents"] == 5000
    assert invoice["total_cents"] == 55000
    assert invoice["status"] == "open"
    assert [line["description"] for line in invoice["lines"]] == ["Website"]

    entry = client.get(f"/api/journal/{invoice['entry_id']}").json()
    assert entry["source_type"] == "invoice"
    assert entry["source_id"] == invoice["id"]

    refreshed = client.get(f"/api/estimates/{estimate['id']}").json()
    assert refreshed["status"] == "converted"
    assert refreshed["converted_invoice_id"] == invoice["id"]


def test_convert_estimate_twice_rejected(client):
    estimate = _create_estimate(client)
    client.post(f"/api/estimates/{estimate['id']}/convert")
    response = client.post(f"/api/estimates/{estimate['id']}/convert")
    assert response.status_code == 409


def test_convert_estimate_unknown(client):
    assert client.post("/api/estimates/9999/convert").status_code == 404


def test_create_estimate_unknown_customer(client):
    response = client.post(
        "/api/estimates",
        json={
            "customer_id": 9999,
            "date": "2026-03-01",
            "lines": [{"description": "X", "unit_price_cents": 100}],
        },
    )
    assert response.status_code == 404


def test_list_estimates_excludes_converted_when_requested(client):
    estimate = _create_estimate(client)
    client.post(f"/api/estimates/{estimate['id']}/convert")
    assert len(client.get("/api/estimates").json()) == 1
    assert (
        client.get("/api/estimates", params={"include_converted": "false"}).json()
        == []
    )
