"""REST endpoints for the chart of accounts."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.account import AccountType
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate
from app.services import accounts as accounts_service

router = APIRouter(
    prefix="/api/accounts", tags=["accounts"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[AccountRead])
def list_accounts(
    type: AccountType | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return accounts_service.list_accounts(
        db, account_type=type, include_inactive=include_inactive
    )


@router.post("", response_model=AccountRead, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    return accounts_service.create_account(db, payload)


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: int, db: Session = Depends(get_db)):
    return accounts_service.get_account(db, account_id)


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)
):
    return accounts_service.update_account(db, account_id, payload)


@router.post("/{account_id}/deactivate", response_model=AccountRead)
def deactivate_account(account_id: int, db: Session = Depends(get_db)):
    return accounts_service.deactivate_account(db, account_id)
