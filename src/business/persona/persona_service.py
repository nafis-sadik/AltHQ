"""Framework-independent persona state machine for the agent's identity and prompt limits."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from business.persona.repository_protocols import IPersonaRepository, IRuntimeConfig

BIO_MAX_LENGTH = 500
NAME_MAX_LENGTH = 100
GENDER_MAX_LENGTH = 30
PROFILE_PICTURE_MAX_LENGTH = 500

# Canonical persona genders; the UI renders them as a fixed dropdown and the
# service re-validates every submission against this tuple.
GENDER_OPTIONS = ("male", "female", "unspecified")
GENDER_LABELS = {
    "male": "Male",
    "female": "Female",
    "unspecified": "Unspecified",
}

# Letters, numbers, spaces, hyphens, and apostrophes; must start with a word character.
_NAME_PATTERN = re.compile(r"^[\w][\w\s\-']*$", re.UNICODE)


@dataclass(frozen=True)
class PersonaPromptSegments:
    """Immutable prompt segments compiled from the agent's persona state."""

    identity: str
    bio: str
    background_story: str
    active_node_limit: int

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

    name: Optional[str] = None
    gender: Optional[str] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    background_story: Optional[str] = None
    active_node_limit: Optional[int] = None

    def has_changes(self) -> bool:
        """Return True when at least one field carries a change."""
        return any(value is not None for value in vars(self).values())

    def to_repository_values(self) -> Dict[str, Any]:
        """Convert validated persona changes into repository column values."""
        return {key: value for key, value in vars(self).items() if value is not None}


@dataclass
class PersonaValidationResult:
    """Outcome of validating an incoming persona update."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    normalized: Optional[PersonaUpdate] = None


class PersonaService:
    """Pure-Python persona manager; persistence is reached only via the injected repository."""

    def __init__(self, repository: IPersonaRepository, config: IRuntimeConfig) -> None:
        """Store the injected dependencies without importing any storage framework."""
        self._repository = repository
        self._config = config

    async def create_persona(self, update: PersonaUpdate) -> Any:
        """Validate a persona draft, then persist it via a plain values dict (no Layer 3 DTOs)."""
        result = self.validate_update(update)

        if not result.valid:
            raise ValueError("; ".join(result.errors))

        defaults = {
            "name": "Unnamed Agent",
            "gender": "unspecified",
            "profile_picture": "__placeholder__",
            "bio": "No bio provided yet.",
            "background_story": "No background story provided yet.",
            "active_node_limit": int(self._config.get("persona.max_active_node_limit", 20)),
        }
        defaults.update(result.normalized.to_repository_values())

        return await self._repository.insert_async(defaults)

    async def get_persona(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """Return the persona row, resolving the default persona when no id is given."""
        if agent_id is not None:
            return await self._repository.get_async(agent_id)

        return await self._get_default_persona()

    async def list_personas_async(self) -> List[Any]:
        """Return all available agents for the dashboard's agent switcher."""
        personas = await self._repository.get_all_async()
        return sorted(
            personas,
            key=lambda persona: (str(persona.name).casefold(), str(persona.id)),
        )

    def validate_update(self, update: PersonaUpdate) -> PersonaValidationResult:
        """Validate and normalize an incoming persona update without touching storage."""
        errors: List[str] = []
        normalized = PersonaUpdate()

        if update.name is not None:
            name = update.name.strip()
            if not name:
                errors.append("name must not be blank.")
            elif len(name) > NAME_MAX_LENGTH:
                errors.append(f"name must not exceed {NAME_MAX_LENGTH} characters.")
            elif not _NAME_PATTERN.match(name):
                errors.append(
                    "name may only contain letters, numbers, spaces, hyphens, and apostrophes."
                )
            else:
                normalized.name = name

        if update.gender is not None:
            gender = update.gender.strip().lower()
            if not gender:
                errors.append("gender must not be blank.")
            elif len(gender) > GENDER_MAX_LENGTH:
                errors.append(f"gender must not exceed {GENDER_MAX_LENGTH} characters.")
            elif gender not in GENDER_OPTIONS:
                allowed = ", ".join(GENDER_LABELS[label] for label in GENDER_OPTIONS)
                errors.append(f"gender must be one of: {allowed}.")
            else:
                normalized.gender = gender

        if update.profile_picture is not None:
            profile_picture = update.profile_picture.strip()
            if not profile_picture:
                errors.append("profile_picture must not be blank.")
            elif len(profile_picture) > PROFILE_PICTURE_MAX_LENGTH:
                errors.append(
                    f"profile_picture must not exceed {PROFILE_PICTURE_MAX_LENGTH} characters."
                )
            else:
                normalized.profile_picture = profile_picture

        if update.bio is not None:
            bio = update.bio.strip()
            if not bio:
                errors.append("bio must not be blank.")
            elif len(bio) > BIO_MAX_LENGTH:
                errors.append(f"bio must not exceed {BIO_MAX_LENGTH} characters.")
            else:
                normalized.bio = bio

        if update.background_story is not None:
            background_story = update.background_story.strip()
            if not background_story:
                errors.append("background_story must not be blank.")
            else:
                normalized.background_story = background_story

        if update.active_node_limit is not None:
            limit = update.active_node_limit
            if isinstance(limit, bool) or not isinstance(limit, int):
                errors.append("active_node_limit must be an integer.")
            elif limit < 1:
                errors.append("active_node_limit must be at least 1.")
            else:
                normalized.active_node_limit = limit

        return PersonaValidationResult(valid=not errors, errors=errors, normalized=normalized)

    async def update_persona(self, agent_id: str, update: PersonaUpdate) -> Any:
        """Validate an update and apply it to the stored persona through the repository."""
        result = self.validate_update(update)

        if not result.valid:
            raise ValueError("; ".join(result.errors))

        if not result.normalized.has_changes():
            raise ValueError("update contains no persona changes.")

        return await self._repository.update_async(
            agent_id,
            result.normalized.to_repository_values(),
        )

    def compile_prompt_segments(self, persona: Any) -> PersonaPromptSegments:
        """Compile a stored persona row into prompt segments for prompt assembly."""
        return PersonaPromptSegments(
            identity=f"{persona.name} ({persona.gender})",
            bio=persona.bio,
            background_story=persona.background_story,
            active_node_limit=persona.active_node_limit,
        )

    async def compile_base_prompt(self) -> PersonaPromptSegments:
        """Load the default persona and compile its prompt segments in one step."""
        persona = await self._get_default_persona()

        if persona is None:
            raise LookupError("no persona has been created yet.")

        return self.compile_prompt_segments(persona)

    async def _get_default_persona(self) -> Optional[Any]:
        """Return the first persona row, or None when no persona exists yet."""
        rows = await self._repository.get_all_async()
        return rows[0] if rows else None
