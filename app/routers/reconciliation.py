"""REST endpoints for bank reconciliation."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.reconciliation import (
    BankAccountRead,
    ReconciliationCreate,
    ReconciliationRead,
)
from app.services import reconciliation as reconciliation_service

router = APIRouter(
    prefix="/api/reconciliation",
    tags=["reconciliation"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/accounts", response_model=list[BankAccountRead])
def get_bank_accounts(db: Session = Depends(get_db)):
    return reconciliation_service.list_bank_accounts(db)


@router.post("", response_model=ReconciliationRead, status_code=201)
def create_reconciliation(
    payload: ReconciliationCreate, db: Session = Depends(get_db)
):
    return reconciliation_service.create_reconciliation(
        db,
        account_id=payload.account_id,
        statement_date=payload.statement_date,
        statement_balance_cents=payload.statement_balance_cents,
        line_ids=payload.line_ids,
        note=payload.note,
    )


@router.get("", response_model=list[ReconciliationRead])
def list_reconciliations(
    account_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return reconciliation_service.list_reconciliations(db, account_id=account_id)


@router.get("/{reconciliation_id}", response_model=ReconciliationRead)
def get_reconciliation(reconciliation_id: int, db: Session = Depends(get_db)):
    return reconciliation_service.get_reconciliation(db, reconciliation_id)


@router.delete("/{reconciliation_id}", status_code=204)
def delete_reconciliation(reconciliation_id: int, db: Session = Depends(get_db)):
    reconciliation_service.delete_reconciliation(db, reconciliation_id)
    return Response(status_code=204)
