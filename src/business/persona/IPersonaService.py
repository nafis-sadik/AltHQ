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
        """Return one persona row, resolving the default persona when no id is given."""
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
        """Load the default persona and compile its prompt segments in one step."""
        ...
