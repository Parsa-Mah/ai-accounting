"""Shared FastAPI dependencies."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import auth as auth_service
from app.services import audit as audit_service


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # Async (not sync) on purpose: a sync dependency runs in a throwaway
    # threadpool context, so a contextvar set there would not reach the
    # endpoint's context. Async runs in the request's task context, so the
    # actor propagates to the endpoint and its commits (the audit hook).
    user = auth_service.get_user(db)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="No user configured. Call POST /api/auth/setup first.",
        )
    token = request.cookies.get(auth_service.COOKIE_NAME)
    if token is None or auth_service.parse_session_token(user, token) is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )
    # Every authenticated request's writes are audited as this user.
    # (The auth router — setup/login — does not go through here, so its
    # writes log as ``system``.)
    audit_service.set_actor(f"user:{user.id}")
    return user
