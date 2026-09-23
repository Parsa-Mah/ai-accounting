"""REST endpoints for the item catalog."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.services import items as items_service

router = APIRouter(
    prefix="/api/items", tags=["items"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    return items_service.create_item(db, payload)


@router.get("", response_model=list[ItemRead])
def list_items(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return items_service.list_items(db, include_inactive=include_inactive)


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)):
    return items_service.get_item(db, item_id)


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)):
    return items_service.update_item(db, item_id, payload)


@router.post("/{item_id}/deactivate", response_model=ItemRead)
def deactivate_item(item_id: int, db: Session = Depends(get_db)):
    return items_service.deactivate_item(db, item_id)
