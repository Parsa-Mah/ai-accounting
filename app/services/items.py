"""Item catalog service."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.errors import NotFoundError


def create_item(db: Session, data: ItemCreate) -> Item:
    item = Item(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_items(db: Session, *, include_inactive: bool = False) -> list[Item]:
    stmt = select(Item).order_by(Item.name)
    if not include_inactive:
        stmt = stmt.where(Item.is_active.is_(True))
    return list(db.scalars(stmt))


def get_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise NotFoundError(f"Item {item_id} not found")
    return item


def update_item(db: Session, item_id: int, data: ItemUpdate) -> Item:
    item = get_item(db, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def deactivate_item(db: Session, item_id: int) -> Item:
    item = get_item(db, item_id)
    item.is_active = False
    db.commit()
    db.refresh(item)
    return item
