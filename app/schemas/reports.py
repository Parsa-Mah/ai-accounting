"""Pydantic schemas for financial statement responses.

Money values are integer cents, positive in the account type's natural
direction.
"""

from datetime import date

from pydantic import BaseModel


class StatementLineRead(BaseModel):
    account_id: int | None
    number: str
    name: str
    amount: int


class IncomeStatementRead(BaseModel):
    date_from: date | None
    date_to: date | None
    revenue: list[StatementLineRead]
    total_revenue: int
    expenses: list[StatementLineRead]
    total_expenses: int
    net_income: int


class BalanceSheetRead(BaseModel):
    as_of: date | None
    assets: list[StatementLineRead]
    total_assets: int
    liabilities: list[StatementLineRead]
    total_liabilities: int
    equity: list[StatementLineRead]
    total_equity: int
    balanced: bool
