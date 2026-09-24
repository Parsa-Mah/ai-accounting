"""Budget service — planned amounts per account over a date range.

Budgets are planning data: they post nothing to the ledger. The report
compares each budget to the account's actual activity over the budget's
own range, expressed in the account type's natural direction (expenses
and assets debit-normal; revenue, liability, equity credit-normal) — the
same convention the financial statements use.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountType
from app.models.budget import Budget
from app.schemas.budget import BudgetCreate, BudgetUpdate
from app.services.accounts import get_account
from app.services.errors import NotFoundError, ValidationError
from app.services.ledger import account_balance


def create_budget(db: Session, data: BudgetCreate) -> Budget:
    get_account(db, data.account_id)  # 404 if the account does not exist
    budget = Budget(
        account_id=data.account_id,
        budget_start=data.budget_start,
        budget_end=data.budget_end,
        budget_cents=data.budget_cents,
        note=data.note,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def get_budget(db: Session, budget_id: int) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise NotFoundError(f"Budget {budget_id} not found")
    return budget


def list_budgets(db: Session, *, account_id: int | None = None) -> list[Budget]:
    stmt = select(Budget)
    if account_id is not None:
        stmt = stmt.where(Budget.account_id == account_id)
    stmt = stmt.order_by(Budget.budget_start.desc(), Budget.id.desc())
    return list(db.scalars(stmt))


def update_budget(db: Session, budget_id: int, data: BudgetUpdate) -> Budget:
    budget = get_budget(db, budget_id)
    changes = data.model_dump(exclude_unset=True)
    new_start = changes.get("budget_start", budget.budget_start)
    new_end = changes.get("budget_end", budget.budget_end)
    if new_start > new_end:
        raise ValidationError("budget_start must be on or before budget_end")
    for field, value in changes.items():
        setattr(budget, field, value)
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: Session, budget_id: int) -> None:
    budget = get_budget(db, budget_id)
    db.delete(budget)
    db.commit()


def _actual_cents(db: Session, account, start: date, end: date) -> int:
    """Account activity for a range in its natural direction (cents)."""
    net = account_balance(db, account.id, date_from=start, date_to=end)
    if account.type in (AccountType.EXPENSE, AccountType.ASSET):
        return net
    return -net


def budget_report(
    db: Session, *, start: date, end: date, account_id: int | None = None
) -> dict:
    """Actual vs budget for budgets fully contained in [start, end].

    Each row compares the budget amount to the account's actual activity
    over the budget's own range. ``variance_cents`` is positive when
    actual is below the budget.
    """
    stmt = select(Budget).where(
        Budget.budget_start >= start, Budget.budget_end <= end
    )
    if account_id is not None:
        stmt = stmt.where(Budget.account_id == account_id)
    stmt = stmt.order_by(Budget.budget_start, Budget.id)
    budgets = list(db.scalars(stmt))

    rows = []
    total_budget = 0
    total_actual = 0
    for budget in budgets:
        account = budget.account
        actual = _actual_cents(db, account, budget.budget_start, budget.budget_end)
        variance = budget.budget_cents - actual
        rows.append(
            {
                "budget_id": budget.id,
                "account_id": account.id,
                "account_number": account.number,
                "account_name": account.name,
                "account_type": account.type.value,
                "budget_start": budget.budget_start,
                "budget_end": budget.budget_end,
                "budget_cents": budget.budget_cents,
                "actual_cents": actual,
                "variance_cents": variance,
                "within_budget": actual <= budget.budget_cents,
            }
        )
        total_budget += budget.budget_cents
        total_actual += actual

    return {
        "start": start,
        "end": end,
        "rows": rows,
        "totals": {
            "budget_cents": total_budget,
            "actual_cents": total_actual,
            "variance_cents": total_budget - total_actual,
        },
    }
