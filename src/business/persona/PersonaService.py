"""Framework-independent persona state machine for the agent's identity and prompt limits."""

from typing import Any, List, Optional

from business.model_validation import (
    ValidatePersona as validate_persona_update,
)
from business.persona.IPersonaService import IPersonaService
from business.persona.repository_protocols import IPersonaRepository, IRuntimeConfig
from core.dtos.persona_vm import (
    PersonaPage,
    PersonaPromptSegments,
    PersonaUpdate,
    PersonaValidationResult,
)

DEFAULT_GENDER = "prefer_not_to_say"
DEFAULT_ACTIVE_NODE_LIMIT = 20


class PersonaService(IPersonaService):
    """Pure-Python persona manager; persistence is reached only via the injected repository."""

    def __init__(
        self,
        persona_repository: IPersonaRepository,
        config: IRuntimeConfig,
    ) -> None:
        """Store the injected dependencies without importing any storage framework."""
        self._persona_repository = persona_repository
        self._config = config

    async def AddNewAsync(self, update: PersonaUpdate) -> PersonaUpdate:
        """Validate a persona draft, apply creation defaults, then persist an Agent entity."""
        result = self.ValidatePersona(update)

        if not result.valid:
            raise ValueError("; ".join(result.errors))
        if result.normalized.name is None:
            raise ValueError("name must not be blank.")
        if result.normalized.bio is None:
            raise ValueError("bio must not be blank.")

        max_node_limit = self._config.get(
            "persona.max_active_node_limit",
            self._config.get("default_active_node_limit", DEFAULT_ACTIVE_NODE_LIMIT),
        )
        try:
            max_node_limit = int(max_node_limit)
        except (TypeError, ValueError):
            max_node_limit = DEFAULT_ACTIVE_NODE_LIMIT
        if max_node_limit < 1:
            max_node_limit = DEFAULT_ACTIVE_NODE_LIMIT

        active_node_limit = result.normalized.active_node_limit or max_node_limit
        entity = PersonaUpdate(
            name=result.normalized.name,
            gender=result.normalized.gender or DEFAULT_GENDER,
            profile_picture=result.normalized.profile_picture or "",
            bio=result.normalized.bio,
            background_story=result.normalized.background_story or "",
            active_node_limit=min(active_node_limit, max_node_limit),
        ).to_entity()

        entity = await self._persona_repository.insert_async(entity)

        return PersonaUpdate.to_dto(entity)

    async def UpdateExistingAsync(
        self,
        agent_id: str,
        update: PersonaUpdate,
    ) -> PersonaUpdate:
        """Validate an update and apply it to the stored persona through the repository."""
        result: PersonaValidationResult = self.ValidatePersona(update)

        if not result.valid:
            raise ValueError("; ".join(result.errors))

        if not result.normalized.has_changes():
            raise ValueError("update contains no persona changes.")

        try:
            entity = await self._persona_repository.update_async(
                agent_id,
                result.normalized.to_dict(),
            )
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
        entities = await self.list_agents_async()

        if paged.search_string:
            search = paged.search_string.casefold()
            entities = [
                entity
                for entity in entities
                if search in str(entity.name).casefold()
            ]

        paged.total_items = len(entities)
        paged.source_data = [
            PersonaUpdate.to_dto(entity)
            for entity in entities[paged.skip:paged.skip + paged.page_length]
        ]
        return paged

    async def GetByIdAsync(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """Return one persona row, resolving the active agent when no id is given."""
        if agent_id is None:
            return await self.get_active_async()

        return await self._persona_repository.get_async(agent_id)

    async def get_active_async(self) -> Optional[Any]:
        """Return the persisted active agent, or None when none is selected."""
        return await self._persona_repository.get_active_async()

    async def set_active_async(self, agent_id: str) -> Any:
        """Atomically persist one agent as active and return it."""
        return await self._persona_repository.set_active_async(agent_id)

    async def list_agents_async(self) -> List[Any]:
        """Return every persona sorted by case-insensitive name and stable id."""
        entities = await self._persona_repository.get_all_async()
        return sorted(
            entities,
            key=lambda entity: (str(entity.name).casefold(), str(entity.id)),
        )

    def ValidatePersona(self, update: PersonaUpdate) -> PersonaValidationResult:
        """Validate and normalize an incoming persona update without touching storage."""
        return validate_persona_update(update)

    def CompilePromptSegments(self, persona: Any) -> PersonaPromptSegments:
        """Compile a stored persona row into prompt segments for prompt assembly."""
        return PersonaPromptSegments(
            identity=f"{persona.name} ({persona.gender})",
            bio=persona.bio,
            background_story=persona.background_story,
            active_node_limit=persona.active_node_limit,
        )

    async def CompileBasePrompt(self) -> PersonaPromptSegments:
        """Load the active agent and compile its prompt segments in one step."""
        persona = await self.GetByIdAsync(None)
        if persona is None:
            raise LookupError("no persona has been created yet.")
        return self.CompilePromptSegments(persona)
