"""Concrete repository for the Agent entity, reusing the generic async SQLAlchemy repository."""

from typing import Any, Optional

from core.db_engine import attach_sqlite_pragmas
from core.dtos.db_entities import Agent
from core.repositories.db_sql_repo.sql_alchemy_repository import SQLAlchemyRepository


class AgentRepository(SQLAlchemyRepository[Agent]):
    """CRUD repository for the ``agents`` table backed by a WAL-enabled SQLite engine."""

    def __init__(self, db_url: str, echo: bool = False) -> None:
        """Create the async engine via the base class, then attach WAL pragmas to it."""
        super().__init__(
            Agent,
            db_url,
            echo,
        )
        attach_sqlite_pragmas(self._engine)

    def _ensure_session(self) -> None:
        """Open a session lazily when the repository is used outside 'async with'."""
        if self._session is None:
            self._session = self._session_factory()

    async def __aenter__(self) -> "AgentRepository":
        """Reuse or open the session so long-lived callers share one session."""
        self._ensure_session()
        return self

    async def insert_async(self, entity: Any) -> Agent:
        """Insert an Agent entity, or build one first when given a plain values dict."""
        if not isinstance(entity, Agent):
            entity = Agent(**entity)

        self._ensure_session()
        return await super().insert_async(entity)

    async def get_async(self, entity_id: str) -> Optional[Agent]:
        """Fetch one agent by id, opening a session first when needed."""
        self._ensure_session()
        return await super().get_async(entity_id)

    async def get_all_async(self) -> list:
        """Fetch every agent, opening a session first when needed."""
        self._ensure_session()
        return await super().get_all_async()

    async def update_async(self, entity_id: str, values: dict) -> Agent:
        """Update one agent, opening a session first when needed."""
        self._ensure_session()
        return await super().update_async(entity_id, values)

    async def delete_async(self, entity_id: str) -> None:
        """Delete one agent, opening a session first when needed."""
        self._ensure_session()
        return await super().delete_async(entity_id)

    async def create_schema_async(self) -> None:
        """Create the agents table when it does not exist yet."""
        await self.create_schema()

    async def get_default_agent_async(self) -> Optional[Agent]:
        """Return the single persona row, or None when the agents table is still empty."""
        agents = await self.get_all_async()

        if not agents:
            return None

        return agents[0]
