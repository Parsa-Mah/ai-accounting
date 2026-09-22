"""Chart of accounts service."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.errors import ConflictError, NotFoundError


def list_accounts(
    db: Session,
    *,
    account_type: AccountType | None = None,
    include_inactive: bool = False,
) -> list[Account]:
    stmt = select(Account).order_by(Account.number)
    if account_type is not None:
        stmt = stmt.where(Account.type == account_type)
    if not include_inactive:
        stmt = stmt.where(Account.is_active.is_(True))
    return list(db.scalars(stmt))


def get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError(f"Account {account_id} not found")
    return account


def create_account(db: Session, data: AccountCreate) -> Account:
    clash = db.scalar(
        select(Account).where(
            (Account.number == data.number) | (Account.name == data.name)
        )
    )
    if clash is not None:
        raise ConflictError(
            f"An account with number '{data.number}' or name '{data.name}' already exists"
        )
    account = Account(**data.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account_id: int, data: AccountUpdate) -> Account:
    account = get_account(db, account_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        clash = db.scalar(
            select(Account).where(Account.name == changes["name"], Account.id != account_id)
        )
        if clash is not None:
            raise ConflictError(f"An account named '{changes['name']}' already exists")
    for field, value in changes.items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


def deactivate_account(db: Session, account_id: int) -> Account:
    account = get_account(db, account_id)
    if account.is_system:
        raise ConflictError("System accounts cannot be deactivated")
    account.is_active = False
    db.commit()
    db.refresh(account)
    return account
