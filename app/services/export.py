"""Export service — render reports as CSV or PDF downloads.

Each ``*_rows`` builder reuses an existing report service (ledger, reports,
journal, invoices, bills) and flattens its result into a table: a header row
plus data rows of strings. Two generic renderers then turn that table into a
CSV (stdlib ``csv``) or a PDF (ReportLab). Money is converted from integer
cents to dollars with two decimals for human-readable output.

Builders return ``(title, subtitle, header, rows, filename)`` so the router
can attach a sensible ``Content-Disposition`` name and the PDF can show a
title and a date-range subtitle.
"""

import csv
import io
import re
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.services import (
    bills as bills_service,
    invoices as invoices_service,
    journal as journal_service,
    ledger as ledger_service,
    reports as reports_service,
)

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


def money(cents: int) -> str:
    """Integer cents as a dollars string with two decimals (exact, no float)."""
    sign = "-" if cents < 0 else ""
    abs_cents = abs(cents)
    return f"{sign}{abs_cents // 100}.{abs_cents % 100:02d}"


def render_csv(header: list[str], rows: list[list[str]]) -> bytes:
    """A table as UTF-8 CSV with a header row and LF line endings."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def render_pdf(
    title: str, subtitle: str, header: list[str], rows: list[list[str]]
) -> bytes:
    """A table as a one-or-more-page PDF: title, subtitle, then a grid table.

    Columns whose non-empty cells are all numeric are right-aligned.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title=title,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_para = Paragraph(title, styles["Title"])
    subtitle_para = Paragraph(subtitle, styles["Normal"])

    data = [list(header)] + [list(row) for row in rows]
    table = Table(data, repeatRows=1)

    numeric_cols = []
    for col in range(len(header)):
        cells = [str(row[col]) for row in rows if row[col] != ""]
        if cells and all(_NUMERIC.match(cell) for cell in cells):
            numeric_cols.append(col)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for col in numeric_cols:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    table.setStyle(TableStyle(style))

    doc.build([title_para, subtitle_para, table])
    return buffer.getvalue()


def _range_subtitle(date_from: date | None, date_to: date | None) -> str:
    if date_from and date_to:
        return f"{date_from.isoformat()} to {date_to.isoformat()}"
    if date_from:
        return f"From {date_from.isoformat()}"
    if date_to:
        return f"Through {date_to.isoformat()}"
    return "All time"


def _range_suffix(date_from: date | None, date_to: date | None) -> str:
    parts = [d.isoformat() for d in (date_from, date_to) if d is not None]
    return f"-{'_'.join(parts)}" if parts else ""


def general_ledger_rows(
    db: Session,
    account_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    include_voided: bool = True,
):
    gl = ledger_service.general_ledger(
        db,
        account_id,
        date_from=date_from,
        date_to=date_to,
        include_voided=include_voided,
    )
    header = [
        "date",
        "entry",
        "description",
        "line_description",
        "debit",
        "credit",
        "balance",
        "cleared",
    ]
    rows = [["", "", "Opening balance", "", "", "", money(gl["opening_balance"]), ""]]
    for line in gl["lines"]:
        rows.append(
            [
                line["date"].isoformat(),
                str(line["entry_id"]),
                line["entry_description"],
                line["line_description"] or "",
                money(line["debit"]),
                money(line["credit"]),
                money(line["balance"]),
                "yes" if line["cleared"] else "",
            ]
        )
    rows.append(["", "", "Closing balance", "", "", "", money(gl["closing_balance"]), ""])

    subtitle = f"{gl['account_number']} {gl['account_name']}"
    if date_from or date_to:
        subtitle += f" — {_range_subtitle(date_from, date_to)}"
    filename = f"general-ledger-{gl['account_number']}"
    return "General Ledger", subtitle, header, rows, filename


def trial_balance_rows(db: Session, *, as_of: date | None = None):
    tb = ledger_service.trial_balance(db, as_of=as_of)
    header = ["number", "name", "type", "debit", "credit"]
    rows = [
        [row["number"], row["name"], row["type"], money(row["debit"]), money(row["credit"])]
        for row in tb["rows"]
    ]
    rows.append(["", "", "Total", money(tb["totals"]["debit"]), money(tb["totals"]["credit"])])

    subtitle = f"As of {as_of.isoformat()}" if as_of else "All time"
    filename = f"trial-balance-{as_of.isoformat()}" if as_of else "trial-balance"
    return "Trial Balance", subtitle, header, rows, filename


