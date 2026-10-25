"""In-memory MCP client tests (Python SDK v2 pattern, anyio/asyncio).

The client talks to the server in-process (no subprocess, no port).
``raise_exceptions=True`` surfaces failures outside tool bodies with the
real message; tool errors still come back as ``is_error=True`` results.

Demo-seed expectations (relative to the current month): 5 invoices
(paid, partially_paid, open, void, paid), 4 bills (2 paid, 2 open),
1 open estimate, 4 budgets (3 current-month, 1 previous-month),
2x "Monthly rent" entries, 1 balanced Cash reconciliation.
"""

import csv
import datetime
import io

import pytest

from app.database import Base, engine
from app.mcp.server import build_server
from app.seed.demo import seed_demo_data
from mcp import Client
from mcp.types import TextContent, TextResourceContents


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def mcp_server():
    """MCP server against a fresh database seeded with the demo business."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_demo_data()
    return build_server()


@pytest.fixture
def write_server(monkeypatch):
    """Like mcp_server, but with MCP_ALLOW_WRITE=1 (set before build)."""
    monkeypatch.setenv("MCP_ALLOW_WRITE", "1")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_demo_data()
    return build_server()


@pytest.fixture
def empty_write_server(monkeypatch):
    """Fresh, UNSEEDED database with write tools enabled (COA only, via
    build_server's init_db). Used to exercise the seed_demo_data tool's
    real-seed path."""
    monkeypatch.setenv("MCP_ALLOW_WRITE", "1")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return build_server()


WRITE_TOOL_NAMES = {
    "create_journal_entry",
    "void_journal_entry",
    "create_reconciliation",
    "delete_reconciliation",
    "lock_period",
    "unlock_period",
    "create_invoice",
    "pay_invoice",
    "void_invoice",
    "create_bill",
    "pay_bill",
    "void_bill",
    "create_estimate",
    "convert_estimate",
    "create_budget",
    "update_budget",
    "delete_budget",
    "create_customer",
    "create_vendor",
    "create_item",
    "update_item",
    "deactivate_item",
    "create_account",
    "update_account",
    "deactivate_account",
    "seed_demo_data",
}


def _rows(result) -> list[dict]:
    """Unwrap the SDK's list-result wrapper ({'result': [...]}) if present."""
    content = result.structured_content
    return content["result"] if isinstance(content, dict) else content


def _text(result) -> str:
    """The text of a tool result's first content block."""
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def _csv_rows(result) -> list[list[str]]:
    """The parsed CSV rows (header first) of an export_report result."""
    body = result.structured_content
    return [row for row in csv.reader(io.StringIO(body["csv"]))]


def _current_month() -> str:
    return datetime.date.today().strftime("%Y-%m")


def _current_month_range() -> tuple[str, str]:
    today = datetime.date.today()
    first = today.replace(day=1)
    if today.month == 12:
        last = datetime.date(today.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last = datetime.date(today.year, today.month + 1, 1) - datetime.timedelta(days=1)
    return first.isoformat(), last.isoformat()


async def _current_month_cash(client) -> tuple[dict, list[int]]:
    """The demo's bank account row plus its uncleared current-month line ids.

    The seeded reconciliation only cleared previous-month lines, so every
    current-month cash line is still uncleared. Using the account's current
    net balance as the statement balance yields a balanced reconciliation
    (opening + cleared total equals the full balance).
    """
    banks = _rows(await client.call_tool("list_bank_accounts", {}))
    bank = next(row for row in banks if row["number"] == "1000")
    start, end = _current_month_range()
    lines = _rows(
        await client.call_tool(
            "search_transactions",
            {"account": "1000", "date_from": start, "date_to": end},
        )
    )
    assert lines, "demo seed should have current-month cash activity"
    return bank, [row["line_id"] for row in lines]


async def _reconcile_current_month(client, bank: dict, line_ids: list[int]) -> dict:
    """Create a balanced reconciliation for the current month's cash lines."""
    result = await client.call_tool(
        "create_reconciliation",
        {
            "account": "1000",
            "statement_date": _current_month_range()[1],
            "statement_balance_cents": bank["balance_cents"],
            "line_ids": line_ids,
        },
    )
    assert result.is_error is False
    return result.structured_content


async def _current_month_rent(client) -> dict:
    """The demo's current-month 'Monthly rent' entry (uncleared lines).

    The seeded reconciliation only cleared previous-month lines, so this
    entry's lines are all uncleared and it can be voided.
    """
    start, end = _current_month_range()
    rows = _rows(
        await client.call_tool(
            "list_journal_entries", {"date_from": start, "date_to": end}
        )
    )
    rent = next(row for row in rows if row["description"] == "Monthly rent")
    assert rent["is_voided"] is False
    return rent


@pytest.mark.anyio
async def test_list_accounts(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_accounts", {})
    assert result.is_error is False
    rows = _rows(result)
    assert isinstance(rows, list) and rows
    cash = next(row for row in rows if row["number"] == "1000")
    assert cash["name"] == "Cash"
    assert cash["type"] == "asset"
    assert cash["active"] is True


@pytest.mark.anyio
async def test_income_statement_current_month(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "get_income_statement", {"month": _current_month()}
        )
    assert result.is_error is False
    body = result.structured_content
    # Revenue: inv5 100000 (inv4's 125000 is voided and nets to zero).
    assert body["total_revenue"] == 100000
    assert body["total_revenue_usd"] == "1000.00"
    # Expenses: rent 200000 + supplies 32500 + hosting 9900.
    assert body["total_expenses"] == 242400
    assert body["net_income"] == -142400
    assert body["net_income_usd"] == "-1424.00"


@pytest.mark.anyio
async def test_balance_sheet_balanced(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("get_balance_sheet", {})
    assert result.is_error is False
    body = result.structured_content
    assert body["balanced"] is True
    assert body["total_assets"] > 0
    assert body["total_assets"] == body["total_liabilities"] + body["total_equity"]


@pytest.mark.anyio
async def test_trial_balance_balanced(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("get_trial_balance", {})
    assert result.is_error is False
    body = result.structured_content
    assert body["balanced"] is True
    assert body["totals"]["debit"] == body["totals"]["credit"]
    assert body["totals"]["debit"] > 0


@pytest.mark.anyio
async def test_account_ledger_cash(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("get_account_ledger", {"account": "Cash"})
    assert result.is_error is False
    body = result.structured_content
    assert body["account_number"] == "1000"
    assert body["account_name"] == "Cash"
    assert body["opening_balance"] == 0
    assert len(body["lines"]) > 0
    movement = sum(line["debit"] - line["credit"] for line in body["lines"])
    assert body["closing_balance"] == body["opening_balance"] + movement
    assert body["closing_balance_usd"]
    assert body["lines"][0]["date"]  # ISO date string


@pytest.mark.anyio
async def test_search_transactions_query_and_account(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        by_query = await client.call_tool(
            "search_transactions", {"query": "rent"}
        )
        by_account = await client.call_tool(
            "search_transactions", {"account": "1000"}
        )
    assert by_query.is_error is False
    rows = _rows(by_query)
    assert len(rows) == 4  # 2 "Monthly rent" entries x 2 lines
    assert all(row["entry_description"] == "Monthly rent" for row in rows)
    assert {row["account_number"] for row in rows} == {"5100", "1000"}

    assert by_account.is_error is False
    rows = _rows(by_account)
    assert len(rows) > 0
    assert all(row["account_number"] == "1000" for row in rows)


@pytest.mark.anyio
async def test_export_report_trial_balance(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "trial_balance"})
    assert result.is_error is False
    body = result.structured_content
    assert body["title"] == "Trial Balance"
    assert body["subtitle"] == "All time"
    assert body["filename"] == "trial-balance.csv"
    rows = _csv_rows(result)
    assert rows[0] == ["number", "name", "type", "debit", "credit"]
    assert rows[-1][2] == "Total"
    cash = next(row for row in rows[1:-1] if row[0] == "1000")
    assert cash[1] == "Cash"
    assert cash[2] == "asset"


@pytest.mark.anyio
async def test_export_report_general_ledger(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "export_report", {"report": "general_ledger", "account": "1000"}
        )
    assert result.is_error is False
    body = result.structured_content
    assert body["title"] == "General Ledger"
    assert body["filename"] == "general-ledger-1000.csv"
    rows = _csv_rows(result)
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
    # The capital injection's cash line shows $25,000.00 as formatted dollars.
    assert any(
        row[3] == "Cash" and row[4] == "25000.00" for row in rows[1:-1]
    )


@pytest.mark.anyio
async def test_export_report_general_ledger_missing_account(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "general_ledger"})
    assert result.is_error is True
    assert "account" in _text(result)


@pytest.mark.anyio
async def test_export_report_income_statement(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "income_statement"})
    assert result.is_error is False
    body = result.structured_content
    assert body["title"] == "Income Statement"
    assert body["filename"] == "income-statement.csv"
    rows = _csv_rows(result)
    assert rows[0] == ["section", "number", "name", "amount"]
    names = [row[2] for row in rows[1:]]
    assert "Total revenue" in names
    assert "Total expenses" in names
    assert "Net income" in names


@pytest.mark.anyio
async def test_export_report_balance_sheet(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "balance_sheet"})
    assert result.is_error is False
    body = result.structured_content
    assert body["title"] == "Balance Sheet"
    assert body["filename"] == "balance-sheet.csv"
    rows = _csv_rows(result)
    assert rows[0] == ["section", "number", "name", "amount"]
    names = [row[2] for row in rows[1:]]
    assert "Total assets" in names
    assert "Total liabilities" in names
    assert "Total equity" in names


@pytest.mark.anyio
async def test_export_report_journal(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "journal"})
    assert result.is_error is False
    body = result.structured_content
    assert body["title"] == "Journal"
    assert body["filename"] == "journal.csv"
    rows = _csv_rows(result)
    assert rows[0] == [
        "entry",
        "date",
        "description",
        "account_number",
        "account_name",
        "debit",
        "credit",
    ]
    descs = [row[2] for row in rows[1:]]
    assert "Owner capital injection" in descs
    capital = next(
        row for row in rows[1:] if row[2] == "Owner capital injection" and row[3] == "1000"
    )
    assert capital[5] == "25000.00"


@pytest.mark.anyio
async def test_export_report_invoices(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "invoices"})
    assert result.is_error is False
    body = result.structured_content
    assert body["title"] == "Invoices"
    assert body["filename"] == "invoices.csv"
    rows = _csv_rows(result)
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
    data = rows[1:]
    assert len(data) == 5  # demo seed: 5 invoices (include_voided default True)
    customers = {row[3] for row in data}
    assert customers == {"Acme Corporation", "Globex Inc", "Initech LLC"}


@pytest.mark.anyio
async def test_export_report_bills(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "bills"})
    assert result.is_error is False
    body = result.structured_content
    assert body["title"] == "Bills"
    assert body["filename"] == "bills.csv"
    rows = _csv_rows(result)
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
    data = rows[1:]
    assert len(data) == 4  # demo seed: 4 bills
    vendors = {row[3] for row in data}
    assert "CloudHost Inc" in vendors


