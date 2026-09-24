from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.dtos.db_entities import Agent, Gender
from core.dtos.paged_vm import PagedModel


@dataclass(frozen=True)
class PersonaPromptSegments:
    """Immutable prompt segments compiled from the agent's persona state."""

    identity: str
    bio: str
    background_story: str
    active_node_limit: int

    recent_messages: Optional[List[str]] = field(default_factory=list)
    vector_search_results: Optional[List[str]] = field(default_factory=list)

    def as_prompt_blocks(self) -> List[str]:
        """Return the persona as ordered prompt blocks ready for LLM prompt assembly."""
        return [
            f"[IDENTITY]\n{self.identity}",
            f"[BIO]\n{self.bio}",
            f"[BACKGROUND STORY]\n{self.background_story}",
        ]


@dataclass
class PersonaUpdate:
    """Incoming persona changes before validation; None fields are left untouched."""

    id: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[Gender] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    background_story: Optional[str] = None
    active_node_limit: Optional[int] = None

    def has_changes(self) -> bool:
        """Return True if any of the fields are non-None, indicating a change."""
        return any(
            field is not None
            for field in [
                self.name,
                self.gender,
                self.profile_picture,
                self.bio,
                self.background_story,
                self.active_node_limit,
            ]
        )

    def to_entity(self) -> Agent:
        """Return a new Agent entity with the non-None fields from this update."""
        return Agent(
            name=self.name,
            gender=self.gender,
            profile_picture=self.profile_picture,
            bio=self.bio,
            background_story=self.background_story,
            active_node_limit=self.active_node_limit,
        )

    @staticmethod
    def to_dto(entity: Agent) -> PersonaUpdate:
        """Return a PersonaUpdate DTO from an Agent entity."""
        return PersonaUpdate(
            id=entity.id,
            name=entity.name,
            gender=entity.gender,
            profile_picture=entity.profile_picture,
            bio=entity.bio,
            background_story=entity.background_story,
            active_node_limit=entity.active_node_limit,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary of the non-None, editable fields for database update."""
        return {k: v for k, v in self.__dict__.items() if v is not None and k != "id"}


@dataclass
class PersonaValidationResult:
    """Outcome of validating an incoming persona update."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    normalized: PersonaUpdate = field(default_factory=PersonaUpdate)


class PersonaPage(PagedModel[PersonaUpdate]):
    """Paged snapshot of persona records returned by :meth:`IPersonaService.GetPagedPersona`."""
