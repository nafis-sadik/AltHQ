"""Concrete repository for time-series event nodes, reusing the generic async SQLAlchemy repository."""

from typing import List, Optional

from core.db_engine import attach_sqlite_pragmas
from core.dtos.db_entities import EventLogNode
from core.repositories.db_sql_repo.sql_alchemy_repository import SQLAlchemyRepository


class EventLogRepository(SQLAlchemyRepository[EventLogNode]):
    """CRUD repository for the ``event_log_nodes`` table on a WAL-enabled SQLite engine."""

    def __init__(self, db_url: str, echo: bool = False) -> None:
        """Create the async engine via the base class, then attach WAL pragmas to it."""
        super().__init__(EventLogNode, db_url, echo)
        attach_sqlite_pragmas(self._engine)

    def _ensure_session(self) -> None:
        """Open a session lazily when the repository is used outside 'async with'."""
        if self._session is None:
            self._session = self._session_factory()

    async def __aenter__(self) -> "EventLogRepository":
        """Reuse or open the session so long-lived callers share one session."""
        self._ensure_session()
        return self

    async def insert_async(self, entity) -> EventLogNode:
        """Insert a node, auto-assigning sequence index and active flags when missing."""
        if not isinstance(entity, EventLogNode):
            entity = EventLogNode(**entity)

        if entity.sequence_index is None:
            entity.sequence_index = await self._next_sequence_async(entity.agent_id)

        if entity.is_active is None:
            entity.is_active = True

        self._ensure_session()
        return await super().insert_async(entity)

    async def _next_sequence_async(self, agent_id: str) -> int:
        """Return the next chronological sequence index for the given agent."""
        timeline = await self.get_timeline_async(agent_id)
        return (timeline[-1].sequence_index + 1) if timeline else 1

    async def get_async(self, entity_id: str) -> Optional[EventLogNode]:
        """Fetch one event node by id, opening a session first when needed."""
        self._ensure_session()
        return await super().get_async(entity_id)

    async def get_all_async(self) -> List[EventLogNode]:
        """Fetch every event node, opening a session first when needed."""
        self._ensure_session()
        return await super().get_all_async()

    async def get_timeline_async(self, agent_id: str) -> List[EventLogNode]:
        """Return every event node for the agent, oldest sequence first."""
        self._ensure_session()
        nodes = await self.get_by_expression_async(
            EventLogNode.agent_id == agent_id
        )
        return sorted(nodes, key=lambda node: node.sequence_index)

    async def get_active_by_agent_async(self, agent_id: str) -> List[EventLogNode]:
        """Return the agent's active event nodes, oldest sequence first."""
        self._ensure_session()
        nodes = await self.get_by_expression_async(
            (EventLogNode.agent_id == agent_id) & (EventLogNode.is_active.is_(True))
        )
        return sorted(nodes, key=lambda node: node.sequence_index)

    async def update_async(self, entity_id: str, values: dict) -> EventLogNode:
        """Update one event node, opening a session first when needed."""
        self._ensure_session()
        return await super().update_async(entity_id, values)

    async def delete_async(self, entity_id: str) -> None:
        """Delete one event node, opening a session first when needed."""
        self._ensure_session()
        await super().delete_async(entity_id)

    async def create_schema_async(self) -> None:
        """Create the tables when they do not exist yet."""
        await self.create_schema()

    async def drop_schema_async(self) -> None:
        """Drop the tables, returning the database to an empty state."""
        await self.drop_schema()