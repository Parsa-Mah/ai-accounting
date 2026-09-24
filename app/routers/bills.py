"""REST endpoints for bills (AP)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.bill import BillCreate, BillPayCreate, BillPaymentRead, BillRead
from app.services import bills as bills_service

router = APIRouter(
    prefix="/api/bills", tags=["bills"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=BillRead, status_code=201)
def create_bill(payload: BillCreate, db: Session = Depends(get_db)):
    return bills_service.create_bill(
        db,
        vendor_id=payload.vendor_id,
        date=payload.date,
        due_date=payload.due_date,
        tax_rate=payload.tax_rate,
        lines=payload.lines,
    )


@router.get("", response_model=list[BillRead])
def list_bills(
    vendor_id: int | None = Query(default=None),
    include_voided: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return bills_service.list_bills(
        db, vendor_id=vendor_id, include_voided=include_voided
    )


@router.get("/{bill_id}", response_model=BillRead)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    return bills_service.get_bill(db, bill_id)


@router.post("/{bill_id}/pay", response_model=BillPaymentRead, status_code=201)
def pay_bill(bill_id: int, payload: BillPayCreate, db: Session = Depends(get_db)):
    return bills_service.pay_bill(
        db,
        bill_id,
        amount_cents=payload.amount_cents,
        date=payload.date,
        note=payload.note,
    )


@router.post("/{bill_id}/void", response_model=BillRead)
def void_bill(bill_id: int, db: Session = Depends(get_db)):
    return bills_service.void_bill(db, bill_id)
