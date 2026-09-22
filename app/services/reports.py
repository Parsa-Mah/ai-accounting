"""Financial statements service — income statement and balance sheet.

Reads from journal lines grouped by account type. The single posting path
guarantees every entry balances, so the balance sheet identity
Assets = Liabilities + Equity holds by construction: with no closing
entries, all-time net income flows into the equity section.

Money is integer cents. Amounts are reported positive in the account type's
natural direction (assets/expenses debit-normal, the rest credit-normal).
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.journal import JournalEntry, JournalLine


def _account_amounts(
    db: Session,
    account_type: AccountType,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[int, tuple[int, int]]:
    """Per-account (debit, credit) totals for one account type."""
    stmt = (
        select(
            JournalLine.account_id,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(Account.type == account_type)
        .group_by(JournalLine.account_id)
    )
    if date_from is not None:
        stmt = stmt.where(JournalEntry.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.date <= date_to)
    return {
        account_id: (int(debit), int(credit))
        for account_id, debit, credit in db.execute(stmt)
    }


def _statement_rows(
    accounts: dict[int, Account],
    amounts: dict[int, tuple[int, int]],
    sign: int,
) -> list[dict]:
    """Rows with amounts positive in the natural direction (sign * net)."""
    rows = []
    for account_id, (debit, credit) in sorted(amounts.items()):
        amount = sign * (debit - credit)
        if amount == 0:
            continue
        account = accounts[account_id]
        rows.append(
            {
                "account_id": account.id,
                "number": account.number,
                "name": account.name,
                "amount": amount,
            }
        )
    return rows


def income_statement(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Income statement for a date range: revenue, expenses, net income."""
    accounts = {
        account.id: account
        for account in db.scalars(select(Account).order_by(Account.number))
    }

    revenue_amounts = _account_amounts(
        db, AccountType.REVENUE, date_from=date_from, date_to=date_to
    )
    expense_amounts = _account_amounts(
        db, AccountType.EXPENSE, date_from=date_from, date_to=date_to
    )

    revenue_rows = _statement_rows(accounts, revenue_amounts, sign=-1)
    expense_rows = _statement_rows(accounts, expense_amounts, sign=1)

    total_revenue = sum(row["amount"] for row in revenue_rows)
    total_expenses = sum(row["amount"] for row in expense_rows)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "revenue": revenue_rows,
        "total_revenue": total_revenue,
        "expenses": expense_rows,
        "total_expenses": total_expenses,
        "net_income": total_revenue - total_expenses,
    }


def balance_sheet(db: Session, *, as_of: date | None = None) -> dict:
    """Balance sheet as of a date: assets = liabilities + equity.

    Equity includes all-time unclosed net income (revenue - expenses
    through ``as_of``), since the app has no closing entries.
    """
    accounts = {
        account.id: account
        for account in db.scalars(select(Account).order_by(Account.number))
    }

    asset_rows = _statement_rows(
        accounts, _account_amounts(db, AccountType.ASSET, date_to=as_of), sign=1
    )
    liability_rows = _statement_rows(
        accounts, _account_amounts(db, AccountType.LIABILITY, date_to=as_of), sign=-1
    )
    equity_rows = _statement_rows(
        accounts, _account_amounts(db, AccountType.EQUITY, date_to=as_of), sign=-1
    )

    revenue_amounts = _account_amounts(db, AccountType.REVENUE, date_to=as_of)
    expense_amounts = _account_amounts(db, AccountType.EXPENSE, date_to=as_of)
    net_income = sum(
        credit - debit for debit, credit in revenue_amounts.values()
    ) - sum(debit - credit for debit, credit in expense_amounts.values())
    if net_income != 0:
        equity_rows.append(
            {
                "account_id": None,
                "number": "",
                "name": "Net Income (unclosed)",
                "amount": net_income,
            }
        )

    total_assets = sum(row["amount"] for row in asset_rows)
    total_liabilities = sum(row["amount"] for row in liability_rows)
    total_equity = sum(row["amount"] for row in equity_rows)

    return {
        "as_of": as_of,
        "assets": asset_rows,
        "total_assets": total_assets,
        "liabilities": liability_rows,
        "total_liabilities": total_liabilities,
        "equity": equity_rows,
        "total_equity": total_equity,
        "balanced": total_assets == total_liabilities + total_equity,
    }
