"""Engine and sessions. The engine is created on first use so tests can point
settings at a temporary database before any query runs."""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_url: str | None = None


def _sqlite_path(url: str) -> Path | None:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    location = url[len(prefix):]
    if not location or location.startswith(":memory:"):
        return None
    return Path(location)


@event.listens_for(Engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine() -> Engine:
    global _engine, _session_factory, _url
    url = settings.DATABASE_URL
    if _engine is not None and _url == url:
        return _engine
    reset_engine()
    path = _sqlite_path(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    _url = url
    return _engine


def session() -> Session:
    get_engine()
    assert _session_factory is not None
    return _session_factory()


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def reset_engine() -> None:
    """Drop pooled connections. Tests call this so a temp database file can be removed."""
    global _engine, _session_factory, _url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _url = None
