"""SQLite engine initializer enforcing WAL, busy timeouts, and foreign keys."""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Pragmas applied to every new DBAPI connection in the pool, per ARCHITECTURE.md §4.
_WAL_PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA busy_timeout=5000;",
    "PRAGMA foreign_keys=ON;",
)


def _apply_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    """Apply journal and timeout pragmas each time a raw connection is created."""
    cursor = dbapi_connection.cursor()
    for pragma in _WAL_PRAGMAS:
        cursor.execute(pragma)
    cursor.close()


def attach_sqlite_pragmas(engine: AsyncEngine) -> AsyncEngine:
    """Attach WAL, busy-timeout, and foreign-key pragmas to an async engine.

    Every DBAPI connection created by the engine's pool afterwards runs the
    pragmas on connect, so pooled connections always honor the same settings.

    Args:
        engine: The ``AsyncEngine`` to configure in place.

    Returns:
        The same engine, for fluent call sites.
    """
    event.listen(engine.sync_engine, "connect", _apply_pragmas)
    return engine


def create_sqlite_engine(db_url: str, echo: bool = False) -> AsyncEngine:
    """Create an async SQLite engine with WAL mode and a 5000ms busy timeout.

    Args:
        db_url: Database URL using the ``sqlite+aiosqlite`` driver scheme.
        echo: When True, log all emitted SQL statements.

    Returns:
        A configured ``AsyncEngine`` whose connections run in WAL journal mode.
    """
    if not db_url.startswith("sqlite+aiosqlite://"):
        raise ValueError(
            "create_sqlite_engine expects a sqlite+aiosqlite:// database URL "
            f"(received: {db_url})"
        )

    return attach_sqlite_pragmas(create_async_engine(db_url, echo=echo))
