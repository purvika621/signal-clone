from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import BACKEND_DIR, settings


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """SQLite stores naive timestamps; expose timezone-aware UTC to Python."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


def build_engine(database_url: str, busy_timeout_ms: int = 5000) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        raise ValueError("This project requires a SQLite DATABASE_URL")
    if url.database and url.database != ":memory:":
        from pathlib import Path

        path = Path(url.database)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        url = url.set(database=str(path.resolve()))

    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": busy_timeout_ms / 1000})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        # Python 3.12+ sqlite3 requires autocommit while changing connection PRAGMAs.
        previous = getattr(connection, "autocommit", None)
        if previous is not None:
            connection.autocommit = True
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        finally:
            cursor.close()
            if previous is not None:
                connection.autocommit = previous

    return engine


engine = build_engine(settings.database_url, settings.sqlite_busy_timeout_ms)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """A session per request; commands will explicitly commit their transaction."""
    with SessionLocal() as session:
        yield session