def income_statement_rows(
    db: Session, *, date_from: date | None = None, date_to: date | None = None
):
    statement = reports_service.income_statement(db, date_from=date_from, date_to=date_to)
    header = ["section", "number", "name", "amount"]
    rows = [
        ["Revenue", row["number"], row["name"], money(row["amount"])]
        for row in statement["revenue"]
    ]
    rows.append(["Revenue", "", "Total revenue", money(statement["total_revenue"])])
    rows.extend(
        ["Expense", row["number"], row["name"], money(row["amount"])]
        for row in statement["expenses"]
    )
    rows.append(["Expense", "", "Total expenses", money(statement["total_expenses"])])
    rows.append(["", "", "Net income", money(statement["net_income"])])

    filename = "income-statement" + _range_suffix(date_from, date_to)
    return "Income Statement", _range_subtitle(date_from, date_to), header, rows, filename


def balance_sheet_rows(db: Session, *, as_of: date | None = None):
    sheet = reports_service.balance_sheet(db, as_of=as_of)
    header = ["section", "number", "name", "amount"]
    rows = [
        ["Assets", row["number"], row["name"], money(row["amount"])] for row in sheet["assets"]
    ]
    rows.append(["Assets", "", "Total assets", money(sheet["total_assets"])])
    rows.extend(
        ["Liabilities", row["number"], row["name"], money(row["amount"])]
        for row in sheet["liabilities"]
    )
    rows.append(["Liabilities", "", "Total liabilities", money(sheet["total_liabilities"])])
    rows.extend(
        ["Equity", row["number"], row["name"], money(row["amount"])] for row in sheet["equity"]
    )
    rows.append(["Equity", "", "Total equity", money(sheet["total_equity"])])

    subtitle = f"As of {as_of.isoformat()}" if as_of else "All time"
    filename = f"balance-sheet-{as_of.isoformat()}" if as_of else "balance-sheet"
    return "Balance Sheet", subtitle, header, rows, filename


def journal_rows(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    include_voided: bool = True,
):
    entries = journal_service.list_journal_entries(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        include_voided=include_voided,
    )
    accounts = {account.id: account for account in db.scalars(select(Account))}
    header = [
        "entry",
        "date",
        "description",
        "account_number",
        "account_name",
        "debit",
        "credit",
    ]
    rows = []
    for entry in entries:
        for line in entry.lines:
            account = accounts[line.account_id]
            rows.append(
                [
                    str(entry.id),
                    entry.date.isoformat(),
                    entry.description,
                    account.number,
                    account.name,
                    money(line.debit),
                    money(line.credit),
                ]
            )

    filename = "journal" + _range_suffix(date_from, date_to)
    return "Journal", _range_subtitle(date_from, date_to), header, rows, filename


def invoice_rows(
    db: Session, *, customer_id: int | None = None, include_voided: bool = True
):
    invoices = invoices_service.list_invoices(
        db, customer_id=customer_id, include_voided=include_voided
    )
    header = [
        "id",
        "date",
        "due_date",
        "customer",
        "subtotal",
        "tax",
        "total",
        "paid",
        "balance",
        "status",
    ]
    rows = [
        [
            str(invoice.id),
            invoice.date.isoformat(),
            invoice.due_date.isoformat() if invoice.due_date else "",
            invoice.customer_name,
            money(invoice.subtotal_cents),
            money(invoice.tax_cents),
            money(invoice.total_cents),
            money(invoice.paid_cents),
            money(invoice.total_cents - invoice.paid_cents),
            invoice.status,
        ]
        for invoice in invoices
    ]
    subtitle = f"{len(invoices)} invoice(s)"
    return "Invoices", subtitle, header, rows, "invoices"


def bill_rows(db: Session, *, vendor_id: int | None = None, include_voided: bool = True):
    bills = bills_service.list_bills(db, vendor_id=vendor_id, include_voided=include_voided)
    header = [
        "id",
        "date",
        "due_date",
        "vendor",
        "subtotal",
        "tax",
        "total",
        "paid",
        "balance",
        "status",
    ]
    rows = [
        [
            str(bill.id),
            bill.date.isoformat(),
            bill.due_date.isoformat() if bill.due_date else "",
            bill.vendor_name,
            money(bill.subtotal_cents),
            money(bill.tax_cents),
            money(bill.total_cents),
            money(bill.paid_cents),
            money(bill.total_cents - bill.paid_cents),
            bill.status,
        ]
        for bill in bills
    ]
    subtitle = f"{len(bills)} bill(s)"
    return "Bills", subtitle, header, rows, "bills"
