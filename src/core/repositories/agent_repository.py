"""Agent-specific facade over an injected generic agent repository."""

from typing import Any, List, Optional

from sqlalchemy import case

from core.dtos.db_entities import Agent
from core.repositories.db_sql_repo.sql_repository import ISQLRepository


class AgentRepository:
    """Expose active-agent selection over generic SQL repository operations."""

    def __init__(self, repository: ISQLRepository[Agent]) -> None:
        """Store the injected generic agent repository."""
        self._repository = repository

    async def insert_async(self, entity: Agent) -> Agent:
        return await self._repository.insert_async(entity)

    async def bulk_insert_async(self, entities: List[Agent]) -> List[Agent]:
        return await self._repository.bulk_insert_async(entities)

    async def get_async(self, entity_id: str) -> Optional[Agent]:
        return await self._repository.get_async(entity_id)

    async def get_all_async(self) -> List[Agent]:
        return await self._repository.get_all_async()

    async def update_async(self, entity_id: str, values: dict) -> Agent:
        return await self._repository.update_async(entity_id, values)

    async def update_by_expression_async(
        self,
        criterion: Any,
        values: dict,
    ) -> List[Agent]:
        return await self._repository.update_by_expression_async(criterion, values)

    async def delete_async(self, entity_id: str) -> None:
        return await self._repository.delete_async(entity_id)

    def base_query(self) -> Any:
        return self._repository.base_query()

    async def count_async(self, query: Any) -> int:
        return await self._repository.count_async(query)

    async def execute_query_async(self, query: Any) -> Any:
        return await self._repository.execute_query_async(query)

    async def get_active_async(self) -> Optional[Agent]:
        """Return the persisted active agent, or None when none has been selected."""
        agents = await self._repository.get_all_async()
        return next((agent for agent in agents if agent.is_active), None)

    async def set_active_async(self, agent_id: str) -> Agent:
        """Persist the requested agent as the only active agent using generic updates."""
        target = await self._repository.get_async(agent_id)
        if target is None:
            raise LookupError("Persona not found.")

        updated_agents = await self._repository.update_by_expression_async(
            Agent.id.is_not(None),
            {
                "is_active": case(
                    (Agent.id == agent_id, True),
                    else_=False,
                )
            },
        )
        return next(
            agent
            for agent in updated_agents
            if str(agent.id) == str(agent_id)
        )
