"""Shared context for MCP tools: per-call sessions and resolution helpers.

Each tool call opens its own short-lived SQLAlchemy session (the MCP
protocol is stateless). Domain errors are converted to ToolError so the
model receives an ``is_error=True`` result it can read and recover from,
never a JSON-RPC error. Money results carry both integer cents and
formatted USD strings so small models can quote numbers correctly.
"""

import datetime
import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar, cast

from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.account import Account
from app.models.party import Customer, Vendor
from app.services import accounts as accounts_service
from app.services import parties
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.export import money

__all__ = [
    "get_session",
    "safe_tool",
    "resolve_account",
    "resolve_customer",
    "resolve_vendor",
    "parse_date",
    "parse_month",
    "check_choice",
    "with_usd",
]

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def get_session() -> Iterator[Session]:
    """One DB session per tool call: commit on success, close in finally.

    Services commit internally on success; the outer commit is a no-op
    safety net, and the rollback undoes partial work on failure.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def safe_tool(fn: F) -> F:
    """Wrap a tool so domain exceptions become ToolError (is_error=True).

    The model reads the message and can recover (list valid accounts,
    retry with a different id), so errors never escape as JSON-RPC
    errors. ToolError itself passes through untouched.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (NotFoundError, ConflictError, ValidationError) as exc:
            raise ToolError(str(exc)) from exc

    return cast(F, wrapper)


def resolve_account(db: Session, ref: str) -> Account:
    """Resolve an account reference: exact number, else case-insensitive name."""
    all_accounts = accounts_service.list_accounts(db, include_inactive=True)
    for account in all_accounts:
        if account.number == ref or account.name.lower() == ref.lower():
            return account
    valid = ", ".join(f"{a.number} {a.name}" for a in all_accounts)
    raise ToolError(f"Account '{ref}' not found. Valid accounts: {valid}")


def resolve_customer(db: Session, name: str) -> Customer:
    """Resolve a customer by case-insensitive name."""
    all_customers = parties.list_customers(db)
    for customer in all_customers:
        if customer.name.lower() == name.lower():
            return customer
    valid = ", ".join(c.name for c in all_customers)
    raise ToolError(f"Customer '{name}' not found. Valid customers: {valid}")


def resolve_vendor(db: Session, name: str) -> Vendor:
    """Resolve a vendor by case-insensitive name."""
    all_vendors = parties.list_vendors(db)
    for vendor in all_vendors:
        if vendor.name.lower() == name.lower():
            return vendor
    valid = ", ".join(v.name for v in all_vendors)
    raise ToolError(f"Vendor '{name}' not found. Valid vendors: {valid}")


def parse_date(value: str) -> datetime.date:
    """Parse an ISO date (YYYY-MM-DD); raise ToolError on bad input."""
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ToolError(
            f"Invalid date '{value}' — expected ISO format YYYY-MM-DD"
        ) from None


def parse_month(value: str) -> tuple[datetime.date, datetime.date]:
    """Parse a month (YYYY-MM) into (first_day, last_day) of that month."""
    parts = value.split("-")
    if len(parts) != 2:
        raise ToolError(
            f"Invalid month '{value}' — expected ISO format YYYY-MM"
        )
    try:
        year, month = int(parts[0]), int(parts[1])
        first = datetime.date(year, month, 1)
    except ValueError:
        raise ToolError(
            f"Invalid month '{value}' — expected ISO format YYYY-MM"
        ) from None
    if month == 12:
        last = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return first, last


def check_choice(value: str, valid: tuple[str, ...], label: str) -> None:
    """Raise ToolError naming the valid options when a choice is invalid."""
    if value not in valid:
        raise ToolError(f"Invalid {label} '{value}'. Valid: {', '.join(valid)}")


# Money keys that do not carry the ``_cents`` suffix but still hold
# integer cents in service results (statements, ledgers, search rows).
_MONEY_KEYS = frozenset(
    {
        "amount",
        "debit",
        "credit",
        "balance",
        "opening_balance",
        "closing_balance",
        "net_income",
        "total_revenue",
        "total_expenses",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "total_debit",
        "total_credit",
    }
)


def with_usd(value: Any) -> Any:
    """Add a formatted ``<key>_usd`` string beside every money integer key.

    Money keys are ``*_cents`` plus the known unsuffixed cents keys
    (``_MONEY_KEYS``). Recursive: walks dicts and lists so nested service
    results (lines, rows, totals) all get dual money fields.
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result[key] = with_usd(item)
            is_money = (
                key.endswith("_cents") or key in _MONEY_KEYS
            ) and isinstance(item, int) and not isinstance(item, bool)
            if is_money:
                result[f"{key}_usd"] = money(item)
        return result
    if isinstance(value, list):
        return [with_usd(item) for item in value]
    return value
