"""Framework-independent persona state machine for the agent's identity and prompt limits."""

from typing import Any, List, Optional

import uuid

from business.model_validation import (
    ValidatePersona as validate_persona_update,
)
from business.persona.IPersonaService import IPersonaService
from business.persona.repository_protocols import IRuntimeConfig
from core.dtos.db_entities import Agent, Gender
from core.dtos.persona_vm import (
    PersonaPage,
    PersonaPromptSegments,
    PersonaUpdate,
    PersonaValidationResult,
)
from core.repositories.db_sql_repo.sql_repository import ISQLRepository


class PersonaService(IPersonaService):
    """Pure-Python persona manager; persistence is reached only via the injected repository."""

    def __init__(self, persona_repository: ISQLRepository[Agent], config: IRuntimeConfig) -> None:
        """Store the injected dependencies without importing any storage framework."""
        self._persona_repository = persona_repository
        self._config = config

    async def AddNewAsync(self, update: PersonaUpdate) -> PersonaUpdate:
        """Validate a persona draft, apply creation defaults, then persist an Agent entity."""
        result = self.ValidatePersona(update)

        if not result.valid:
            raise ValueError("; ".join(result.errors))

        entity: Agent = update.to_entity()
        entity.id = str(uuid.uuid4())

        await self._persona_repository.insert_async(entity)

        update.id = entity.id
        return update

    async def UpdateExistingAsync(self, agent_id: str, update: PersonaUpdate) -> PersonaUpdate:
        """Validate an update and apply it to the stored persona through the repository."""
        result: PersonaValidationResult = self.ValidatePersona(update)

        if not result.valid:
            raise ValueError("; ".join(result.errors))

        if not result.normalized.has_changes():
            raise ValueError("update contains no persona changes.")

        try:
            entity = await self._persona_repository.update_async(agent_id, result.normalized.to_dict())
            return PersonaUpdate.to_dto(entity)
        except ValueError as missing:
            raise LookupError("Persona not found.") from missing

    async def GetPagedPersona(self, page: int = 1, page_size: int = 20) -> PersonaPage:
        """Return a page of personas ordered by name along with paging totals."""
        paged = PersonaPage(
            page_number=page,
            page_length=page_size,
            has_create_access=True,
            has_update_access=True,
            has_delete_access=True,
        )

        query = self._persona_repository.base_query()
        if paged.search_string:
            query = query.where(Agent.name.ilike(f"%{paged.search_string}%"))

        paged.total_items = await self._persona_repository.count_async(query)
        ordered = query.order_by(Agent.name).offset(paged.skip).limit(
            paged.page_length
        )
        entities = (
                await self._persona_repository.execute_query_async(ordered)
            ).scalars().all()

        paged.source_data = [
            PersonaUpdate(
                id=item.id,
                name=item.name,
                gender=item.gender,
                profile_picture=item.profile_picture,
                bio=item.bio,
                background_story=item.background_story,
                active_node_limit=item.active_node_limit,
            )
            for item in entities
        ]

        return paged

    async def GetByIdAsync(self, agent_id: Optional[str] = None) -> Optional[Agent]:
        """Return one persona row, resolving the default persona when no id is given."""
        if agent_id is not None:
            return await self._persona_repository.get_async(agent_id)
        return None  # Default persona resolution can be implemented here if needed

    def ValidatePersona(self, update: PersonaUpdate) -> PersonaValidationResult:
        """Validate and normalize an incoming persona update without touching storage."""
        return validate_persona_update(update)

    def CompilePromptSegments(self, persona: Agent) -> PersonaPromptSegments:
        """Compile a stored persona row into prompt segments for prompt assembly."""
        return PersonaPromptSegments(
            identity=f"{persona.name} ({persona.gender})",
            bio=persona.bio,
            background_story=persona.background_story,
            active_node_limit=persona.active_node_limit,
            # recent_messages=persona.recent_messages,
            # vector_search_results=persona.vector_search_results,
        )

    async def CompileBasePrompt(self) -> PersonaPromptSegments:
        """Load the default persona and compile its prompt segments in one step."""
        persona = await self.GetByIdAsync(None)
        if persona is None:
            raise LookupError("no persona has been created yet.")
        return self.CompilePromptSegments(persona)