"""Database engine + session factory (§6).

Starts on SQLite but every model uses portable column types and no SQLite-only
features, so a future move to PostgreSQL is a connection-string change plus a
migration tool - not a rewrite.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from ..core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base with automatic created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


_settings = get_settings()
_connect_args = (
    {"check_same_thread": False}
    if _settings.resolved_database_url().startswith("sqlite")
    else {}
)
engine = create_engine(
    _settings.resolved_database_url(),
    connect_args=_connect_args,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
