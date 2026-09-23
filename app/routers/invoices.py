"""REST endpoints for invoices (AR)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.invoice import (
    InvoiceCreate,
    InvoicePayCreate,
    InvoicePaymentRead,
    InvoiceRead,
)
from app.services import invoices as invoices_service

router = APIRouter(
    prefix="/api/invoices", tags=["invoices"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    return invoices_service.create_invoice(
        db,
        customer_id=payload.customer_id,
        date=payload.date,
        due_date=payload.due_date,
        tax_rate=payload.tax_rate,
        lines=payload.lines,
    )


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    customer_id: int | None = Query(default=None),
    include_voided: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return invoices_service.list_invoices(
        db, customer_id=customer_id, include_voided=include_voided
    )


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    return invoices_service.get_invoice(db, invoice_id)


@router.post("/{invoice_id}/pay", response_model=InvoicePaymentRead, status_code=201)
def pay_invoice(
    invoice_id: int, payload: InvoicePayCreate, db: Session = Depends(get_db)
):
    return invoices_service.pay_invoice(
        db,
        invoice_id,
        amount_cents=payload.amount_cents,
        date=payload.date,
        note=payload.note,
    )


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
def void_invoice(invoice_id: int, db: Session = Depends(get_db)):
    return invoices_service.void_invoice(db, invoice_id)
