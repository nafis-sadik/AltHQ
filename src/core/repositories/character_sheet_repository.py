"""Concrete repository for character reference sheet records."""

from typing import List, Optional

from core.db_engine import attach_sqlite_pragmas
from core.dtos.db_entities import CharacterSheet
from core.repositories.db_sql_repo.sql_alchemy_repository import SQLAlchemyRepository


class CharacterSheetRepository(SQLAlchemyRepository[CharacterSheet]):
    """CRUD repository for the ``character_sheets`` table on a WAL-enabled SQLite engine."""

    def __init__(self, db_url: str, echo: bool = False) -> None:
        """Create the async engine via the base class, then attach WAL pragmas to it."""
        super().__init__(CharacterSheet, db_url, echo)
        attach_sqlite_pragmas(self._engine)

    def _ensure_session(self) -> None:
        """Open a session lazily when the repository is used outside 'async with'."""
        if self._session is None:
            self._session = self._session_factory()

    async def __aenter__(self) -> "CharacterSheetRepository":
        """Reuse or open the session so long-lived callers share one session."""
        self._ensure_session()
        return self

    async def get_by_agent_async(self, agent_id: str) -> List[CharacterSheet]:
        """Return every sheet uploaded for the given agent, newest first."""
        self._ensure_session()
        return list(
            reversed(
                await self.get_by_expression_async(
                    CharacterSheet.agent_id == agent_id
                )
            )
        )

    async def get_async(self, entity_id: str) -> Optional[CharacterSheet]:
        """Fetch one sheet record by id, opening a session first when needed."""
        self._ensure_session()
        return await super().get_async(entity_id)

    async def insert_async(self, entity) -> CharacterSheet:
        """Insert a sheet record, or build one first when given a values dict."""
        if not isinstance(entity, CharacterSheet):
            entity = CharacterSheet(**entity)
        self._ensure_session()
        return await super().insert_async(entity)

    async def delete_async(self, entity_id: str) -> None:
        """Delete one sheet record, opening a session first when needed."""
        self._ensure_session()
        await super().delete_async(entity_id)
