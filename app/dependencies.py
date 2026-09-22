"""Shared FastAPI dependencies."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import auth as auth_service


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
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
    return user
