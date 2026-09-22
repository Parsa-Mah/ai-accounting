"""REST endpoints for financial statements (income statement, balance sheet)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.reports import BalanceSheetRead, IncomeStatementRead
from app.services import reports as reports_service

router = APIRouter(
    prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)]
)


@router.get("/income-statement", response_model=IncomeStatementRead)
def get_income_statement(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return reports_service.income_statement(
        db, date_from=date_from, date_to=date_to
    )


@router.get("/balance-sheet", response_model=BalanceSheetRead)
def get_balance_sheet(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return reports_service.balance_sheet(db, as_of=as_of)
