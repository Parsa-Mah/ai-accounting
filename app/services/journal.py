"""Journal service — the single posting path for the double-entry core.

Every financial event posts through :func:`create_journal_entry`, which is the
only way journal entries are created. This guarantees every entry balances
(sum of debits == sum of credits) and carries provenance.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.journal import JournalEntry, JournalLine
from app.schemas.journal import JournalLineCreate
from app.services.accounts import get_account
from app.services.errors import ConflictError, NotFoundError, ValidationError


def create_journal_entry(
    db: Session,
    *,
    date: date,
    description: str,
    lines: list[JournalLineCreate],
    source_type: str = "manual",
    source_id: int | None = None,
) -> JournalEntry:
    total_debit = 0
    total_credit = 0
    for line in lines:
        account = get_account(db, line.account_id)
        if not account.is_active:
            raise ConflictError(
                f"Account '{account.name}' is inactive and cannot be used"
            )
        total_debit += line.debit
        total_credit += line.credit

    if total_debit != total_credit:
        raise ValidationError(
            "journal entry does not balance "
            f"(debits {total_debit} != credits {total_credit})"
        )

    entry = JournalEntry(
        date=date,
        description=description,
        source_type=source_type,
        source_id=source_id,
    )
    for line in lines:
        entry.lines.append(
            JournalLine(
                account_id=line.account_id,
                description=line.description,
                debit=line.debit,
                credit=line.credit,
            )
        )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_journal_entry(db: Session, entry_id: int) -> JournalEntry:
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise NotFoundError(f"Journal entry {entry_id} not found")
    return entry


def list_journal_entries(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    include_voided: bool = True,
) -> list[JournalEntry]:
    stmt = select(JournalEntry)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.date <= date_to)
    if not include_voided:
        stmt = stmt.where(JournalEntry.is_voided.is_(False))
    if account_id is not None:
        stmt = stmt.where(JournalEntry.lines.any(JournalLine.account_id == account_id))
    stmt = stmt.order_by(JournalEntry.date, JournalEntry.id)
    return list(db.scalars(stmt))


def void_journal_entry(db: Session, entry_id: int) -> JournalEntry:
    entry = get_journal_entry(db, entry_id)
    if entry.is_voided:
        raise ConflictError("journal entry is already voided")

    reversal_lines = [
        JournalLineCreate(
            account_id=line.account_id,
            description=line.description,
            debit=line.credit,
            credit=line.debit,
        )
        for line in entry.lines
    ]
    reversal = create_journal_entry(
        db,
        date=date.today(),
        description=f"VOID: {entry.description}",
        lines=reversal_lines,
        source_type="void",
        source_id=entry.id,
    )
    entry.is_voided = True
    entry.voided_by_id = reversal.id
    db.commit()
    db.refresh(entry)
    return reversal
