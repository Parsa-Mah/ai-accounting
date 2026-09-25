"""REST endpoints for exporting reports as CSV or PDF file downloads.

Each endpoint mirrors an existing report (general ledger, trial balance,
income statement, balance sheet, journal, invoices, bills) and returns the
report as a downloadable file. ``format`` selects CSV (default) or PDF; the
response carries a ``Content-Disposition`` header so the browser saves it.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.services import export as export_service

router = APIRouter(
    prefix="/api/export", tags=["export"], dependencies=[Depends(get_current_user)]
)


def _download(
    title: str, subtitle: str, header: list[str], rows: list[list[str]], filename: str, fmt: str
) -> Response:
    if fmt == "pdf":
        content = export_service.render_pdf(title, subtitle, header, rows)
        media_type = "application/pdf"
        ext = "pdf"
    else:
        content = export_service.render_csv(header, rows)
        media_type = "text/csv"
        ext = "csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{ext}"'},
    )


@router.get("/general-ledger")
def export_general_ledger(
    account_id: int = Query(...),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    include_voided: bool = Query(default=True),
    format: Literal["csv", "pdf"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    title, subtitle, header, rows, filename = export_service.general_ledger_rows(
        db,
        account_id,
        date_from=date_from,
        date_to=date_to,
        include_voided=include_voided,
    )
    return _download(title, subtitle, header, rows, filename, format)


@router.get("/trial-balance")
def export_trial_balance(
    as_of: date | None = Query(default=None),
    format: Literal["csv", "pdf"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    title, subtitle, header, rows, filename = export_service.trial_balance_rows(db, as_of=as_of)
    return _download(title, subtitle, header, rows, filename, format)


@router.get("/income-statement")
def export_income_statement(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    format: Literal["csv", "pdf"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    title, subtitle, header, rows, filename = export_service.income_statement_rows(
        db, date_from=date_from, date_to=date_to
    )
    return _download(title, subtitle, header, rows, filename, format)


@router.get("/balance-sheet")
def export_balance_sheet(
    as_of: date | None = Query(default=None),
    format: Literal["csv", "pdf"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    title, subtitle, header, rows, filename = export_service.balance_sheet_rows(db, as_of=as_of)
    return _download(title, subtitle, header, rows, filename, format)


@router.get("/journal")
def export_journal(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    account_id: int | None = Query(default=None),
    include_voided: bool = Query(default=True),
    format: Literal["csv", "pdf"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    title, subtitle, header, rows, filename = export_service.journal_rows(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        include_voided=include_voided,
    )
    return _download(title, subtitle, header, rows, filename, format)


@router.get("/invoices")
def export_invoices(
    customer_id: int | None = Query(default=None),
    include_voided: bool = Query(default=True),
    format: Literal["csv", "pdf"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    title, subtitle, header, rows, filename = export_service.invoice_rows(
        db, customer_id=customer_id, include_voided=include_voided
    )
    return _download(title, subtitle, header, rows, filename, format)


@router.get("/bills")
def export_bills(
    vendor_id: int | None = Query(default=None),
    include_voided: bool = Query(default=True),
    format: Literal["csv", "pdf"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    title, subtitle, header, rows, filename = export_service.bill_rows(
        db, vendor_id=vendor_id, include_voided=include_voided
    )
    return _download(title, subtitle, header, rows, filename, format)
