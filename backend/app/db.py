"""Database engine + sessions. SQLite locally, Neon Postgres in production."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

log = logging.getLogger(__name__)

# columns created as 32-bit INTEGER on Postgres before they became BIGINT (create_all never alters columns)
BIGINT_COLUMNS = [("customers", "telegram_chat_id"), ("decisions", "telegram_message_id")]
COLUMN_TYPE_SQL = text(
    "SELECT data_type FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
)


def _normalise_url(url: str) -> str:
    # Neon hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg3 driver name.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str | None = None):
    url = _normalise_url(url or settings.database_url)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = make_engine()


def init_db() -> None:
    import app.models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)
    upgrade_bigint_columns()


def upgrade_bigint_columns() -> None:
    """One-time, idempotent fix for tables created before the BIGINT change (Postgres only)."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table, column in BIGINT_COLUMNS:
            kind = conn.execute(COLUMN_TYPE_SQL, {"t": table, "c": column}).scalar()
            if kind == "integer":
                conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE BIGINT'))
                log.info("upgraded %s.%s to BIGINT", table, column)


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """For scripts, the bot and scheduler jobs: commits on success, rolls back on error."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
