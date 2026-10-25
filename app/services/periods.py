"""Period locking service.

A :class:`~app.models.period.Period` is a calendar month that can be
locked. While locked, the single posting path, the void path, and bank
reconciliation all refuse to touch entries dated in that month
(409 ConflictError) — locking protects the books from human *and* AI
mistakes once the AI has full write access.

Locking is idempotent (re-locking a locked month is a no-op success,
which keeps AI callers simple). Unlocking is the controlled reopen:
it 404s for a month that was never locked and 409s for a month that
is not currently locked. Lock and unlock are ordinary committed writes,
so the centralized audit hook records them like anything else.
"""

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.period import Period
from app.services.errors import ConflictError, NotFoundError


def get_period(db: Session, *, year: int, month: int) -> Period | None:
    return db.scalar(
        select(Period).where(Period.year == year, Period.month == month)
    )


def list_periods(db: Session) -> list[Period]:
    return list(db.scalars(select(Period).order_by(Period.year, Period.month)))


def lock_period(db: Session, *, year: int, month: int) -> Period:
    """Lock a calendar month, creating the period row on first lock."""
    period = get_period(db, year=year, month=month)
    if period is None:
        period = Period(year=year, month=month)
        db.add(period)
    period.is_locked = True
    period.locked_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(period)
    return period


def unlock_period(db: Session, *, year: int, month: int) -> Period:
    """Unlock a previously locked calendar month (the controlled reopen)."""
    period = get_period(db, year=year, month=month)
    if period is None:
        raise NotFoundError(f"period {year:04d}-{month:02d} not found")
    if not period.is_locked:
        raise ConflictError(f"period {year:04d}-{month:02d} is not locked")
    period.is_locked = False
    period.locked_at = None
    db.commit()
    db.refresh(period)
    return period


def assert_period_open(db: Session, entry_date: datetime.date) -> None:
    """Raise 409 if the given date falls in a locked period.

    The single guard used by the posting path (``create_journal_entry``),
    the void path (``void_journal_entry``), and bank reconciliation
    (clearing and un-clearing lines). A no-op when nothing is locked,
    so existing behavior is unchanged until a month is actually locked.
    """
    period = get_period(db, year=entry_date.year, month=entry_date.month)
    if period is not None and period.is_locked:
        raise ConflictError(
            f"period {entry_date.year:04d}-{entry_date.month:02d} is locked; "
            "unlock it before making changes to that month"
        )
