"""In-memory MCP client tests (Python SDK v2 pattern, anyio/asyncio).

The client talks to the server in-process (no subprocess, no port).
``raise_exceptions=True`` surfaces failures outside tool bodies with the
real message; tool errors still come back as ``is_error=True`` results.

Demo-seed expectations (relative to the current month): 5 invoices
(paid, partially_paid, open, void, paid), 4 bills (2 paid, 2 open),
1 open estimate, 4 budgets (3 current-month, 1 previous-month),
2x "Monthly rent" entries, 1 balanced Cash reconciliation.
"""

import datetime

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


WRITE_TOOL_NAMES = {
    "create_journal_entry",
    "create_invoice",
    "pay_invoice",
    "void_invoice",
    "create_bill",
    "pay_bill",
    "create_budget",
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
