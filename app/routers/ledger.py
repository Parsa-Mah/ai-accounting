"""REST endpoints for the ledger (general ledger and trial balance)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.ledger import GeneralLedgerRead, TrialBalanceRead
from app.services import ledger as ledger_service

router = APIRouter(
    prefix="/api/ledger", tags=["ledger"], dependencies=[Depends(get_current_user)]
)


@router.get("/accounts/{account_id}/transactions", response_model=GeneralLedgerRead)
def get_general_ledger(
    account_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    include_voided: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return ledger_service.general_ledger(
        db,
        account_id,
        date_from=date_from,
        date_to=date_to,
        include_voided=include_voided,
    )


@router.get("/trial-balance", response_model=TrialBalanceRead)
def get_trial_balance(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ledger_service.trial_balance(db, as_of=as_of)
