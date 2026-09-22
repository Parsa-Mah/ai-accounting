"""Pydantic schemas for ledger and trial balance responses.

Money values are integer cents. Net balances are debit-positive.
"""

from datetime import date

from pydantic import BaseModel


class GeneralLedgerLineRead(BaseModel):
    date: date
    entry_id: int
    entry_description: str
    line_description: str | None
    debit: int
    credit: int
    balance: int
    is_voided: bool


class GeneralLedgerRead(BaseModel):
    account_id: int
    account_number: str
    account_name: str
    account_type: str
    opening_balance: int
    lines: list[GeneralLedgerLineRead]
    closing_balance: int


class TrialBalanceRowRead(BaseModel):
    account_id: int
    number: str
    name: str
    type: str
    debit: int
    credit: int


class TrialBalanceTotalsRead(BaseModel):
    debit: int
    credit: int


class TrialBalanceRead(BaseModel):
    as_of: date | None
    rows: list[TrialBalanceRowRead]
    totals: TrialBalanceTotalsRead
    balanced: bool
