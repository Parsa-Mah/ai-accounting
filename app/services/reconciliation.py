"""Bank reconciliation service.

A reconciliation matches a bank statement (date + ending balance) against a
set of journal lines for a bank account (an account with ``bank_kind`` set).
The difference between the statement balance and the computed balance
(opening balance + cleared lines) represents outstanding items; zero means
a clean match. Cleared lines are locked to their reconciliation until it is
deleted, which un-clears them. Money is integer cents.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine
from app.models.reconciliation import Reconciliation
from app.services.accounts import get_account
from app.services.errors import ConflictError, NotFoundError, ValidationError


def list_bank_accounts(db: Session) -> list[dict]:
    """Bank accounts (``bank_kind`` set) with their current net balance."""
    accounts = db.scalars(
        select(Account)
        .where(Account.bank_kind.is_not(None))
        .order_by(Account.number)
    ).all()
    result = []
    for account in accounts:
        debit, credit = _line_totals(db, account.id)
        result.append(
            {
                "id": account.id,
                "number": account.number,
                "name": account.name,
                "bank_kind": account.bank_kind,
                "balance_cents": debit - credit,
            }
        )
    return result


def create_reconciliation(
    db: Session,
    *,
    account_id: int,
    statement_date: date,
    statement_balance_cents: int,
    line_ids: list[int],
    note: str | None = None,
) -> dict:
    account = get_account(db, account_id)
    if account.bank_kind is None:
        raise ValidationError(
            f"account '{account.name}' is not a bank account and cannot be reconciled"
        )

    lines = _fetch_lines(db, account_id, line_ids)
    entries = {}
    for line in lines:
        entry = db.get(JournalEntry, line.entry_id)
        if entry is None:
            raise NotFoundError(f"journal entry {line.entry_id} not found")
        entries[line.entry_id] = entry
    for line in lines:
        if entries[line.entry_id].date > statement_date:
            raise ValidationError(
                f"journal line {line.id} is dated {entries[line.entry_id].date}, "
                "after the statement date"
            )

    first_date = min(entry.date for entry in entries.values())
    opening = _net_before(db, account_id, first_date)
    cleared_total = sum(line.debit - line.credit for line in lines)
    difference = statement_balance_cents - (opening + cleared_total)

    recon = Reconciliation(
        account_id=account_id,
        statement_date=statement_date,
        statement_balance_cents=statement_balance_cents,
        opening_balance_cents=opening,
        cleared_total_cents=cleared_total,
        difference_cents=difference,
        note=note,
    )
    db.add(recon)
    db.flush()
    for line in lines:
        line.cleared = True
        line.reconciliation_id = recon.id
    db.commit()
    return get_reconciliation(db, recon.id)


def get_reconciliation(db: Session, reconciliation_id: int) -> dict:
    recon = db.get(Reconciliation, reconciliation_id)
    if recon is None:
        raise NotFoundError(f"reconciliation {reconciliation_id} not found")
    return _to_dict(recon)


def list_reconciliations(
    db: Session, *, account_id: int | None = None
) -> list[dict]:
    stmt = select(Reconciliation)
    if account_id is not None:
        stmt = stmt.where(Reconciliation.account_id == account_id)
    stmt = stmt.order_by(
        Reconciliation.statement_date.desc(), Reconciliation.id.desc()
    )
    return [_to_dict(recon) for recon in db.scalars(stmt)]


def delete_reconciliation(db: Session, reconciliation_id: int) -> None:
    """Un-clear the reconciliation's lines and remove the record."""
    recon = db.get(Reconciliation, reconciliation_id)
    if recon is None:
        raise NotFoundError(f"reconciliation {reconciliation_id} not found")
    for line in recon.lines:
        line.cleared = False
        line.reconciliation_id = None
    db.delete(recon)
    db.commit()


def _fetch_lines(
    db: Session, account_id: int, line_ids: list[int]
) -> list[JournalLine]:
    found = list(db.scalars(select(JournalLine).where(JournalLine.id.in_(line_ids))))
    by_id = {line.id: line for line in found}
    missing = [line_id for line_id in line_ids if line_id not in by_id]
    if missing:
        raise NotFoundError(f"journal line {missing[0]} not found")
    ordered = [by_id[line_id] for line_id in line_ids]
    for line in ordered:
        if line.account_id != account_id:
            raise ValidationError(
                f"journal line {line.id} belongs to a different account"
            )
        if line.cleared:
            raise ConflictError(f"journal line {line.id} is already cleared")
    return ordered


def _line_totals(db: Session, account_id: int) -> tuple[int, int]:
    stmt = select(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).where(JournalLine.account_id == account_id)
    debit, credit = db.execute(stmt).one()
    return int(debit), int(credit)


def _net_before(db: Session, account_id: int, before: date) -> int:
    """Net balance (debits - credits) of all activity strictly before a date."""
    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(
            JournalLine.account_id == account_id,
            JournalEntry.date < before,
        )
    )
    debit, credit = db.execute(stmt).one()
    return int(debit) - int(credit)


def _to_dict(recon: Reconciliation) -> dict:
    lines = [
        {
            "id": line.id,
            "date": line.entry.date,
            "description": line.description,
            "debit": line.debit,
            "credit": line.credit,
        }
        for line in sorted(recon.lines, key=lambda line: (line.entry.date, line.id))
    ]
    return {
        "id": recon.id,
        "account_id": recon.account_id,
        "account_number": recon.account_number,
        "account_name": recon.account_name,
        "statement_date": recon.statement_date,
        "statement_balance_cents": recon.statement_balance_cents,
        "opening_balance_cents": recon.opening_balance_cents,
        "cleared_total_cents": recon.cleared_total_cents,
        "difference_cents": recon.difference_cents,
        "is_balanced": recon.is_balanced,
        "note": recon.note,
        "created_at": recon.created_at,
        "line_count": len(lines),
        "lines": lines,
    }
