"""Single-user authentication: password hashing and signed session cookies."""

import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, TimestampSigner
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.errors import ConflictError

PBKDF2_ITERATIONS = 200_000
COOKIE_NAME = "session"
COOKIE_MAX_AGE_SECONDS = 12 * 60 * 60


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hex: str) -> bool:
    _, digest_hex = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest_hex, expected_hex)


def get_user(db: Session) -> User | None:
    return db.scalar(select(User).limit(1))


def setup_user(db: Session, username: str, password: str) -> User:
    if get_user(db) is not None:
        raise ConflictError("A user is already configured")
    salt_hex, digest_hex = hash_password(password)
    user = User(
        username=username,
        password_hash=f"{PBKDF2_ITERATIONS}${salt_hex}${digest_hex}",
        session_secret=secrets.token_hex(32),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        return None
    _iterations, salt_hex, digest_hex = user.password_hash.split("$")
    if not verify_password(password, salt_hex, digest_hex):
        return None
    return user


def create_session_token(user: User) -> str:
    signer = TimestampSigner(user.session_secret)
    return signer.sign(user.username.encode("utf-8")).decode("utf-8")


def parse_session_token(user: User, token: str) -> str | None:
    signer = TimestampSigner(user.session_secret)
    try:
        username = signer.unsign(token, max_age=COOKIE_MAX_AGE_SECONDS)
    except BadSignature:
        return None
    if username != user.username.encode("utf-8"):
        return None
    return username.decode("utf-8")
