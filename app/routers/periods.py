"""REST endpoints for period locking (calendar months).

Locking is an idempotent upsert (re-locking a locked month succeeds and
returns the same period); unlocking is the controlled reopen (404 for a
month that was never locked, 409 for one that is not currently locked).
Both are ordinary writes, so the audit trail records who locked and who
reopened.
"""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.period import PeriodRead
from app.services import periods as periods_service

router = APIRouter(
    prefix="/api/periods", tags=["periods"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[PeriodRead])
def list_periods(db: Session = Depends(get_db)):
    return periods_service.list_periods(db)


@router.post("/{year}/{month}/lock", response_model=PeriodRead, status_code=201)
def lock_period(
    year: int = Path(ge=1, le=9999),
    month: int = Path(ge=1, le=12),
    db: Session = Depends(get_db),
):
    return periods_service.lock_period(db, year=year, month=month)


@router.post("/{year}/{month}/unlock", response_model=PeriodRead)
def unlock_period(
    year: int = Path(ge=1, le=9999),
    month: int = Path(ge=1, le=12),
    db: Session = Depends(get_db),
):
    return periods_service.unlock_period(db, year=year, month=month)
