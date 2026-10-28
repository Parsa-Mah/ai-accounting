"""REST endpoints for reading the audit trail.

The trail is append-only and written by the centralized Session hook
(``app/services/audit.py``); this router only reads it. Filters are
exact matches (``actor``/``model``/``action``) plus an inclusive
calendar-day range on the write timestamp.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.audit import AuditLogRead
from app.services import audit as audit_service

router = APIRouter(
    prefix="/api/audit", tags=["audit"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[AuditLogRead])
def list_audit_log(
    actor: str | None = Query(default=None),
    model: str | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return audit_service.list_audit_log(
        db,
        actor=actor,
        model=model,
        action=action,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
