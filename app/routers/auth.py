"""Authentication endpoints: setup (first run), login, logout, me."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import AuthStatus, AuthUser, Credentials
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        auth_service.COOKIE_NAME,
        auth_service.create_session_token(user),
        max_age=auth_service.COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


@router.get("/status", response_model=AuthStatus)
def auth_status(db: Session = Depends(get_db)):
    return AuthStatus(configured=auth_service.get_user(db) is not None)


@router.post("/setup", response_model=AuthUser, status_code=201)
def setup(
    payload: Credentials,
    response: Response,
    db: Session = Depends(get_db),
):
    user = auth_service.setup_user(db, payload.username, payload.password)
    _set_session_cookie(response, user)
    return AuthUser(username=user.username)


@router.post("/login", response_model=AuthUser)
def login(
    payload: Credentials,
    response: Response,
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    _set_session_cookie(response, user)
    return AuthUser(username=user.username)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=AuthUser)
def me(user: User = Depends(get_current_user)):
    return AuthUser(username=user.username)
