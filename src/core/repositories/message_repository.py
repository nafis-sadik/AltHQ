"""Concrete repository for dialogue messages attached to event nodes."""

from typing import List, Optional

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
        """Insert a message, or build one first when given a values dict."""
        if not isinstance(entity, Message):
            entity = Message(**entity)
        self._ensure_session()
        return await super().insert_async(entity)

    async def get_async(self, entity_id: str) -> Optional[Message]:
        """Fetch one message by id, opening a session first when needed."""
        self._ensure_session()
        return await super().get_async(entity_id)

    async def get_by_node_async(self, node_id: str) -> List[Message]:
        """Return every message attached to the node, oldest first."""
        self._ensure_session()
        messages = await self.get_by_expression_async(Message.node_id == node_id)
        return sorted(messages, key=lambda message: message.timestamp)

    async def update_async(self, entity_id: str, values: dict) -> Message:
        """Update one message, opening a session first when needed."""
        self._ensure_session()
        return await super().update_async(entity_id, values)

    async def delete_async(self, entity_id: str) -> None:
        """Delete one message, opening a session first when needed."""
        self._ensure_session()
        await super().delete_async(entity_id)

    async def create_schema_async(self) -> None:
        """Create the tables when they do not exist yet."""
        await self.create_schema()

    async def drop_schema_async(self) -> None:
        """Drop the tables, returning the database to an empty state."""
        await self.drop_schema()