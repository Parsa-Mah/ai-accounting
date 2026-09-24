"""Database engine, session, and schema initialization."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("ACCOUNTING_DB_PATH", str(PROJECT_ROOT / "accounting.db")))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_journal_line_columns(db) -> None:
    """Add reconciliation columns to a pre-existing journal_lines table.

    ``create_all`` only creates missing tables; it never alters existing
    ones. Fresh databases already have the columns, so this is a no-op
    there.
    """
    from sqlalchemy import text

    existing = {
        row[1] for row in db.execute(text("PRAGMA table_info(journal_lines)"))
    }
    if "cleared" not in existing:
        db.execute(
            text("ALTER TABLE journal_lines ADD COLUMN cleared BOOLEAN NOT NULL DEFAULT 0")
        )
    if "reconciliation_id" not in existing:
        db.execute(
            text(
                "ALTER TABLE journal_lines ADD COLUMN reconciliation_id "
                "INTEGER REFERENCES reconciliations(id)"
            )
        )
    db.commit()


def init_db():
    from app import models  # noqa: F401  (registers models on Base.metadata)
    from app.seed.coa import seed_coa

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        _ensure_journal_line_columns(db)
        seed_coa(db)
    finally:
        db.close()
