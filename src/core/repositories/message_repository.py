"""Concrete repository for dialogue messages attached to event nodes."""

from typing import List, Optional

from sqlalchemy import inspect, text

from core.db_engine import attach_sqlite_pragmas
from core.dtos.db_entities import Message
from core.repositories.db_sql_repo.sql_alchemy_repository import SQLAlchemyRepository


class MessageRepository(SQLAlchemyRepository[Message]):
    """CRUD repository for the ``messages`` table on a WAL-enabled SQLite engine."""

    def __init__(self, db_url: str, echo: bool = False) -> None:
        """Create the async engine via the base class, then attach WAL pragmas to it."""
        super().__init__(Message, db_url, echo)
        attach_sqlite_pragmas(self._engine)

    def _ensure_session(self) -> None:
        """Open a session lazily when the repository is used outside 'async with'."""
        if self._session is None:
            self._session = self._session_factory()

    async def __aenter__(self) -> "MessageRepository":
        """Reuse or open the session so long-lived callers share one session."""
        self._ensure_session()
        return self

    async def insert_async(self, entity) -> Message:
        """Insert a message, assigning its next per-node position when absent."""
        if not isinstance(entity, Message):
            entity = Message(**entity)

        if entity.position is None:
            entity.position = await self._next_position_async(entity.node_id)

        self._ensure_session()
        return await super().insert_async(entity)

    async def _next_position_async(self, node_id: str) -> int:
        """Return the next zero-based conversation position for a node."""
        messages = await self.get_by_node_async(node_id)
        positions = [
            int(message.position)
            for message in messages
            if getattr(message, "position", None) is not None
        ]
        return max(positions, default=-1) + 1

    async def get_async(self, entity_id: str) -> Optional[Message]:
        """Fetch one message by id, opening a session first when needed."""
        self._ensure_session()
        return await super().get_async(entity_id)

    async def get_by_node_async(self, node_id: str) -> List[Message]:
        """Return messages in explicit conversation order.

        The timestamp is retained as the user-editable time the message was
        spoken; it is only a tie-breaker for legacy rows that have no distinct
        position yet.
        """
        self._ensure_session()
        messages = await self.get_by_expression_async(Message.node_id == node_id)
        return sorted(
            messages,
            key=lambda message: (
                getattr(message, "position", None)
                if getattr(message, "position", None) is not None
                else 0,
                message.timestamp,
                message.id or "",
            ),
        )

    async def update_async(self, entity_id: str, values: dict) -> Message:
        """Update one message, opening a session first when needed."""
        self._ensure_session()
        return await super().update_async(entity_id, values)

    async def delete_async(self, entity_id: str) -> None:
        """Delete one message, opening a session first when needed."""
        self._ensure_session()
        await super().delete_async(entity_id)

    async def create_schema_async(self) -> None:
        """Create/upgrade message storage with ordering and node foreign key."""
        await self.create_schema()
        position_added = await self._ensure_position_column_async()
        await self._ensure_node_foreign_key_async()
        if position_added:
            await self._backfill_positions_async()

    async def _ensure_node_foreign_key_async(self) -> None:
        """Rebuild an old message table so node records reference event nodes."""
        async with self._engine.begin() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
            if "messages" not in table_names:
                return

            foreign_keys = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_foreign_keys(
                    "messages"
                )
            )
            has_node_foreign_key = any(
                foreign_key.get("referred_table") == "event_log_nodes"
                and "node_id" in foreign_key.get("constrained_columns", [])
                for foreign_key in foreign_keys
            )
            if has_node_foreign_key:
                return

            await connection.execute(
                text("ALTER TABLE messages RENAME TO messages_legacy")
            )
            await connection.run_sync(
                lambda sync_connection: Message.__table__.create(sync_connection)
            )
            await connection.execute(
                text(
                    "INSERT INTO messages "
                    "(id, node_id, sender, content, position, timestamp) "
                    "SELECT id, node_id, sender, content, position, timestamp "
                    "FROM messages_legacy"
                )
            )
            await connection.execute(text("DROP TABLE messages_legacy"))

    async def _ensure_position_column_async(self) -> bool:
        """Add ``messages.position`` to databases created before ordering existed."""
        async with self._engine.begin() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_columns("messages")
            )
            if any(column["name"] == "position" for column in columns):
                return False
            await connection.execute(
                text("ALTER TABLE messages ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
            )
        return True

    async def _backfill_positions_async(self) -> None:
        """Give legacy messages deterministic positions ordered by timestamp."""
        self._ensure_session()
        try:
            messages = await self.get_all_async()
            grouped: dict[str, List[Message]] = {}
            for message in messages:
                grouped.setdefault(message.node_id, []).append(message)

            for node_messages in grouped.values():
                ordered = sorted(
                    node_messages,
                    key=lambda message: (message.timestamp, message.id or ""),
                )
                for position, message in enumerate(ordered):
                    if message.position != position:
                        await super().update_async(message.id, {"position": position})
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    async def drop_schema_async(self) -> None:
        """Drop the tables, returning the database to an empty state."""
        await self.drop_schema()