@pytest.mark.anyio
async def test_export_report_invalid_report(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("export_report", {"report": "payroll"})
    assert result.is_error is True
    text = _text(result)
    assert "Invalid report" in text
    assert "payroll" in text


@pytest.mark.anyio
async def test_list_journal_entries(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_journal_entries", {})
    assert result.is_error is False
    rows = _rows(result)
    assert rows
    for row in rows:
        assert row["id"] and row["date"] and row["description"]
        assert row["source_type"]
        assert isinstance(row["is_voided"], bool)
        assert row["lines"]
    capital = next(
        row for row in rows if row["description"] == "Owner capital injection"
    )
    assert capital["source_type"] == "manual"
    assert capital["is_voided"] is False
    assert capital["voided_by_id"] is None
    assert len(capital["lines"]) == 2
    assert {line["account_number"] for line in capital["lines"]} == {
        "1000",
        "3000",
    }
    debit_line = next(line for line in capital["lines"] if line["debit"] > 0)
    assert debit_line["account_number"] == "1000"
    assert debit_line["debit"] == 2500000
    assert debit_line["debit_usd"] == "25000.00"
    # Ordered by (date, id), oldest first.
    keys = [(row["date"], row["id"]) for row in rows]
    assert keys == sorted(keys)


@pytest.mark.anyio
async def test_list_journal_entries_filters(mcp_server) -> None:
    start, end = _current_month_range()
    async with Client(mcp_server, raise_exceptions=True) as client:
        by_date = await client.call_tool(
            "list_journal_entries", {"date_from": start, "date_to": end}
        )
        by_account = await client.call_tool(
            "list_journal_entries",
            {"date_from": start, "date_to": end, "account": "1000"},
        )
    assert by_date.is_error is False
    rows = _rows(by_date)
    assert rows
    assert all(start <= row["date"] <= end for row in rows)
    assert any(row["description"] == "Monthly rent" for row in rows)
    assert not any(row["description"] == "Owner capital injection" for row in rows)

    assert by_account.is_error is False
    rows = _rows(by_account)
    assert rows
    # Every returned entry touches Cash (at least one line on 1000).
    assert all(
        any(line["account_number"] == "1000" for line in row["lines"]) for row in rows
    )
    assert any(row["description"] == "Monthly rent" for row in rows)


@pytest.mark.anyio
async def test_get_journal_entry(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        rows = _rows(await client.call_tool("list_journal_entries", {}))
        capital = next(
            row for row in rows if row["description"] == "Owner capital injection"
        )
        result = await client.call_tool(
            "get_journal_entry", {"entry_id": capital["id"]}
        )
    assert result.is_error is False
    body = result.structured_content
    assert body["id"] == capital["id"]
    assert body["description"] == "Owner capital injection"
    assert body["is_voided"] is False
    assert body["voided_by_id"] is None
    assert len(body["lines"]) == 2


@pytest.mark.anyio
async def test_get_journal_entry_missing(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("get_journal_entry", {"entry_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_list_invoices_status_filters(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        paid = _rows(await client.call_tool("list_invoices", {"status": "paid"}))
        open_ = _rows(await client.call_tool("list_invoices", {"status": "open"}))
        partial = _rows(
            await client.call_tool("list_invoices", {"status": "partially_paid"})
        )
        voided = _rows(await client.call_tool("list_invoices", {"status": "void"}))
    assert [row["total_cents"] for row in paid] == [100000, 270000]
    assert len(open_) == 1 and open_[0]["total_cents"] == 1080000
    assert len(partial) == 1 and partial[0]["total_cents"] == 150000
    assert len(voided) == 1 and voided[0]["total_cents"] == 125000


@pytest.mark.anyio
async def test_list_invoices_month_filter(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "list_invoices", {"month": _current_month()}
        )
    rows = _rows(result)
    assert len(rows) == 2  # the voided and the paid current-month invoices
    assert {row["status"] for row in rows} == {"void", "paid"}


@pytest.mark.anyio
async def test_get_invoice_detail(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        listed = _rows(
            await client.call_tool("list_invoices", {"status": "paid"})
        )
        acme = next(row for row in listed if row["customer_name"] == "Acme Corporation")
        detail = await client.call_tool("get_invoice", {"invoice_id": acme["id"]})
    assert detail.is_error is False
    body = detail.structured_content
    assert body["total_cents"] == 270000
    assert body["total_cents_usd"] == "2700.00"
    assert body["tax_cents"] == 20000
    assert body["status"] == "paid"
    assert len(body["lines"]) == 1
    assert len(body["payments"]) == 1
    assert body["payments"][0]["amount_cents"] == 270000


@pytest.mark.anyio
async def test_list_bills_status_filters(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        paid = _rows(await client.call_tool("list_bills", {"status": "paid"}))
        open_ = _rows(await client.call_tool("list_bills", {"status": "open"}))
    assert {row["total_cents"] for row in paid} == {29700, 45000}
    assert {row["total_cents"] for row in open_} == {32500, 9900}


@pytest.mark.anyio
async def test_list_estimates(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_estimates", {})
    rows = _rows(result)
    assert len(rows) == 1
    assert rows[0]["status"] == "open"
    assert rows[0]["customer_name"] == "Globex Inc"
    assert rows[0]["total_cents"] == 750000


@pytest.mark.anyio
async def test_get_bill_detail(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_bills", {"status": "open"}))
        offimax = next(
            row for row in listed if row["vendor_name"] == "OfficeMax Supplies"
        )
        result = await client.call_tool("get_bill", {"bill_id": offimax["id"]})
    assert result.is_error is False
    body = result.structured_content
    assert body["vendor_name"] == "OfficeMax Supplies"
    assert body["status"] == "open"
    assert body["total_cents"] == 32500
    assert body["total_cents_usd"] == "325.00"
    assert body["paid_cents"] == 0
    assert len(body["lines"]) == 1
    assert body["lines"][0]["expense_account_id"]
    assert body["payments"] == []


@pytest.mark.anyio
async def test_get_bill_missing_is_tool_error(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("get_bill", {"bill_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_get_estimate_detail(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_estimates", {}))
        result = await client.call_tool(
            "get_estimate", {"estimate_id": listed[0]["id"]}
        )
    assert result.is_error is False
    body = result.structured_content
    assert body["customer_name"] == "Globex Inc"
    assert body["status"] == "open"
    assert body["subtotal_cents"] == 750000
    assert body["subtotal_cents_usd"] == "7500.00"
    assert body["tax_cents"] == 0
    assert body["total_cents"] == 750000
    assert [line["description"] for line in body["lines"]] == [
        "Website Design",
        "Consulting (day)",
    ]


@pytest.mark.anyio
async def test_get_estimate_missing_is_tool_error(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("get_estimate", {"estimate_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_list_budgets(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_budgets", {})
    rows = _rows(result)
    assert len(rows) == 4
    assert [row["account_number"] for row in rows] == ["5500", "5700", "5100", "5100"]
    assert all(row["note"] for row in rows)


@pytest.mark.anyio
async def test_list_budgets_account_filter(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        by_number = _rows(await client.call_tool("list_budgets", {"account": "5100"}))
        by_name = _rows(
            await client.call_tool("list_budgets", {"account": "Rent Expense"})
        )
    assert len(by_number) == 2
    assert all(row["account_number"] == "5100" for row in by_number)
    assert all(row["note"] == "Monthly rent" for row in by_number)
    assert {row["id"] for row in by_number} == {row["id"] for row in by_name}


@pytest.mark.anyio
async def test_list_budgets_unknown_account(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_budgets", {"account": "9999"})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_get_budget_detail(mcp_server) -> None:
    start, end = _current_month_range()
    async with Client(mcp_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_budgets", {"account": "5500"}))
        result = await client.call_tool("get_budget", {"budget_id": listed[0]["id"]})
    assert result.is_error is False
    body = result.structured_content
    assert body["account_number"] == "5500"
    assert body["account_name"] == "Marketing Expense"
    assert body["budget_cents"] == 50000
    assert body["budget_cents_usd"] == "500.00"
    assert body["note"] == "Advertising and events"
    assert body["budget_start"] == start
    assert body["budget_end"] == end


@pytest.mark.anyio
async def test_get_budget_missing_is_tool_error(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("get_budget", {"budget_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_budget_report_current_month(mcp_server) -> None:
    start, end = _current_month_range()
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "get_budget_report", {"start": start, "end": end}
        )
    assert result.is_error is False
    body = result.structured_content
    by_number = {row["account_number"]: row for row in body["rows"]}
    assert set(by_number) == {"5100", "5700", "5500"}
    rent = by_number["5100"]
    assert rent["budget_cents"] == 200000
    assert rent["actual_cents"] == 200000
    assert rent["variance_cents"] == 0
    assert rent["within_budget"] is True
    software = by_number["5700"]
    assert software["actual_cents"] == 9900
    assert software["variance_cents"] == 5100


@pytest.mark.anyio
async def test_list_bank_accounts(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_bank_accounts", {})
    rows = _rows(result)
    assert len(rows) == 1
    row = rows[0]
    assert row["number"] == "1000"
    assert row["name"] == "Cash"
    assert row["bank_kind"] == "checking"
    assert row["balance_cents"] > 0
    assert row["balance_cents_usd"]


@pytest.mark.anyio
async def test_list_reconciliations(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_reconciliations", {})
    rows = _rows(result)
    assert len(rows) == 1
    recon = rows[0]
    assert recon["account_number"] == "1000"
    assert recon["is_balanced"] is True
    assert recon["difference_cents"] == 0
    assert recon["difference_cents_usd"] == "0.00"


@pytest.mark.anyio
async def test_list_customers(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_customers", {})
    assert result.is_error is False
    rows = _rows(result)
    assert [row["name"] for row in rows] == [
        "Acme Corporation",
        "Globex Inc",
        "Initech LLC",
    ]
    assert rows[0]["email"] == "billing@acme.example"
    assert rows[0]["id"] and rows[0]["created_at"]


@pytest.mark.anyio
async def test_list_vendors(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_vendors", {})
    assert result.is_error is False
    rows = _rows(result)
    assert [row["name"] for row in rows] == [
        "City Power & Light",
        "CloudHost Inc",
        "OfficeMax Supplies",
    ]


@pytest.mark.anyio
async def test_list_items(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_items", {})
    assert result.is_error is False
    rows = _rows(result)
    assert len(rows) == 5
    assert all(row["is_active"] is True for row in rows)
    consulting = next(row for row in rows if row["name"] == "Consulting (day)")
    assert consulting["unit_price_cents"] == 25000
    assert consulting["unit_price_cents_usd"] == "250.00"


@pytest.mark.anyio
async def test_resources_listed_and_readable(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        listed = await client.list_resources()
        uris = {resource.uri for resource in listed.resources}
        assert uris == {"accounting://accounts", "accounting://trial-balance"}

        accounts = await client.read_resource("accounting://accounts")
        accounts_block = accounts.contents[0]
        assert isinstance(accounts_block, TextResourceContents)
        accounts_text = accounts_block.text
        assert "1000" in accounts_text and "Cash" in accounts_text

        trial = await client.read_resource("accounting://trial-balance")
        trial_block = trial.contents[0]
        assert isinstance(trial_block, TextResourceContents)
        assert '"balanced"' in trial_block.text


@pytest.mark.anyio
async def test_prompts_listed_and_rendered(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        listed = await client.list_prompts()
        names = {prompt.name for prompt in listed.prompts}
        assert names == {"monthly_report", "tax_position", "cash_position"}

        rendered = await client.get_prompt(
            "monthly_report", {"month": "2026-03"}
        )
        content = rendered.messages[0].content
        assert isinstance(content, TextContent)
        assert "2026-03" in content.text
        assert "get_income_statement" in content.text


@pytest.mark.anyio
async def test_unknown_account_is_tool_error(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "get_account_ledger", {"account": "Nonexistent"}
        )
    assert result.is_error is True
    text = _text(result)
    assert "Nonexistent" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_invalid_status_is_tool_error(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        result = await client.call_tool("list_invoices", {"status": "bogus"})
    assert result.is_error is True
    text = _text(result)
    assert "Invalid status" in text
    assert "partially_paid" in text


@pytest.mark.anyio
async def test_write_tools_absent_by_default(mcp_server) -> None:
    async with Client(mcp_server, raise_exceptions=True) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert not (names & WRITE_TOOL_NAMES)


@pytest.mark.anyio
async def test_write_tools_present_when_enabled(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert WRITE_TOOL_NAMES <= names


@pytest.mark.anyio
async def test_create_journal_entry_balanced(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_journal_entry",
            {
                "date": "2026-09-01",
                "description": "Ad hoc rent payment",
                "lines": [
                    {"account": "5100", "debit_cents": 10000, "credit_cents": 0},
                    {"account": "Cash", "debit_cents": 0, "credit_cents": 10000},
                ],
            },
        )
        assert result.is_error is False
        body = result.structured_content
        assert body["entry_id"]
        assert body["description"] == "Ad hoc rent payment"
        assert len(body["lines"]) == 2

        trial = await client.call_tool("get_trial_balance", {})
        assert trial.structured_content["balanced"] is True

        found = await client.call_tool(
            "search_transactions", {"query": "Ad hoc rent"}
        )
        rows = _rows(found)
        assert len(rows) == 2
        assert {row["account_number"] for row in rows} == {"5100", "1000"}


@pytest.mark.anyio
async def test_create_journal_entry_unbalanced(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_journal_entry",
            {
                "date": "2026-09-01",
                "description": "Bad entry",
                "lines": [
                    {"account": "5100", "debit_cents": 10000, "credit_cents": 0},
                    {"account": "Cash", "debit_cents": 0, "credit_cents": 5000},
                ],
            },
        )
    assert result.is_error is True
    assert "does not balance" in _text(result)


@pytest.mark.anyio
async def test_create_invoice_unknown_customer(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_invoice",
            {
                "customer": "NoSuchCustomer",
                "issue_date": "2026-09-01",
                "lines": [
                    {"description": "Consulting", "quantity": 1, "unit_price_cents": 10000}
                ],
            },
        )
    assert result.is_error is True
    text = _text(result)
    assert "NoSuchCustomer" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_create_invoice_and_pay(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_invoice",
            {
                "customer": "Globex Inc",
                "issue_date": "2026-09-01",
                "lines": [
                    {"description": "Consulting", "quantity": 2, "unit_price_cents": 50000}
                ],
                "tax_rate": 8.0,
            },
        )
        assert created.is_error is False
        body = created.structured_content
        assert body["status"] == "open"
        assert body["subtotal_cents"] == 100000
        assert body["tax_cents"] == 8000
        assert body["total_cents"] == 108000

        paid = await client.call_tool(
            "pay_invoice",
            {
                "invoice_id": body["id"],
                "amount_cents": 108000,
                "method": "bank transfer",
            },
        )
    assert paid.is_error is False
    paid_body = paid.structured_content
    assert paid_body["status"] == "paid"
    assert paid_body["paid_cents"] == 108000
    assert paid_body["payments"][0]["note"] == "bank transfer"


@pytest.mark.anyio
async def test_pay_invoice_overpayment(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_invoice",
            {
                "customer": "Initech LLC",
                "issue_date": "2026-09-01",
                "lines": [
                    {"description": "Consulting", "quantity": 1, "unit_price_cents": 10000}
                ],
            },
        )
        invoice_id = created.structured_content["id"]
        result = await client.call_tool(
            "pay_invoice", {"invoice_id": invoice_id, "amount_cents": 999999}
        )
    assert result.is_error is True
    assert "exceeds" in _text(result)


@pytest.mark.anyio
async def test_void_invoice(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_invoice",
            {
                "customer": "Acme Corporation",
                "issue_date": "2026-09-01",
                "lines": [
                    {"description": "Consulting", "quantity": 1, "unit_price_cents": 10000}
                ],
            },
        )
        invoice_id = created.structured_content["id"]
        voided = await client.call_tool(
            "void_invoice", {"invoice_id": invoice_id}
        )
        assert voided.is_error is False
        assert voided.structured_content["status"] == "void"

        again = await client.call_tool(
            "void_invoice", {"invoice_id": invoice_id}
        )
    assert again.is_error is True
    assert "already voided" in _text(again)


@pytest.mark.anyio
async def test_create_bill(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_bill",
            {
                "vendor": "City Power & Light",
                "date": "2026-09-01",
                "lines": [
                    {
                        "description": "Electricity",
                        "quantity": 1,
                        "unit_price_cents": 45000,
                        "expense_account": "Utilities Expense",
                    }
                ],
            },
        )
    assert result.is_error is False
    body = result.structured_content
    assert body["status"] == "open"
    assert body["total_cents"] == 45000
    assert body["vendor_name"] == "City Power & Light"
    assert body["lines"][0]["expense_account_id"]


@pytest.mark.anyio
async def test_create_budget(write_server) -> None:
    start, end = _current_month_range()
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_budget",
            {
                "account": "5100",
                "budget_start": start,
                "budget_end": end,
                "amount_cents": 300000,
            },
        )
        assert result.is_error is False
        body = result.structured_content
        assert body["budget_cents"] == 300000
        assert body["account_name"] == "Rent Expense"

        report = await client.call_tool(
            "get_budget_report", {"start": start, "end": end}
        )
    rows = report.structured_content["rows"]
    rent_rows = [row for row in rows if row["account_number"] == "5100"]
    assert {row["budget_cents"] for row in rent_rows} == {200000, 300000}


@pytest.mark.anyio
async def test_create_customer_round_trip(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_customer",
            {"name": "Northwind Traders", "email": "ap@northwind.example"},
        )
        assert created.is_error is False
        body = created.structured_content
        assert body["name"] == "Northwind Traders"
        assert body["email"] == "ap@northwind.example"
        assert body["phone"] is None

        listed = _rows(await client.call_tool("list_customers", {}))
    assert any(row["id"] == body["id"] for row in listed)


@pytest.mark.anyio
async def test_create_vendor_round_trip(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_vendor", {"name": "Stark Industries"}
        )
        assert created.is_error is False
        body = created.structured_content
        assert body["name"] == "Stark Industries"

        listed = _rows(await client.call_tool("list_vendors", {}))
    assert any(row["id"] == body["id"] for row in listed)


@pytest.mark.anyio
async def test_create_item_round_trip(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_item",
            {
                "name": "SEO Audit",
                "description": "One-time SEO audit",
                "unit_price_cents": 75000,
            },
        )
        assert created.is_error is False
        body = created.structured_content
        assert body["unit_price_cents"] == 75000
        assert body["unit_price_cents_usd"] == "750.00"
        assert body["is_active"] is True

        listed = _rows(await client.call_tool("list_items", {}))
    assert any(row["id"] == body["id"] for row in listed)


@pytest.mark.anyio
async def test_update_item_partial_keeps_other_fields(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_items", {}))
        consulting = next(row for row in listed if row["name"] == "Consulting (day)")
        result = await client.call_tool(
            "update_item",
            {"item_id": consulting["id"], "unit_price_cents": 30000},
        )
    assert result.is_error is False
    body = result.structured_content
    assert body["unit_price_cents"] == 30000
    assert body["unit_price_cents_usd"] == "300.00"
    assert body["name"] == "Consulting (day)"
    assert body["description"] == "Consulting service, billed per day"


@pytest.mark.anyio
async def test_update_item_missing_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "update_item", {"item_id": 9999, "name": "Ghost"}
        )
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_deactivate_item_hides_from_default_list(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_items", {}))
        logo = next(row for row in listed if row["name"] == "Logo Design")
        result = await client.call_tool("deactivate_item", {"item_id": logo["id"]})
        assert result.is_error is False
        assert result.structured_content["is_active"] is False

        default_rows = _rows(await client.call_tool("list_items", {}))
        all_rows = _rows(
            await client.call_tool("list_items", {"include_inactive": True})
        )
    assert "Logo Design" not in {row["name"] for row in default_rows}
    assert "Logo Design" in {row["name"] for row in all_rows}


@pytest.mark.anyio
async def test_create_account_round_trip(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_account",
            {"number": "5800", "name": "Contractor Expense", "type": "expense"},
        )
        assert created.is_error is False
        body = created.structured_content
        assert body["number"] == "5800"
        assert body["name"] == "Contractor Expense"
        assert body["type"] == "expense"
        assert body["subtype"] is None
        assert body["is_system"] is False
        assert body["is_active"] is True

        listed = _rows(await client.call_tool("list_accounts", {}))
    assert any(row["number"] == "5800" for row in listed)


@pytest.mark.anyio
async def test_create_account_duplicate_number_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_account",
            {"number": "1000", "name": "Cash Two", "type": "asset"},
        )
    assert result.is_error is True
    text = _text(result)
    assert "1000" in text
    assert "already exists" in text.lower()


@pytest.mark.anyio
async def test_create_account_invalid_type_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_account",
            {"number": "5800", "name": "Contractor Expense", "type": "bogus"},
        )
    assert result.is_error is True
    text = _text(result)
    assert "Invalid type" in text
    assert "expense" in text


@pytest.mark.anyio
async def test_create_account_bad_number_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_account",
            {"number": "1A", "name": "Bad Number", "type": "expense"},
        )
    assert result.is_error is True
    assert "digit" in _text(result).lower()


@pytest.mark.anyio
async def test_update_account_partial_keeps_other_fields(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "update_account",
            {
                "account": "5400",
                "name": "Office Supplies",
                "description": "Pens, paper, toner",
            },
        )
    assert result.is_error is False
    body = result.structured_content
    assert body["name"] == "Office Supplies"
    assert body["description"] == "Pens, paper, toner"
    assert body["number"] == "5400"
    assert body["type"] == "expense"
    assert body["subtype"] == "supplies"


@pytest.mark.anyio
async def test_update_account_missing_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "update_account", {"account": "9999", "name": "Ghost"}
        )
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_deactivate_account_marks_inactive_in_list(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_account",
            {"number": "5800", "name": "Contractor Expense", "type": "expense"},
        )
        assert created.is_error is False
        result = await client.call_tool("deactivate_account", {"account": "5800"})
        assert result.is_error is False
        assert result.structured_content["is_active"] is False

        listed = _rows(await client.call_tool("list_accounts", {}))
    row = next(row for row in listed if row["number"] == "5800")
    assert row["active"] is False


@pytest.mark.anyio
async def test_deactivate_system_account_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("deactivate_account", {"account": "Cash"})
    assert result.is_error is True
    assert "system" in _text(result).lower()


@pytest.mark.anyio
async def test_deactivate_used_account_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("deactivate_account", {"account": "5100"})
    assert result.is_error is True
    assert "journal entries" in _text(result).lower()


@pytest.mark.anyio
async def test_void_bill(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_bills", {"status": "open"}))
        offimax = next(
            row for row in listed if row["vendor_name"] == "OfficeMax Supplies"
        )
        result = await client.call_tool("void_bill", {"bill_id": offimax["id"]})
        assert result.is_error is False
        body = result.structured_content
        assert body["is_voided"] is True
        assert body["status"] == "void"

        again = await client.call_tool("void_bill", {"bill_id": offimax["id"]})
    assert again.is_error is True
    assert "already voided" in _text(again)


@pytest.mark.anyio
async def test_void_bill_paid_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_bills", {"status": "paid"}))
        result = await client.call_tool("void_bill", {"bill_id": listed[0]["id"]})
    assert result.is_error is True
    assert "payments" in _text(result).lower()


@pytest.mark.anyio
async def test_void_bill_missing_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("void_bill", {"bill_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_create_estimate_round_trip(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_estimate",
            {
                "customer": "Acme Corporation",
                "date": "2026-09-01",
                "lines": [
                    {
                        "description": "Website Design",
                        "quantity": 1,
                        "unit_price_cents": 500000,
                    },
                    {
                        "description": "Consulting (day)",
                        "quantity": 10,
                        "unit_price_cents": 25000,
                    },
                ],
                "tax_rate": 8.0,
            },
        )
        assert created.is_error is False
        body = created.structured_content
        assert body["customer_name"] == "Acme Corporation"
        assert body["status"] == "open"
        assert body["subtotal_cents"] == 750000
        assert body["tax_cents"] == 60000
        assert body["total_cents"] == 810000
        assert body["total_cents_usd"] == "8100.00"
        assert body["converted_invoice_id"] is None

        listed = _rows(await client.call_tool("list_estimates", {}))
    assert any(row["id"] == body["id"] for row in listed)


@pytest.mark.anyio
async def test_create_estimate_unknown_customer(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_estimate",
            {
                "customer": "Ghost Corp",
                "date": "2026-09-01",
                "lines": [
                    {"description": "Consulting", "quantity": 1, "unit_price_cents": 10000}
                ],
            },
        )
    assert result.is_error is True
    text = _text(result)
    assert "Ghost Corp" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_convert_estimate(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_estimates", {}))
        estimate = next(
            row for row in listed if row["customer_name"] == "Globex Inc"
        )
        result = await client.call_tool(
            "convert_estimate", {"estimate_id": estimate["id"]}
        )
        assert result.is_error is False
        invoice = result.structured_content
        assert invoice["customer_name"] == "Globex Inc"
        assert invoice["status"] == "open"
        assert invoice["subtotal_cents"] == 750000
        assert invoice["total_cents"] == 750000
        assert len(invoice["lines"]) == 2

        est_listed = _rows(await client.call_tool("list_estimates", {}))
        est_row = next(row for row in est_listed if row["id"] == estimate["id"])
        assert est_row["status"] == "converted"
        assert est_row["converted_invoice_id"] == invoice["id"]

        inv_listed = _rows(await client.call_tool("list_invoices", {}))
        assert any(row["id"] == invoice["id"] for row in inv_listed)

        again = await client.call_tool(
            "convert_estimate", {"estimate_id": estimate["id"]}
        )
    assert again.is_error is True
    assert "already been converted" in _text(again).lower()


@pytest.mark.anyio
async def test_convert_estimate_missing_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("convert_estimate", {"estimate_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_update_budget(write_server) -> None:
    start, end = _current_month_range()
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_budgets", {"account": "5500"}))
        result = await client.call_tool(
            "update_budget",
            {
                "budget_id": listed[0]["id"],
                "amount_cents": 75000,
                "note": "Raised for Q4 campaign",
            },
        )
        assert result.is_error is False
        body = result.structured_content
        assert body["budget_cents"] == 75000
        assert body["budget_cents_usd"] == "750.00"
        assert body["note"] == "Raised for Q4 campaign"
        assert body["account_number"] == "5500"
        assert body["budget_start"] == start
        assert body["budget_end"] == end


@pytest.mark.anyio
async def test_update_budget_start_after_end(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_budgets", {"account": "5500"}))
        budget = listed[0]
        bad_start = (
            datetime.date.fromisoformat(budget["budget_end"])
            + datetime.timedelta(days=1)
        ).isoformat()
        result = await client.call_tool(
            "update_budget",
            {"budget_id": budget["id"], "budget_start": bad_start},
        )
    assert result.is_error is True
    assert "on or before" in _text(result)


@pytest.mark.anyio
async def test_update_budget_missing_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "update_budget", {"budget_id": 9999, "note": "nope"}
        )
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_delete_budget(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        listed = _rows(await client.call_tool("list_budgets", {"account": "5500"}))
        budget_id = listed[0]["id"]
        result = await client.call_tool("delete_budget", {"budget_id": budget_id})
        assert result.is_error is False
        assert result.structured_content == {"deleted": True, "budget_id": budget_id}

        remaining = _rows(await client.call_tool("list_budgets", {}))
        assert len(remaining) == 3
        assert all(row["id"] != budget_id for row in remaining)

        again = await client.call_tool("delete_budget", {"budget_id": budget_id})
    assert again.is_error is True
    assert "not found" in _text(again).lower()


@pytest.mark.anyio
async def test_delete_budget_missing_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("delete_budget", {"budget_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_create_reconciliation_balanced(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        bank, line_ids = await _current_month_cash(client)
        body = await _reconcile_current_month(client, bank, line_ids)
        assert body["account_number"] == "1000"
        assert body["statement_date"] == _current_month_range()[1]
        assert body["difference_cents"] == 0
        assert body["difference_cents_usd"] == "0.00"
        assert body["is_balanced"] is True
        assert body["line_count"] == len(line_ids)
        listed = _rows(await client.call_tool("list_reconciliations", {}))
        assert len(listed) == 2
        assert listed[0]["id"] == body["id"]


@pytest.mark.anyio
async def test_list_periods_empty(mcp_server) -> None:
    """No periods exist until a month is locked."""
    async with Client(mcp_server, raise_exceptions=True) as client:
        rows = _rows(await client.call_tool("list_periods", {}))
    assert rows == []


@pytest.mark.anyio
async def test_lock_period_and_list(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("lock_period", {"month": "2030-02"})
        assert result.is_error is False
        body = result.structured_content
        assert (body["year"], body["month"]) == (2030, 2)
        assert body["is_locked"] is True
        assert body["locked_at"] is not None

        # Idempotent re-lock returns the same period.
        again = await client.call_tool("lock_period", {"month": "2030-02"})
        assert again.structured_content["id"] == body["id"]

        rows = _rows(await client.call_tool("list_periods", {}))
    assert [(row["year"], row["month"]) for row in rows] == [(2030, 2)]


@pytest.mark.anyio
async def test_unlock_period_semantics(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        unknown = await client.call_tool("unlock_period", {"month": "2031-01"})
        assert unknown.is_error is True
        assert "not found" in _text(unknown).lower()

        await client.call_tool("lock_period", {"month": "2030-03"})
        unlocked = await client.call_tool("unlock_period", {"month": "2030-03"})
        assert unlocked.is_error is False
        assert unlocked.structured_content["is_locked"] is False
        assert unlocked.structured_content["locked_at"] is None

        again = await client.call_tool("unlock_period", {"month": "2030-03"})
    assert again.is_error is True
    assert "not locked" in _text(again)


@pytest.mark.anyio
async def test_lock_invalid_month_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("lock_period", {"month": "2026-13"})
    assert result.is_error is True
    assert "Invalid month" in _text(result)


@pytest.mark.anyio
async def test_locked_month_blocks_journal_entry(write_server) -> None:
    """The MCP write path honors the period guard (a tool error, not a crash)."""
    async with Client(write_server, raise_exceptions=True) as client:
        await client.call_tool("lock_period", {"month": _current_month()})
        result = await client.call_tool(
            "create_journal_entry",
            {
                "date": datetime.date.today().isoformat(),
                "description": "Blocked by lock",
                "lines": [
                    {"account": "5100", "debit_cents": 10000, "credit_cents": 0},
                    {"account": "1000", "debit_cents": 0, "credit_cents": 10000},
                ],
            },
        )
    assert result.is_error is True
    assert "locked" in _text(result)


@pytest.mark.anyio
async def test_create_reconciliation_not_a_bank_account(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        _, line_ids = await _current_month_cash(client)
        result = await client.call_tool(
            "create_reconciliation",
            {
                "account": "5100",
                "statement_date": _current_month_range()[1],
                "statement_balance_cents": 0,
                "line_ids": line_ids,
            },
        )
    assert result.is_error is True
    assert "not a bank account" in _text(result)


@pytest.mark.anyio
async def test_create_reconciliation_line_after_statement_date(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        _, line_ids = await _current_month_cash(client)
        result = await client.call_tool(
            "create_reconciliation",
            {
                "account": "1000",
                "statement_date": "2020-01-01",
                "statement_balance_cents": 0,
                "line_ids": line_ids,
            },
        )
    assert result.is_error is True
    assert "after the statement date" in _text(result)


@pytest.mark.anyio
async def test_create_reconciliation_already_cleared(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        bank, line_ids = await _current_month_cash(client)
        first = await _reconcile_current_month(client, bank, line_ids)
        again = await client.call_tool(
            "create_reconciliation",
            {
                "account": "1000",
                "statement_date": _current_month_range()[1],
                "statement_balance_cents": bank["balance_cents"],
                "line_ids": line_ids,
            },
        )
    assert first["is_balanced"] is True
    assert again.is_error is True
    assert "already cleared" in _text(again)


@pytest.mark.anyio
async def test_create_reconciliation_empty_line_ids(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_reconciliation",
            {
                "account": "1000",
                "statement_date": _current_month_range()[1],
                "statement_balance_cents": 0,
                "line_ids": [],
            },
        )
    assert result.is_error is True
    assert "at least one" in _text(result)


@pytest.mark.anyio
async def test_create_reconciliation_missing_line(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "create_reconciliation",
            {
                "account": "1000",
                "statement_date": _current_month_range()[1],
                "statement_balance_cents": 0,
                "line_ids": [99999],
            },
        )
    assert result.is_error is True
    text = _text(result)
    assert "99999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_delete_reconciliation(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        bank, line_ids = await _current_month_cash(client)
        body = await _reconcile_current_month(client, bank, line_ids)
        result = await client.call_tool(
            "delete_reconciliation", {"reconciliation_id": body["id"]}
        )
        assert result.is_error is False
        assert result.structured_content == {
            "deleted": True,
            "reconciliation_id": body["id"],
        }
        remaining = _rows(await client.call_tool("list_reconciliations", {}))
        assert len(remaining) == 1
        assert all(row["id"] != body["id"] for row in remaining)
        # The lines are un-cleared: the same lines reconcile again.
        again = await _reconcile_current_month(client, bank, line_ids)
    assert again["is_balanced"] is True


@pytest.mark.anyio
async def test_delete_reconciliation_missing_is_tool_error(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "delete_reconciliation", {"reconciliation_id": 9999}
        )
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_void_journal_entry(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        rent = await _current_month_rent(client)
        result = await client.call_tool(
            "void_journal_entry", {"entry_id": rent["id"]}
        )
        assert result.is_error is False
        reversal = result.structured_content
        # The tool returns the reversal entry, not the voided original.
        assert reversal["source_type"] == "void"
        assert reversal["source_id"] == rent["id"]
        assert reversal["description"] == "VOID: Monthly rent"
        assert reversal["date"] == datetime.date.today().isoformat()
        assert reversal["is_voided"] is False
        original = (
            await client.call_tool("get_journal_entry", {"entry_id": rent["id"]})
        ).structured_content
        assert original["is_voided"] is True
        assert original["voided_by_id"] == reversal["id"]
        # The reversal mirrors the original with debits and credits swapped.
        for rev_line, orig_line in zip(reversal["lines"], original["lines"]):
            assert rev_line["debit"] == orig_line["credit"]
            assert rev_line["credit"] == orig_line["debit"]


@pytest.mark.anyio
async def test_void_journal_entry_already_voided(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        rent = await _current_month_rent(client)
        first = await client.call_tool(
            "void_journal_entry", {"entry_id": rent["id"]}
        )
        assert first.is_error is False
        again = await client.call_tool(
            "void_journal_entry", {"entry_id": rent["id"]}
        )
    assert again.is_error is True
    assert "already voided" in _text(again)


@pytest.mark.anyio
async def test_void_journal_entry_cleared_lines(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        rows = _rows(await client.call_tool("list_journal_entries", {}))
        capital = next(
            row for row in rows if row["description"] == "Owner capital injection"
        )
        result = await client.call_tool(
            "void_journal_entry", {"entry_id": capital["id"]}
        )
    # Its cash line was cleared by the seeded reconciliation.
    assert result.is_error is True
    assert "cleared lines" in _text(result)


@pytest.mark.anyio
async def test_void_journal_entry_missing(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("void_journal_entry", {"entry_id": 9999})
    assert result.is_error is True
    text = _text(result)
    assert "9999" in text
    assert "not found" in text.lower()


@pytest.mark.anyio
async def test_list_journal_entries_include_voided(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        rent = await _current_month_rent(client)
        reversal = (
            await client.call_tool("void_journal_entry", {"entry_id": rent["id"]})
        ).structured_content
        hidden = _rows(
            await client.call_tool(
                "list_journal_entries", {"include_voided": False}
            )
        )
        shown = _rows(await client.call_tool("list_journal_entries", {}))
    hidden_ids = {row["id"] for row in hidden}
    assert rent["id"] not in hidden_ids
    assert reversal["id"] in hidden_ids  # the reversal itself is not voided
    shown_ids = {row["id"] for row in shown}
    assert rent["id"] in shown_ids
    assert reversal["id"] in shown_ids
    # include_voided=False hides exactly the voided entries (the demo
    # seed also voids one invoice's entry).
    voided_ids = {row["id"] for row in shown if row["is_voided"]}
    assert shown_ids - hidden_ids == voided_ids
    assert rent["id"] in voided_ids


@pytest.mark.anyio
async def test_seed_demo_data(empty_write_server) -> None:
    async with Client(empty_write_server, raise_exceptions=True) as client:
        result = await client.call_tool("seed_demo_data", {})
        assert result.is_error is False
        body = result.structured_content
        assert body["seeded"] is True
        assert body["login"] == {"username": "demo", "password": "demo123"}
        customers = _rows(await client.call_tool("list_customers", {}))
    assert len(customers) == 3  # the demo business really landed


@pytest.mark.anyio
async def test_seed_demo_data_already_present(write_server) -> None:
    async with Client(write_server, raise_exceptions=True) as client:
        result = await client.call_tool("seed_demo_data", {})
    assert result.is_error is False
    body = result.structured_content
    assert body["seeded"] is False
    assert "already present" in body["message"]
    assert "login" not in body


@pytest.mark.anyio
async def test_seed_demo_data_idempotent(empty_write_server) -> None:
    async with Client(empty_write_server, raise_exceptions=True) as client:
        first = await client.call_tool("seed_demo_data", {})
        assert first.is_error is False
        assert first.structured_content["seeded"] is True
        again = await client.call_tool("seed_demo_data", {})
        assert again.is_error is False
        assert again.structured_content["seeded"] is False
        customers = _rows(await client.call_tool("list_customers", {}))
    assert len(customers) == 3  # the second call created nothing new
