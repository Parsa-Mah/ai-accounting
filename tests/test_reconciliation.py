"""Tests for the bank reconciliation API (register, create, list, delete, void guard)."""


def _account_id(client, number: str) -> int:
    accounts = {a["number"]: a for a in client.get("/api/accounts").json()}
    return accounts[number]["id"]


def _post_entry(client, date, description, lines):
    response = client.post(
        "/api/journal",
        json={"date": date, "description": description, "lines": lines},
    )
    assert response.status_code == 201
    return response.json()


def _line_id_for_account(client, entry, number: str) -> int:
    account_id = _account_id(client, number)
    for line in entry["lines"]:
        if line["account_id"] == account_id:
            return line["id"]
    raise AssertionError(f"no line for account {number}")


def _create_bank_account(client, number, name, bank_kind) -> int:
    response = client.post(
        "/api/accounts",
        json={
            "number": number,
            "name": name,
            "type": "asset",
            "bank_kind": bank_kind,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_cash_activity(client):
    """Three cash entries: one prior (uncleared), two to be cleared.

    Returns (prior_entry, deposit_entry, withdrawal_entry).
    """
    cash = _account_id(client, "1000")
    revenue = _account_id(client, "4000")
    rent = _account_id(client, "5100")
    prior = _post_entry(
        client, "2026-02-15", "Opening deposit",
        [
            {"account_id": cash, "debit": 5000, "credit": 0},
            {"account_id": revenue, "debit": 0, "credit": 5000},
        ],
    )
    deposit = _post_entry(
        client, "2026-03-10", "Client payment",
        [
            {"account_id": cash, "debit": 10000, "credit": 0},
            {"account_id": revenue, "debit": 0, "credit": 10000},
        ],
    )
    withdrawal = _post_entry(
        client, "2026-03-20", "Pay rent",
        [
            {"account_id": rent, "debit": 2000, "credit": 0},
            {"account_id": cash, "debit": 0, "credit": 2000},
        ],
    )
    return prior, deposit, withdrawal


def _reconcile(client, line_ids, statement_balance_cents, statement_date="2026-03-31",
               account_number="1000", **overrides):
    payload = {
        "account_id": _account_id(client, account_number),
        "statement_date": statement_date,
        "statement_balance_cents": statement_balance_cents,
        "line_ids": line_ids,
    }
    payload.update(overrides)
    return client.post("/api/reconciliation", json=payload)


def test_list_bank_accounts(client):
    body = client.get("/api/reconciliation/accounts").json()
    numbers = {a["number"] for a in body}
    assert "1000" in numbers
    assert "1100" not in numbers  # AR is not a bank account
    cash = next(a for a in body if a["number"] == "1000")
    assert cash["bank_kind"] == "checking"
    assert cash["balance_cents"] == 0


def test_create_reconciliation_balanced(client):
    _, deposit, withdrawal = _seed_cash_activity(client)
    cash = _account_id(client, "1000")
    line_ids = [
        _line_id_for_account(client, deposit, "1000"),
        _line_id_for_account(client, withdrawal, "1000"),
    ]
    response = _reconcile(client, line_ids, statement_balance_cents=13000)
    assert response.status_code == 201
    body = response.json()
    assert body["account_id"] == cash
    assert body["opening_balance_cents"] == 5000
    assert body["cleared_total_cents"] == 8000
    assert body["difference_cents"] == 0
    assert body["is_balanced"] is True
    assert body["line_count"] == 2


def test_create_reconciliation_difference(client):
    _, deposit, withdrawal = _seed_cash_activity(client)
    line_ids = [
        _line_id_for_account(client, deposit, "1000"),
        _line_id_for_account(client, withdrawal, "1000"),
    ]
    response = _reconcile(client, line_ids, statement_balance_cents=13500)
    assert response.status_code == 201
    body = response.json()
    assert body["difference_cents"] == 500
    assert body["is_balanced"] is False


def test_create_reconciliation_non_bank_account(client):
    ar = _account_id(client, "1100")
    revenue = _account_id(client, "4000")
    entry = _post_entry(
        client, "2026-03-10", "Invoice",
        [
            {"account_id": ar, "debit": 5000, "credit": 0},
            {"account_id": revenue, "debit": 0, "credit": 5000},
        ],
    )
    line_id = _line_id_for_account(client, entry, "1100")
    response = _reconcile(client, [line_id], 5000, account_number="1100")
    assert response.status_code == 422


def test_create_reconciliation_unknown_account(client):
    response = client.post(
        "/api/reconciliation",
        json={
            "account_id": 9999,
            "statement_date": "2026-03-31",
            "statement_balance_cents": 0,
            "line_ids": [1],
        },
    )
    assert response.status_code == 404


def test_create_reconciliation_line_wrong_account(client):
    _, deposit, _ = _seed_cash_activity(client)
    ar = _account_id(client, "1100")
    revenue = _account_id(client, "4000")
    entry = _post_entry(
        client, "2026-03-12", "Invoice",
        [
            {"account_id": ar, "debit": 5000, "credit": 0},
            {"account_id": revenue, "debit": 0, "credit": 5000},
        ],
    )
    ar_line = _line_id_for_account(client, entry, "1100")
    response = _reconcile(client, [ar_line], 5000)
    assert response.status_code == 422


def test_create_reconciliation_line_already_cleared(client):
    _, deposit, withdrawal = _seed_cash_activity(client)
    line_ids = [
        _line_id_for_account(client, deposit, "1000"),
        _line_id_for_account(client, withdrawal, "1000"),
    ]
    assert _reconcile(client, line_ids, 13000).status_code == 201
    response = _reconcile(client, line_ids, 13000)
    assert response.status_code == 409


def test_create_reconciliation_line_after_statement_date(client):
    cash = _account_id(client, "1000")
    revenue = _account_id(client, "4000")
    entry = _post_entry(
        client, "2026-04-05", "Late deposit",
        [
            {"account_id": cash, "debit": 1000, "credit": 0},
            {"account_id": revenue, "debit": 0, "credit": 1000},
        ],
    )
    line_id = _line_id_for_account(client, entry, "1000")
    response = _reconcile(client, [line_id], 1000, statement_date="2026-03-31")
    assert response.status_code == 422


def test_create_reconciliation_unknown_line(client):
    response = _reconcile(client, [9999], 0)
    assert response.status_code == 404


def test_get_reconciliation(client):
    _, deposit, withdrawal = _seed_cash_activity(client)
    line_ids = [
        _line_id_for_account(client, deposit, "1000"),
        _line_id_for_account(client, withdrawal, "1000"),
    ]
    created = _reconcile(client, line_ids, 13000, note="March statement").json()
    response = client.get(f"/api/reconciliation/{created['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["note"] == "March statement"
    assert body["line_count"] == 2
    assert [l["date"] for l in body["lines"]] == ["2026-03-10", "2026-03-20"]


def test_get_reconciliation_not_found(client):
    assert client.get("/api/reconciliation/9999").status_code == 404


def test_list_reconciliations_filter_account(client):
    _, deposit, withdrawal = _seed_cash_activity(client)
    cash_lines = [
        _line_id_for_account(client, deposit, "1000"),
        _line_id_for_account(client, withdrawal, "1000"),
    ]
    _reconcile(client, cash_lines, 13000)

    savings = _create_bank_account(client, "1010", "Savings", "savings")
    revenue = _account_id(client, "4000")
    entry = _post_entry(
        client, "2026-03-15", "Savings deposit",
        [
            {"account_id": savings, "debit": 3000, "credit": 0},
            {"account_id": revenue, "debit": 0, "credit": 3000},
        ],
    )
    savings_line = next(l["id"] for l in entry["lines"] if l["account_id"] == savings)
    _reconcile(client, [savings_line], 3000, account_number="1010")

    assert len(client.get("/api/reconciliation").json()) == 2
    filtered = client.get(
        "/api/reconciliation", params={"account_id": savings}
    ).json()
    assert len(filtered) == 1
    assert filtered[0]["account_id"] == savings


def test_delete_reconciliation_unclears(client):
    _, deposit, withdrawal = _seed_cash_activity(client)
    line_ids = [
        _line_id_for_account(client, deposit, "1000"),
        _line_id_for_account(client, withdrawal, "1000"),
    ]
    created = _reconcile(client, line_ids, 13000).json()

    response = client.delete(f"/api/reconciliation/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/reconciliation/{created['id']}").status_code == 404

    # Lines are un-cleared and can be reconciled again.
    assert _reconcile(client, line_ids, 13000).status_code == 201


def test_void_cleared_entry_conflict(client):
    _, deposit, _ = _seed_cash_activity(client)
    line_id = _line_id_for_account(client, deposit, "1000")
    _reconcile(client, [line_id], 15000)

    response = client.post(f"/api/journal/{deposit['id']}/void")
    assert response.status_code == 409


def test_general_ledger_shows_cleared(client):
    _, deposit, withdrawal = _seed_cash_activity(client)
    line_ids = [
        _line_id_for_account(client, deposit, "1000"),
        _line_id_for_account(client, withdrawal, "1000"),
    ]
    created = _reconcile(client, line_ids, 13000).json()

    cash = _account_id(client, "1000")
    body = client.get(f"/api/ledger/accounts/{cash}/transactions").json()
    by_entry = {l["entry_id"]: l for l in body["lines"]}
    cleared = by_entry[deposit["id"]]
    assert cleared["cleared"] is True
    assert cleared["reconciliation_id"] == created["id"]
    prior = by_entry[_seed_prior_entry_id(client, body)]
    assert prior["cleared"] is False
    assert prior["reconciliation_id"] is None


def _seed_prior_entry_id(client, ledger_body):
    # The opening (uncleared) entry is the one dated 2026-02-15.
    for line in ledger_body["lines"]:
        if line["date"] == "2026-02-15":
            return line["entry_id"]
    raise AssertionError("prior entry not found in ledger")
