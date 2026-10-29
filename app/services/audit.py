"""Centralized audit trail: actor identity + a Session-level hook.

Every committed write to the books lands in the append-only ``audit_log``
table. The hook is registered once on the ``Session`` class (idempotent),
so it catches every session in the process — web ``get_db``, MCP
``get_session``, tests — without any service or router knowing about
auditing.

Actor identity is a contextvar set at the two front doors:

- web requests: ``user:<id>`` in ``get_current_user``
- MCP tool calls: ``ai:<MCP_CLIENT_NAME>`` in ``context.get_session()``
- everything else (COA seed, ``--seed`` demo data, first-run setup):
  the ``system`` default

A per-context override (``set_actor_override``) can replace the front-door
actor; the command center uses it to audit its tool executions as
``ai:command-center``.

SQLAlchemy 2.0 blocks re-entrant flushes/commits inside its events
("Session is already flushing" / "committed" state), so the hook buffers
the changed records on ``after_flush`` (where the session's pending sets
still hold the flushed objects) and writes the audit rows on
``after_commit`` in a follow-up transaction via a fresh session.
Rollbacks clear the buffer, so nothing is audited unless it committed.
"""

import contextvars
import datetime
import os

from sqlalchemy import event, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.unitofwork import UOWTransaction

from app.database import SessionLocal
from app.models.audit import AuditLog

__all__ = [
    "AI_COMMAND_CENTER_ACTOR",
    "set_actor",
    "reset_actor",
    "current_actor",
    "ai_actor",
    "set_actor_override",
    "reset_actor_override",
    "actor_override",
    "list_audit_log",
    "install_hooks",
]

_current_actor: contextvars.ContextVar[str] = contextvars.ContextVar(
    "accounting_actor", default="system"
)

# Actor for the AI command center (web chat acting through the tools):
# distinguishes AI-composed actions from ``user:<id>`` (manual UI) and
# ``ai:<client>`` (external MCP clients).
AI_COMMAND_CENTER_ACTOR = "ai:command-center"

# Optional per-context override of the front-door actor. Set by the
# command center around tool executions so they audit as
# ``ai:command-center`` even though ``get_session()`` would otherwise
# use the MCP client actor. Default None = no override.
_actor_override: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "accounting_actor_override", default=None
)

# Negative skip list: everything is audited except these. AuditLog itself
# guards against recursion; the line-item child models are audited through
# their parent (journal entry / invoice / bill / estimate).
_SKIP = frozenset(
    {
        "AuditLog",
        "JournalLine",
        "InvoiceLine",
        "BillLine",
        "EstimateLine",
        "ChatConversation",
    }
)

_BUFFER_KEY = "audit_buffer"

_installed = False


def set_actor(actor: str) -> contextvars.Token[str]:
    """Set the actor for the current context (per request / tool call)."""
    return _current_actor.set(actor)


def reset_actor(token: contextvars.Token[str]) -> None:
    """Restore the actor to its value before the matching ``set_actor``."""
    _current_actor.reset(token)


def current_actor() -> str:
    """The actor for the current context (``system`` by default)."""
    return _current_actor.get()


def ai_actor() -> str:
    """MCP actor id: ``ai:<MCP_CLIENT_NAME>`` (env read at call time)."""
    return f"ai:{os.environ.get('MCP_CLIENT_NAME', 'mcp')}"


def set_actor_override(actor: str) -> contextvars.Token[str | None]:
    """Override the front-door actor for the current context.

    Used by the command center so its tool executions audit as
    ``ai:command-center``. Pair with :func:`reset_actor_override`.
    """
    return _actor_override.set(actor)


def reset_actor_override(token: contextvars.Token[str | None]) -> None:
    """Restore the override to its value before the matching set."""
    _actor_override.reset(token)


def actor_override() -> str | None:
    """The actor override for the current context, if one is set."""
    return _actor_override.get()


def list_audit_log(
    db: Session,
    *,
    actor: str | None = None,
    model: str | None = None,
    action: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = 200,
) -> list[AuditLog]:
    """List audit rows, newest first, with optional exact-match filters.

    ``date_from``/``date_to`` are inclusive calendar days on the write
    timestamp. The trail is append-only, so ``id`` order is the true
    insertion order (timestamps can tie within a commit).
    """
    stmt = select(AuditLog)
    if actor is not None:
        stmt = stmt.where(AuditLog.actor == actor)
    if model is not None:
        stmt = stmt.where(AuditLog.model == model)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if date_from is not None:
        stmt = stmt.where(
            AuditLog.timestamp
            >= datetime.datetime.combine(date_from, datetime.time.min)
        )
    if date_to is not None:
        stmt = stmt.where(
            AuditLog.timestamp
            <= datetime.datetime.combine(date_to, datetime.time.max)
        )
    return list(db.scalars(stmt.order_by(AuditLog.id.desc()).limit(limit)))


def _buffer_changes(session: Session, flush_context: UOWTransaction) -> None:
    """Record (model, action, record_id) for every object in this flush.

    At ``after_flush`` time the session's pending sets still hold the
    flushed objects (``finalize_flush_changes`` runs after the event), so
    ``session.new/dirty/deleted`` are exactly this flush's changes.
    ``flush_context`` is the unit-of-work transaction; it carries no
    per-flush object lists in SQLAlchemy 2.0, so the session sets are the
    source of truth here.
    """
    buffer: list[tuple[str, str, int | None]] = session.info.setdefault(
        _BUFFER_KEY, []
    )
    for objects, action in (
        (session.new, "create"),
        (session.dirty, "update"),
        (session.deleted, "delete"),
    ):
        for obj in objects:
            name = type(obj).__name__
            if name not in _SKIP:
                buffer.append((name, action, getattr(obj, "id", None)))


def _write_audit(session: Session) -> None:
    """Write the buffered changes as audit rows in a follow-up transaction.

    A fresh session is used: at ``after_commit`` time the committing
    session's transaction is already in the "committed" state and cannot
    start new SQL until its next autobegin. The re-fired ``after_commit``
    sees an empty buffer (popped above) and the re-fired ``after_flush``
    sees only skipped ``AuditLog`` rows, so this terminates.
    """
    buffer: list[tuple[str, str, int | None]] = session.info.pop(_BUFFER_KEY, [])
    if not buffer:
        return
    audit_db = SessionLocal()
    try:
        for model, action, record_id in buffer:
            audit_db.add(
                AuditLog(
                    actor=current_actor(),
                    action=action,
                    model=model,
                    record_id=record_id,
                )
            )
        audit_db.commit()
    except Exception:
        audit_db.rollback()
        raise
    finally:
        audit_db.close()


def _clear_buffer(session: Session) -> None:
    """Drop buffered changes on rollback (nothing committed, nothing audited)."""
    session.info.pop(_BUFFER_KEY, None)


def install_hooks() -> None:
    """Register the Session-level audit hooks once (idempotent).

    ``init_db()`` runs per ``create_app()``, per ``build_server()``, and
    per test fixture, so the flag makes re-registration a no-op.
    """
    global _installed
    if _installed:
        return
    _installed = True
    event.listen(Session, "after_flush", _buffer_changes)
    event.listen(Session, "after_commit", _write_audit)
    event.listen(Session, "after_rollback", _clear_buffer)
