"""MCP tools: curated, intent-oriented wrappers over the domain services.

Docstrings are the LLM's only guidance: each states what the tool does,
when to use it, and an example question. Money results carry both integer
cents and formatted USD strings (see ``context.with_usd``).
"""

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.orm import Session

from app.mcp import context
from app.schemas.bill import BillLineCreate, BillRead
from app.schemas.budget import BudgetCreate
from app.schemas.estimate import EstimateRead
from app.schemas.invoice import InvoiceLineCreate, InvoiceRead
from app.schemas.journal import JournalLineCreate
from app.services import accounts
from app.services import budgets as budgets_service
from app.services import bills as bills_service
from app.services import estimates as estimates_service
from app.services import invoices as invoices_service
from app.services import journal as journal_service
from app.services import ledger
from app.services import reconciliation as reconciliation_service
from app.services import reports

INVOICE_STATUSES = ("open", "partially_paid", "paid", "void")
BILL_STATUSES = ("open", "partially_paid", "paid", "void")
ESTIMATE_STATUSES = ("open", "converted")


@context.safe_tool
def list_accounts() -> list[dict[str, Any]]:
    """List the chart of accounts: number, name, type, subtype, active.

    Use to discover valid account references before calling other tools,
    or to answer questions like 'what accounts do we have?'.
    """
    with context.get_session() as db:
        return context.with_usd(
            [
                {
                    "number": account.number,
                    "name": account.name,
                    "type": account.type.value,
                    "subtype": account.subtype,
                    "is_system": account.is_system,
                    "active": account.is_active,
                }
                for account in accounts.list_accounts(db, include_inactive=True)
            ]
        )


@context.safe_tool
def get_income_statement(month: str | None = None) -> dict[str, Any]:
    """Income statement for a month: revenue, expenses, net income.

    ``month`` is 'YYYY-MM' (e.g. '2026-03'); omit it for the all-time
    statement. Use for questions like 'how much did we earn in March?'
    or 'what was our net income?'.
    """
    date_from, date_to = (
        context.parse_month(month) if month is not None else (None, None)
    )
    with context.get_session() as db:
        return context.with_usd(
            reports.income_statement(db, date_from=date_from, date_to=date_to)
        )


@context.safe_tool
def get_balance_sheet(as_of: str | None = None) -> dict[str, Any]:
    """Balance sheet as of a date: assets, liabilities, equity.

    ``as_of`` is 'YYYY-MM-DD'; omit it for the current position. Use for
    questions like 'what is our net worth?' or 'how much do we owe?'.
    The result's 'balanced' flag confirms assets = liabilities + equity.
    """
    with context.get_session() as db:
        return context.with_usd(
            reports.balance_sheet(
                db, as_of=context.parse_date(as_of) if as_of is not None else None
            )
        )


@context.safe_tool
def get_trial_balance(as_of: str | None = None) -> dict[str, Any]:
    """Trial balance: per-account debit/credit totals as of a date.

    ``as_of`` is 'YYYY-MM-DD'; omit it for the current totals. Use to
    check that the books balance (debits = credits) or to see an
    account's net position.
    """
    with context.get_session() as db:
        return context.with_usd(
            ledger.trial_balance(
                db, as_of=context.parse_date(as_of) if as_of is not None else None
            )
        )


@context.safe_tool
def get_account_ledger(
    account: str,
    date_from: str | None = None,
    date_to: str | None = None,
    include_voided: bool = False,
) -> dict[str, Any]:
    """General ledger for one account: every line with a running balance.

    ``account`` is a number ('1000') or name ('Cash'). ``date_from`` /
    ``date_to`` are 'YYYY-MM-DD' and optional. Use for questions like
    'what is our cash balance?' or 'what went into the rent account?'.
    """
    with context.get_session() as db:
        account_obj = context.resolve_account(db, account)
        return context.with_usd(
            ledger.general_ledger(
                db,
                account_obj.id,
                date_from=context.parse_date(date_from) if date_from is not None else None,
                date_to=context.parse_date(date_to) if date_to is not None else None,
                include_voided=include_voided,
            )
        )


