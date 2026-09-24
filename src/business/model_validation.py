from typing import List
import re

from core.dtos.db_entities import Gender
from core.dtos.persona_vm import PersonaUpdate, PersonaValidationResult


TEXT_AREA_MAX_LENGTH = 500
TEXT_FIELD_MAX_LENGTH = 100
GENDER_MAX_LENGTH = 30
PROFILE_PICTURE_MAX_LENGTH = 500

# Letters, numbers, spaces, hyphens, and apostrophes; must start with a word character.
_NAME_PATTERN = re.compile(r"^[\w][\w\s\-']*$", re.UNICODE)

def ValidatePersona(update: PersonaUpdate) -> PersonaValidationResult:
    """Validate and normalize an incoming persona update without touching storage."""
    errors: List[str] = []
    normalized = PersonaUpdate()

    if update.name is not None:
        name = update.name.strip()
        if not name:
            errors.append("name must not be blank.")
        elif len(name) > TEXT_FIELD_MAX_LENGTH:
            errors.append(f"name must not exceed {TEXT_FIELD_MAX_LENGTH} characters.")
        elif not _NAME_PATTERN.match(name):
            errors.append(
                "name may only contain letters, numbers, spaces, hyphens, and apostrophes."
            )
        else:
            normalized.name = name

    if update.gender is not None:
        gender = str(update.gender).strip()
        if not gender:
            errors.append("gender must not be blank.")
        elif gender not in Gender:
            allowed = ", ".join(str(label) for label in Gender)
            errors.append(f"gender must be one of: {allowed}.")
        else:
            normalized.gender = Gender(gender)

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
        elif len(bio) > TEXT_AREA_MAX_LENGTH:
            errors.append(f"bio must not exceed {TEXT_AREA_MAX_LENGTH} characters.")
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
