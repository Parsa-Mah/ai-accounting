"""REST endpoints for customers and vendors."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.party import CustomerCreate, CustomerRead, VendorCreate, VendorRead
from app.services import parties as parties_service

router = APIRouter(
    prefix="/api", tags=["parties"], dependencies=[Depends(get_current_user)]
)


@router.post("/customers", response_model=CustomerRead, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    return parties_service.create_customer(db, payload)


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)):
    return parties_service.list_customers(db)


@router.get("/customers/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return parties_service.get_customer(db, customer_id)


@router.post("/vendors", response_model=VendorRead, status_code=201)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db)):
    return parties_service.create_vendor(db, payload)


@router.get("/vendors", response_model=list[VendorRead])
def list_vendors(db: Session = Depends(get_db)):
    return parties_service.list_vendors(db)


@router.get("/vendors/{vendor_id}", response_model=VendorRead)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    return parties_service.get_vendor(db, vendor_id)
