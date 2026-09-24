"""REST endpoints for budgets (actual vs budget, variance)."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.budget import (
    BudgetCreate,
    BudgetRead,
    BudgetReportRead,
    BudgetUpdate,
)
from app.services import budgets as budgets_service

router = APIRouter(
    prefix="/api/budgets", tags=["budgets"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=BudgetRead, status_code=201)
def create_budget(payload: BudgetCreate, db: Session = Depends(get_db)):
    return budgets_service.create_budget(db, payload)


@router.get("", response_model=list[BudgetRead])
def list_budgets(
    account_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return budgets_service.list_budgets(db, account_id=account_id)


@router.get("/report", response_model=BudgetReportRead)
def budget_report(
    start: date = Query(...),
    end: date = Query(...),
    account_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return budgets_service.budget_report(
        db, start=start, end=end, account_id=account_id
    )


@router.get("/{budget_id}", response_model=BudgetRead)
def get_budget(budget_id: int, db: Session = Depends(get_db)):
    return budgets_service.get_budget(db, budget_id)


@router.patch("/{budget_id}", response_model=BudgetRead)
def update_budget(
    budget_id: int, payload: BudgetUpdate, db: Session = Depends(get_db)
):
    return budgets_service.update_budget(db, budget_id, payload)


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    budgets_service.delete_budget(db, budget_id)
    return Response(status_code=204)