@context.safe_tool
def search_transactions(
    query: str | None = None,
    account: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search journal activity by free text, account, and date range.

    ``query`` matches entry or line descriptions (e.g. 'rent',
    'invoice 7'). ``account`` is a number or name. Dates are
    'YYYY-MM-DD'. Newest first. Use for questions like 'what was
    March's payroll?' or 'show me everything that touched Cash'.
    """
    with context.get_session() as db:
        account_id = (
            context.resolve_account(db, account).id if account is not None else None
        )
        rows = ledger.search_transactions(
            db,
            query=query,
            account_id=account_id,
            date_from=context.parse_date(date_from) if date_from is not None else None,
            date_to=context.parse_date(date_to) if date_to is not None else None,
            limit=limit,
        )
    return context.with_usd(rows)


@context.safe_tool
def list_invoices(
    status: str | None = None,
    month: str | None = None,
) -> list[dict[str, Any]]:
    """List invoices, newest first.

    ``status`` filters by 'open', 'partially_paid', 'paid', or 'void'.
    ``month`` filters by issue date ('YYYY-MM'). Use for questions like
    'which invoices are outstanding?' or 'how much did we bill in
    March?'. Call get_invoice for line detail.
    """
    with context.get_session() as db:
        invoices = invoices_service.list_invoices(db)
        if status is not None:
            context.check_choice(status, INVOICE_STATUSES, "status")
            invoices = [invoice for invoice in invoices if invoice.status == status]
        if month is not None:
            first, last = context.parse_month(month)
            invoices = [invoice for invoice in invoices if first <= invoice.date <= last]
        return [
            context.with_usd(
                InvoiceRead.model_validate(invoice).model_dump(mode="json")
            )
            for invoice in invoices
        ]


@context.safe_tool
def get_invoice(invoice_id: int) -> dict[str, Any]:
    """Full detail for one invoice: lines, payments, status, totals.

    Use after list_invoices to inspect a specific invoice, e.g. 'what
    did we bill Acme for?'.
    """
    with context.get_session() as db:
        invoice = invoices_service.get_invoice(db, invoice_id)
        return context.with_usd(
            InvoiceRead.model_validate(invoice).model_dump(mode="json")
        )


@context.safe_tool
def list_bills(
    status: str | None = None,
    month: str | None = None,
) -> list[dict[str, Any]]:
    """List bills (accounts payable), newest first.

    ``status`` filters by 'open', 'partially_paid', 'paid', or 'void'.
    ``month`` filters by bill date ('YYYY-MM'). Use for questions like
    'what do we still owe vendors?'.
    """
    with context.get_session() as db:
        bills = bills_service.list_bills(db)
        if status is not None:
            context.check_choice(status, BILL_STATUSES, "status")
            bills = [bill for bill in bills if bill.status == status]
        if month is not None:
            first, last = context.parse_month(month)
            bills = [bill for bill in bills if first <= bill.date <= last]
        return [
            context.with_usd(BillRead.model_validate(bill).model_dump(mode="json"))
            for bill in bills
        ]


@context.safe_tool
def list_estimates(status: str | None = None) -> list[dict[str, Any]]:
    """List estimates (quotes), newest first.

    ``status`` filters by 'open' or 'converted'. Use for questions like
    'what quotes are outstanding?'.
    """
    with context.get_session() as db:
        estimates = estimates_service.list_estimates(db)
        if status is not None:
            context.check_choice(status, ESTIMATE_STATUSES, "status")
            estimates = [estimate for estimate in estimates if estimate.status == status]
        return [
            context.with_usd(
                EstimateRead.model_validate(estimate).model_dump(mode="json")
            )
            for estimate in estimates
        ]


@context.safe_tool
def get_budget_report(start: str, end: str) -> dict[str, Any]:
    """Budget vs actual for budgets fully contained in [start, end].

    Dates are 'YYYY-MM-DD'. Each row compares a budget to the account's
    actual activity over the budget's own range; positive variance means
    under budget. Use for 'are we over budget on rent this month?'.
    """
    with context.get_session() as db:
        return context.with_usd(
            budgets_service.budget_report(
                db, start=context.parse_date(start), end=context.parse_date(end)
            )
        )


@context.safe_tool
def list_reconciliations() -> list[dict[str, Any]]:
    """List bank reconciliations, newest first.

    Each has the statement date/balance, the computed opening + cleared
    totals, and the difference (zero = balanced). Use for 'is the bank
    account reconciled?' or 'what is outstanding at the bank?'.
    """
    with context.get_session() as db:
        return context.with_usd(reconciliation_service.list_reconciliations(db))


# --- Write tools (registered only when MCP_ALLOW_WRITE=1) --------------


def _journal_lines(db: Session, raw_lines: list[dict[str, Any]]) -> list[JournalLineCreate]:
    """Validate raw tool lines and resolve account references."""
    lines: list[JournalLineCreate] = []
    for index, raw in enumerate(raw_lines, start=1):
        account_ref = raw.get("account")
        debit = raw.get("debit_cents", 0)
        credit = raw.get("credit_cents", 0)
        if not isinstance(account_ref, str) or not account_ref:
            raise ToolError(f"line {index}: 'account' (number or name) is required")
        if not isinstance(debit, int) or not isinstance(credit, int) or debit < 0 or credit < 0:
            raise ToolError(
                f"line {index}: 'debit_cents' and 'credit_cents' must be "
                "non-negative integers"
            )
        if (debit > 0) == (credit > 0):
            raise ToolError(
                f"line {index}: exactly one of debit_cents/credit_cents "
                "must be positive"
            )
        description = raw.get("description")
        account = context.resolve_account(db, account_ref)
        lines.append(
            JournalLineCreate(
                account_id=account.id,
                description=description if isinstance(description, str) else None,
                debit=debit,
                credit=credit,
            )
        )
    if not lines:
        raise ToolError("at least one line is required")
    return lines


def _invoice_lines(raw_lines: list[dict[str, Any]]) -> list[InvoiceLineCreate]:
    """Validate raw invoice/bill line dicts."""
    lines: list[InvoiceLineCreate] = []
    for index, raw in enumerate(raw_lines, start=1):
        description = raw.get("description")
        quantity = raw.get("quantity", 1)
        unit_price_cents = raw.get("unit_price_cents", 0)
        if not isinstance(description, str) or not description:
            raise ToolError(f"line {index}: 'description' is required")
        if not isinstance(quantity, int) or quantity < 1:
            raise ToolError(f"line {index}: 'quantity' must be an integer >= 1")
        if not isinstance(unit_price_cents, int) or unit_price_cents < 0:
            raise ToolError(
                f"line {index}: 'unit_price_cents' must be an integer >= 0"
            )
        lines.append(
            InvoiceLineCreate(
                description=description,
                quantity=quantity,
                unit_price_cents=unit_price_cents,
            )
        )
    if not lines:
        raise ToolError("at least one line is required")
    return lines


def _bill_lines(db: Session, raw_lines: list[dict[str, Any]]) -> list[BillLineCreate]:
    """Validate raw bill line dicts and resolve per-line expense accounts."""
    lines: list[BillLineCreate] = []
    for index, raw in enumerate(raw_lines, start=1):
        description = raw.get("description")
        quantity = raw.get("quantity", 1)
        unit_price_cents = raw.get("unit_price_cents", 0)
        expense_ref = raw.get("expense_account")
        if not isinstance(description, str) or not description:
            raise ToolError(f"line {index}: 'description' is required")
        if not isinstance(quantity, int) or quantity < 1:
            raise ToolError(f"line {index}: 'quantity' must be an integer >= 1")
        if not isinstance(unit_price_cents, int) or unit_price_cents < 0:
            raise ToolError(
                f"line {index}: 'unit_price_cents' must be an integer >= 0"
            )
        if not isinstance(expense_ref, str) or not expense_ref:
            raise ToolError(
                f"line {index}: 'expense_account' (number or name) is required"
            )
        account = context.resolve_account(db, expense_ref)
        lines.append(
            BillLineCreate(
                description=description,
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                expense_account_id=account.id,
            )
        )
    if not lines:
        raise ToolError("at least one line is required")
    return lines


@context.safe_tool
def create_journal_entry(
    date: str,
    description: str,
    lines: list[dict[str, Any]],
) -> dict[str, Any]:
    """Record a manual journal entry. The entry must balance (debits = credits).

    ``date`` is 'YYYY-MM-DD'. Each line is an object
    {"account": "1000" or "Cash", "debit_cents": int, "credit_cents": int}
    with exactly one of debit_cents/credit_cents positive. Use for
    transactions no other tool covers, e.g. 'record $500 cash paid for
    office coffee on 2026-09-01'.
    """
    with context.get_session() as db:
        entry = journal_service.create_journal_entry(
            db,
            date=context.parse_date(date),
            description=description,
            lines=_journal_lines(db, lines),
        )
        return context.with_usd(
            {
                "entry_id": entry.id,
                "date": entry.date,
                "description": entry.description,
                "lines": [
                    {
                        "account_id": line.account_id,
                        "description": line.description,
                        "debit_cents": line.debit,
                        "credit_cents": line.credit,
                    }
                    for line in entry.lines
                ],
            }
        )


@context.safe_tool
def create_invoice(
    customer: str,
    issue_date: str,
    lines: list[dict[str, Any]],
    tax_rate: float = 0.0,
    due_date: str | None = None,
) -> dict[str, Any]:
    """Create an invoice for a customer and post it to the ledger.

    ``customer`` is a customer name. ``issue_date`` is 'YYYY-MM-DD';
    ``due_date`` optional; ``tax_rate`` is a percent (e.g. 8.0). Each
    line is {"description": str, "quantity": int, "unit_price_cents": int}.
    Use for 'invoice Acme for 5 days of consulting at $250/day'.
    """
    with context.get_session() as db:
        customer_obj = context.resolve_customer(db, customer)
        invoice = invoices_service.create_invoice(
            db,
            customer_id=customer_obj.id,
            date=context.parse_date(issue_date),
            due_date=context.parse_date(due_date) if due_date is not None else None,
            tax_rate=tax_rate,
            lines=_invoice_lines(lines),
        )
        return context.with_usd(
            InvoiceRead.model_validate(invoice).model_dump(mode="json")
        )


@context.safe_tool
def pay_invoice(
    invoice_id: int,
    amount_cents: int,
    date: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    """Record a payment against an invoice (partial or full).

    ``amount_cents`` must not exceed the invoice's remaining balance.
    ``date`` is 'YYYY-MM-DD' (defaults to today); ``method`` (e.g.
    'cash', 'bank transfer') is stored as the payment note. Returns the
    updated invoice. Use for 'Acme paid $1,000 toward invoice 3'.
    """
    with context.get_session() as db:
        invoices_service.pay_invoice(
            db,
            invoice_id,
            amount_cents=amount_cents,
            date=context.parse_date(date) if date is not None else None,
            note=method,
        )
        invoice = invoices_service.get_invoice(db, invoice_id)
        return context.with_usd(
            InvoiceRead.model_validate(invoice).model_dump(mode="json")
        )


@context.safe_tool
def void_invoice(invoice_id: int) -> dict[str, Any]:
    """Void an invoice (only while it has no payments).

    Posts a reversing journal entry; the invoice is flagged void and its
    history is never deleted. Returns the updated invoice. Use for
    'void invoice 4, it was entered in error'.
    """
    with context.get_session() as db:
        invoice = invoices_service.void_invoice(db, invoice_id)
        return context.with_usd(
            InvoiceRead.model_validate(invoice).model_dump(mode="json")
        )


@context.safe_tool
def create_bill(
    vendor: str,
    date: str,
    lines: list[dict[str, Any]],
    tax_rate: float = 0.0,
    due_date: str | None = None,
) -> dict[str, Any]:
    """Record a bill (accounts payable) from a vendor and post it.

    ``vendor`` is a vendor name; ``date`` is 'YYYY-MM-DD'; ``due_date``
    optional; ``tax_rate`` a percent. Each line is
    {"description": str, "quantity": int, "unit_price_cents": int,
    "expense_account": "5100" or "Rent Expense"} — an expense account is
    required per line. Use for 'record a $450 electricity bill from
    City Power & Light'.
    """
    with context.get_session() as db:
        vendor_obj = context.resolve_vendor(db, vendor)
        bill = bills_service.create_bill(
            db,
            vendor_id=vendor_obj.id,
            date=context.parse_date(date),
            due_date=context.parse_date(due_date) if due_date is not None else None,
            tax_rate=tax_rate,
            lines=_bill_lines(db, lines),
        )
        return context.with_usd(BillRead.model_validate(bill).model_dump(mode="json"))


@context.safe_tool
def pay_bill(
    bill_id: int,
    amount_cents: int,
    date: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    """Record a payment against a bill (partial or full).

    ``amount_cents`` must not exceed the bill's remaining balance.
    ``date`` is 'YYYY-MM-DD' (defaults to today); ``method`` (e.g.
    'check', 'bank transfer') is stored as the payment note. Returns the
    updated bill. Use for 'pay the CloudHost hosting bill in full'.
    """
    with context.get_session() as db:
        bills_service.pay_bill(
            db,
            bill_id,
            amount_cents=amount_cents,
            date=context.parse_date(date) if date is not None else None,
            note=method,
        )
        bill = bills_service.get_bill(db, bill_id)
        return context.with_usd(BillRead.model_validate(bill).model_dump(mode="json"))


@context.safe_tool
def create_budget(
    account: str,
    budget_start: str,
    budget_end: str,
    amount_cents: int,
) -> dict[str, Any]:
    """Create a budget: a planned amount for an account over a date range.

    ``account`` is a number or name; dates are 'YYYY-MM-DD' with
    budget_start on or before budget_end. Budgets post nothing to the
    ledger. Use for 'budget $2,000 for rent in September'.
    """
    with context.get_session() as db:
        account_obj = context.resolve_account(db, account)
        budget = budgets_service.create_budget(
            db,
            BudgetCreate(
                account_id=account_obj.id,
                budget_start=context.parse_date(budget_start),
                budget_end=context.parse_date(budget_end),
                budget_cents=amount_cents,
            ),
        )
        return context.with_usd(
            {
                "budget_id": budget.id,
                "account_number": budget.account.number,
                "account_name": budget.account.name,
                "budget_start": budget.budget_start,
                "budget_end": budget.budget_end,
                "budget_cents": budget.budget_cents,
            }
        )


# --- Resources ---------------------------------------------------------


def accounts_resource() -> dict[str, Any]:
    """Full chart of accounts as standing context for the model."""
    with context.get_session() as db:
        return {
            "accounts": [
                {
                    "number": account.number,
                    "name": account.name,
                    "type": account.type.value,
                    "subtype": account.subtype,
                }
                for account in accounts.list_accounts(db, include_inactive=True)
            ]
        }


def trial_balance_resource() -> dict[str, Any]:
    """Current trial balance as standing context for the model."""
    with context.get_session() as db:
        return ledger.trial_balance(db)


# --- Prompts -----------------------------------------------------------


def monthly_report(month: str) -> str:
    """Monthly close summary for a month ('YYYY-MM').

    Pulls the income statement, Cash ledger, and budget report for the
    month and produces a plain-English summary.
    """
    return (
        f"Produce a plain-English monthly close summary for {month}.\n\n"
        f"1. Call get_income_statement with month='{month}' — report revenue, "
        "expenses, and net income in dollars (use the *_usd fields).\n"
        f"2. Call get_account_ledger with account='Cash' and date_from/date_to "
        f"covering {month} — summarize the cash movement.\n"
        f"3. Call get_budget_report for {month} — flag any budget over plan.\n\n"
        "Keep it under 200 words and quote exact dollar amounts."
    )


def tax_position() -> str:
    """Net tax owed: taxes payable vs tax recoverable, in plain English."""
    return (
        "Determine the net tax position.\n\n"
        "1. Call get_account_ledger with account='2200' (Taxes Payable) — the "
        "closing balance is tax owed to the government.\n"
        "2. Call get_account_ledger with account='2210' (Tax Recoverable) — "
        "the closing balance is tax we can reclaim.\n"
        "3. Compute net = payable - recoverable and explain in plain English "
        "whether we owe tax or are owed a refund, quoting dollar amounts."
    )


def cash_position() -> str:
    """Cash on hand vs the last bank statement, in plain English."""
    return (
        "Summarize the cash position.\n\n"
        "1. Call get_account_ledger with account='Cash' — report the closing "
        "balance.\n"
        "2. Call list_reconciliations — find the most recent reconciliation "
        "and report its statement date, balance, and difference (outstanding "
        "items).\n"
        "3. Explain in plain English how the current cash balance compares to "
        "the last bank statement."
    )


def read_tools() -> list[Callable[..., Any]]:
    """Read tools, always registered."""
    return [
        list_accounts,
        get_income_statement,
        get_balance_sheet,
        get_trial_balance,
        get_account_ledger,
        search_transactions,
        list_invoices,
        get_invoice,
        list_bills,
        list_estimates,
        get_budget_report,
        list_reconciliations,
    ]


def write_tools() -> list[Callable[..., Any]]:
    """Write tools, registered only when MCP_ALLOW_WRITE=1."""
    return [
        create_journal_entry,
        create_invoice,
        pay_invoice,
        void_invoice,
        create_bill,
        pay_bill,
        create_budget,
    ]


def resources() -> list[tuple[str, str, str, Callable[..., Any]]]:
    """Resources, always registered: (uri, name, description, function)."""
    return [
        (
            "accounting://accounts",
            "accounts",
            "Full chart of accounts: number, name, type, subtype.",
            accounts_resource,
        ),
        (
            "accounting://trial-balance",
            "trial-balance",
            "Current trial balance: per-account debit/credit totals.",
            trial_balance_resource,
        ),
    ]


def prompts() -> list[Callable[..., Any]]:
    """Prompts, always registered."""
    return [monthly_report, tax_position, cash_position]
