"""Ledger service — account balances, general ledger, and trial balance.

Reads from journal lines. The single posting path guarantees every entry
balances, so balances are internally consistent. Voided entries are offset
by their reversing entries, so no filtering is needed for balance math.

Money is integer cents. Net balances are debit-positive (debits - credits).
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine
from app.services.accounts import get_account


def _line_totals(
    db: Session,
    account_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_before: date | None = None,
) -> tuple[int, int]:
    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account_id)
    )
    if date_from is not None:
        stmt = stmt.where(JournalEntry.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.date <= date_to)
    if date_before is not None:
        stmt = stmt.where(JournalEntry.date < date_before)
    debit, credit = db.execute(stmt).one()
    return int(debit), int(credit)


def account_balance(
    db: Session,
    account_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> int:
    """Net balance in cents (debits - credits) for one account."""
    get_account(db, account_id)
    debit, credit = _line_totals(
        db, account_id, date_from=date_from, date_to=date_to
    )
    return debit - credit


def general_ledger(
    db: Session,
    account_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    include_voided: bool = True,
) -> dict:
    """General ledger for one account: lines with a running balance.

    The running balance starts from the account's opening balance (all
    activity before ``date_from``). With ``include_voided=False``, voided
    entries and their reversing entries are hidden together (the pair nets
    to zero), so the running balance stays accurate.
    """
    account = get_account(db, account_id)

    if date_from is not None:
        opening_debit, opening_credit = _line_totals(
            db, account_id, date_before=date_from
        )
        opening = opening_debit - opening_credit
    else:
        opening = 0
    running = opening

    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account_id)
    )
    if date_from is not None:
        stmt = stmt.where(JournalEntry.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.date <= date_to)
    if not include_voided:
        stmt = stmt.where(JournalEntry.is_voided.is_(False))
    stmt = stmt.order_by(JournalEntry.date, JournalEntry.id, JournalLine.id)

    voided_ids: set[int] = set()
    if not include_voided:
        voided_ids = set(
            db.scalars(
                select(JournalEntry.id)
                .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
                .where(
                    JournalLine.account_id == account_id,
                    JournalEntry.is_voided.is_(True),
                )
            )
        )

    lines = []
    for line, entry in db.execute(stmt):
        if (
            not include_voided
            and entry.source_type == "void"
            and entry.source_id in voided_ids
        ):
            continue
        running += line.debit - line.credit
        lines.append(
            {
                "date": entry.date,
                "entry_id": entry.id,
                "entry_description": entry.description,
                "line_description": line.description,
                "debit": line.debit,
                "credit": line.credit,
                "balance": running,
                "is_voided": entry.is_voided,
                "cleared": line.cleared,
                "reconciliation_id": line.reconciliation_id,
            }
        )

    return {
        "account_id": account.id,
        "account_number": account.number,
        "account_name": account.name,
        "account_type": account.type.value,
        "opening_balance": opening,
        "lines": lines,
        "closing_balance": running,
    }


def trial_balance(db: Session, *, as_of: date | None = None) -> dict:
    """Trial balance: per-account debit/credit totals as of a date.

    Each account's net balance is shown in its natural column (positive
    net = debit column, negative net = credit column). The two columns
    must total equally because every entry balances.
    """
    stmt = (
        select(
            JournalLine.account_id,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .group_by(JournalLine.account_id)
    )
    if as_of is not None:
        stmt = stmt.where(JournalEntry.date <= as_of)

    totals_by_account = {
        account_id: (int(debit), int(credit))
        for account_id, debit, credit in db.execute(stmt)
    }

    rows = []
    total_debit = 0
    total_credit = 0
    for account in db.scalars(select(Account).order_by(Account.number)):
        if account.id not in totals_by_account:
            continue
        debit, credit = totals_by_account[account.id]
        net = debit - credit
        if net == 0:
            continue
        row = {
            "account_id": account.id,
            "number": account.number,
            "name": account.name,
            "type": account.type.value,
        }
        if net > 0:
            row["debit"] = net
            row["credit"] = 0
            total_debit += net
        else:
            row["debit"] = 0
            row["credit"] = -net
            total_credit += -net
        rows.append(row)

    return {
        "as_of": as_of,
        "rows": rows,
        "totals": {"debit": total_debit, "credit": total_credit},
        "balanced": total_debit == total_credit,
    }
