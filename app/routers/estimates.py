"""REST endpoints for estimates."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.estimate import EstimateCreate, EstimateRead
from app.schemas.invoice import InvoiceRead
from app.services import estimates as estimates_service

router = APIRouter(
    prefix="/api/estimates", tags=["estimates"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=EstimateRead, status_code=201)
def create_estimate(payload: EstimateCreate, db: Session = Depends(get_db)):
    return estimates_service.create_estimate(
        db,
        customer_id=payload.customer_id,
        date=payload.date,
        tax_rate=payload.tax_rate,
        lines=payload.lines,
    )


@router.get("", response_model=list[EstimateRead])
def list_estimates(
    customer_id: int | None = Query(default=None),
    include_converted: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return estimates_service.list_estimates(
        db, customer_id=customer_id, include_converted=include_converted
    )


@router.get("/{estimate_id}", response_model=EstimateRead)
def get_estimate(estimate_id: int, db: Session = Depends(get_db)):
    return estimates_service.get_estimate(db, estimate_id)


@router.post("/{estimate_id}/convert", response_model=InvoiceRead, status_code=201)
def convert_estimate(estimate_id: int, db: Session = Depends(get_db)):
    return estimates_service.convert_estimate(db, estimate_id)
