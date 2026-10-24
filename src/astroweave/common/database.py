"""Shared database engine: SQLite locally, Postgres in production.

The whole app used to talk to a single SQLite file directly. That works on one
machine but not on a free cloud host, where the filesystem is ephemeral (a
redeploy or restart wipes it), so signups, conversations and the admin usage
dashboard would all reset. This module is the seam that lets the same code and
the same SQL run against either backend, chosen entirely by configuration:

* ``DATABASE_URL`` **unset** (local development, tests) -> a SQLite file under
  ``app/data/`` exactly where it has always lived. Zero setup.
* ``DATABASE_URL`` **set** (production) -> Postgres. Render can provision this
  and inject the variable automatically, so deploying does not depend on anyone
  hand-creating a database.

Every store (auth, conversations, rate limiter, usage) is migrated onto this
engine, so the admin dashboard keeps reading real data wherever it runs.

Nothing here is Postgres- or SQLite-specific beyond URL handling and the SQLite
WAL pragma; the stores use SQLAlchemy Core with portable SQL so the dialect is
invisible to them.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from astroweave.common.config import get_logger

logger = get_logger(__name__)

_shared_engine: Engine | None = None
_path_engines: dict[str, Engine] = {}


def _repo_root() -> Path:
    # database.py -> common -> astroweave -> src -> repo root
    return Path(__file__).resolve().parents[3]


def default_sqlite_path() -> Path:
    """Historical on-disk location, kept so local data carries over unchanged."""
    return _repo_root() / "app" / "data" / "astroweave.db"


def normalize_url(url: str) -> str:
    """Make a Postgres URL use the psycopg v3 driver SQLAlchemy expects.

    Hosts like Render and Heroku hand out ``postgres://...`` (and sometimes
    ``postgresql://...``) with no driver; SQLAlchemy 2 needs an explicit
    ``postgresql+psycopg://`` to select psycopg 3. A URL that already names a
    driver (``postgresql+psycopg://``) is left untouched.
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def database_url() -> str:
    """The configured database URL, defaulting to the local SQLite file."""
    configured = os.environ.get("DATABASE_URL") or os.environ.get("ASTROWEAVE_DATABASE_URL")
    if configured:
        return normalize_url(configured)
    path = default_sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def _apply_sqlite_pragmas(engine: Engine) -> None:
    """WAL + a busy timeout on every SQLite connection (parity with the old code)."""

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _record):  # noqa: ANN001 - SQLAlchemy callback
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA busy_timeout = 10000")
        cursor.execute("PRAGMA foreign_keys = ON")  # enforce FK cascades (off by default in SQLite)
        cursor.close()


def make_engine(url: str) -> Engine:
    """Build an Engine for a URL, applying backend-appropriate options."""
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        # check_same_thread off: FastAPI serves requests from a threadpool.
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 10}
    else:
        # Free Postgres plans drop idle connections; recycle before they do.
        kwargs["pool_recycle"] = 300
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        _apply_sqlite_pragmas(engine)
    return engine


def get_engine() -> Engine:
    """The process-wide engine selected by ``DATABASE_URL`` (cached)."""
    global _shared_engine
    if _shared_engine is None:
        url = database_url()
        _shared_engine = make_engine(url)
        logger.info("Database engine ready (%s)", url.split("://", 1)[0])
    return _shared_engine


def engine_for_path(path: Path | str) -> Engine:
    """A SQLite engine bound to an explicit file.

    Kept so a store can still be pointed at a specific file (tests pass a temp
    path, and some callers pass the historical DB path). Engines are cached per
    path so repeated construction reuses one connection pool.
    """
    key = str(Path(path))
    engine = _path_engines.get(key)
    if engine is None:
        Path(key).parent.mkdir(parents=True, exist_ok=True)
        engine = make_engine(f"sqlite:///{key}")
        _path_engines[key] = engine
    return engine


def is_postgres(engine: Engine) -> bool:
    return engine.dialect.name == "postgresql"


def resolve_engine(db_path: Path | str | None = None, engine: Engine | None = None) -> Engine:
    """Pick the engine a store should use.

    Precedence: an explicitly passed ``engine`` (tests/embedding), else a
    ``db_path`` (a specific SQLite file), else the shared ``DATABASE_URL``
    engine. This keeps every existing ``Store(path)`` call working while letting
    production route everything through one Postgres engine.
    """
    if engine is not None:
        return engine
    if db_path is not None:
        return engine_for_path(db_path)
    return get_engine()
