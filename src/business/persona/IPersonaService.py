from abc import ABC, abstractmethod
from typing import Any, List, Optional

from core.dtos.persona_vm import PersonaPage, PersonaPromptSegments, PersonaUpdate, PersonaValidationResult


class IPersonaService(ABC):
    """Domain contract the persona service exposes to Layer 1 controllers.

    Declared here (and not in the app layer) so the presentation layer depends
    only on this abstraction while the concrete ``PersonaService`` implements it.
    """

    @abstractmethod
    async def AddNewAsync(self, update: PersonaUpdate) -> PersonaUpdate:
        """Validate and persist a new persona from an incoming update."""
        ...

    @abstractmethod
    async def UpdateExistingAsync(self, agent_id: str, update: PersonaUpdate) -> PersonaUpdate:
        """Validate and apply persona changes to an existing agent."""
        ...

    @abstractmethod
    async def GetPagedPersona(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> PersonaPage:
        """Return a page of personas ordered by name plus paging totals."""
        ...

    @abstractmethod
    async def GetByIdAsync(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """Return one persona row, resolving the active agent when no id is given."""
        ...

    @abstractmethod
    async def get_active_async(self) -> Optional[Any]:
        """Return the persisted active agent, or None when none is selected."""
        ...

    @abstractmethod
    async def set_active_async(self, agent_id: str) -> Any:
        """Atomically persist one agent as active and return it."""
        ...

    @abstractmethod
    async def list_agents_async(self) -> List[Any]:
        """Return every persona sorted by name for agent selection UIs."""
        ...

    @abstractmethod
    def ValidatePersona(self, update: PersonaUpdate) -> PersonaValidationResult:
        """Validate and normalize an incoming persona update without touching storage."""
        ...

    @abstractmethod
    def CompilePromptSegments(self, persona: Any) -> PersonaPromptSegments:
        """Compile a stored persona row into prompt segments for prompt assembly."""
        ...

    @abstractmethod
    async def CompileBasePrompt(self) -> PersonaPromptSegments:
        """Load the active agent and compile its prompt segments in one step."""
        ...
