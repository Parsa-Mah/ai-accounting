"""REST endpoints for the journal (double-entry core)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryRead,
)
from app.services import journal as journal_service

router = APIRouter(
    prefix="/api/journal", tags=["journal"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=JournalEntryRead, status_code=201)
def create_journal_entry(payload: JournalEntryCreate, db: Session = Depends(get_db)):
    return journal_service.create_journal_entry(
        db,
        date=payload.date,
        description=payload.description,
        lines=payload.lines,
    )


@router.get("", response_model=list[JournalEntryRead])
def list_journal_entries(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    account_id: int | None = Query(default=None),
    include_voided: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return journal_service.list_journal_entries(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        include_voided=include_voided,
    )


@router.get("/{entry_id}", response_model=JournalEntryRead)
def get_journal_entry(entry_id: int, db: Session = Depends(get_db)):
    return journal_service.get_journal_entry(db, entry_id)


@router.post("/{entry_id}/void", response_model=JournalEntryRead, status_code=201)
def void_journal_entry(entry_id: int, db: Session = Depends(get_db)):
    return journal_service.void_journal_entry(db, entry_id)
