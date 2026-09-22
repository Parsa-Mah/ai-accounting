"""Standard chart of accounts, seeded automatically on startup (idempotent)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType

# (number, name, type, subtype, description, bank_kind, is_system)
STANDARD_COA = [
    ("1000", "Cash", AccountType.ASSET, "cash", "Cash on hand and checking account", "checking", True),
    ("1100", "Accounts Receivable", AccountType.ASSET, "ar", "Amounts owed by customers", None, True),
    ("1200", "Inventory", AccountType.ASSET, "inventory", "Goods held for sale", None, False),
    ("1300", "Prepaid Expenses", AccountType.ASSET, "prepaid", "Expenses paid in advance", None, False),
    ("1500", "Equipment", AccountType.ASSET, "fixed_asset", "Tangible long-lived assets", None, False),
    ("1550", "Accumulated Depreciation - Equipment", AccountType.ASSET, "contra_asset", None, None, False),
    ("2000", "Accounts Payable", AccountType.LIABILITY, "ap", "Amounts owed to vendors", None, True),
    ("2100", "Credit Card Payable", AccountType.LIABILITY, "credit_card", None, None, False),
    ("2200", "Taxes Payable", AccountType.LIABILITY, "tax", "Sales tax collected, not yet remitted", None, True),
    ("2210", "Tax Recoverable", AccountType.LIABILITY, "tax", "Input tax recoverable on purchases", None, True),
    ("2500", "Loans Payable", AccountType.LIABILITY, "loan", None, None, False),
    ("3000", "Owner's Capital", AccountType.EQUITY, "capital", None, None, True),
    ("3100", "Owner's Drawings", AccountType.EQUITY, "drawings", None, None, False),
    ("3900", "Retained Earnings", AccountType.EQUITY, "retained_earnings", None, None, True),
    ("4000", "Sales Revenue", AccountType.REVENUE, "revenue", None, None, True),
    ("4100", "Service Revenue", AccountType.REVENUE, "revenue", None, None, False),
    ("4900", "Other Income", AccountType.REVENUE, "other_income", None, None, False),
    ("5000", "Cost of Goods Sold", AccountType.EXPENSE, "cogs", None, None, True),
    ("5100", "Rent Expense", AccountType.EXPENSE, "rent", None, None, False),
    ("5200", "Payroll Expense", AccountType.EXPENSE, "payroll", None, None, False),
    ("5300", "Utilities Expense", AccountType.EXPENSE, "utilities", None, None, False),
    ("5400", "Office Supplies Expense", AccountType.EXPENSE, "supplies", None, None, False),
    ("5500", "Marketing Expense", AccountType.EXPENSE, "marketing", None, None, False),
    ("5600", "Travel Expense", AccountType.EXPENSE, "travel", None, None, False),
    ("5700", "Software & Subscriptions", AccountType.EXPENSE, "software", None, None, False),
    ("5900", "Miscellaneous Expense", AccountType.EXPENSE, "misc", None, None, False),
]


def seed_coa(db: Session) -> None:
    existing_numbers = set(db.scalars(select(Account.number)))
    for number, name, account_type, subtype, description, bank_kind, is_system in STANDARD_COA:
        if number in existing_numbers:
            continue
        db.add(
            Account(
                number=number,
                name=name,
                type=account_type,
                subtype=subtype,
                description=description,
                bank_kind=bank_kind,
                is_system=is_system,
            )
        )
    db.commit()
