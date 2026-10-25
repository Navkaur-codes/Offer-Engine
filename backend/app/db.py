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
PK_COLUMNS_SQL = text(
    "SELECT k.column_name FROM information_schema.table_constraints c "
    "JOIN information_schema.key_column_usage k "
    "ON k.constraint_name = c.constraint_name AND k.table_name = c.table_name "
    "WHERE c.table_name = :t AND c.constraint_type = 'PRIMARY KEY'"
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

    rekey_customer_bots()
    SQLModel.metadata.create_all(engine)
    upgrade_bigint_columns()


def rekey_customer_bots() -> None:
    """CR-C1: `customer_bots` used to be keyed by username. The Lab rebuilds its rows every round, so an
    old-shaped table is simply dropped and `create_all` recreates it keyed by customer_id. Idempotent."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        if conn.execute(PK_COLUMNS_SQL, {"t": "customer_bots"}).scalars().all() == ["username"]:
            conn.execute(text('DROP TABLE "customer_bots"'))
            log.info("dropped customer_bots keyed by username; recreating keyed by customer_id")


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
