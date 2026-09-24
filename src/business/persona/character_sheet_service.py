"""Framework-independent character sheet management for persona reference images."""

from datetime import datetime
from typing import Any, List, Optional

from business.persona.repository_protocols import IFileStorage, IImageProvider
from core.dtos.db_entities import CharacterSheet
from core.repositories.db_sql_repo.sql_repository import ISQLRepository

# Upper bound for uploaded sheet images (5 MB).
MAX_SHEET_SIZE_BYTES = 5 * 1024 * 1024

# Content types accepted for character reference sheets.
ALLOWED_CONTENT_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")


class CharacterSheetService:
    """Manages reference sheet uploads and the profile-picture generation workflow."""

    def __init__(
        self,
        sheet_repository: ISQLRepository[CharacterSheet],
        storage: IFileStorage,
        image_provider: IImageProvider,
    ) -> None:
        """Store the injected repository, storage, and image provider strategy."""
        self._sheets = sheet_repository
        self._storage = storage
        self._provider = image_provider

    async def upload_sheet_async(
        self,
        agent_id: str,
        original_filename: str,
        content_type: str,
        data: bytes,
    ) -> CharacterSheet:
        """Validate and persist an uploaded reference sheet for the agent."""
        if not agent_id:
            raise ValueError("agent_id is required.")

        if not original_filename:
            raise ValueError("An image file is required.")

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                "Unsupported image format. Allowed: PNG, JPEG, GIF, WebP."
            )

        if len(data) == 0:
            raise ValueError("The uploaded file is empty.")

        if len(data) > MAX_SHEET_SIZE_BYTES:
            raise ValueError("Sheet images must be 5 MB or smaller.")

        if not self._storage.is_allowed_image(data):
            raise ValueError("File content does not look like a valid image.")

        stored_filename = self._storage.save_bytes(original_filename, data)
        sheet = CharacterSheet(
            agent_id=agent_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
        )

        async with self._sheets:
            return await self._sheets.insert_async(sheet)

    async def list_sheets_async(self, agent_id: str) -> List[CharacterSheet]:
        """Return the agent's uploaded sheets, newest first."""
        return await self._sheets_of_agent_async(agent_id)

    async def open_sheet_async(self, sheet_id: str) -> Optional[bytes]:
        """Return the stored image bytes for a sheet, or None when absent."""
        sheet = await self._get_sheet_async(sheet_id)

        if sheet is None:
            return None

        return self._storage.open(sheet.stored_filename)

    async def delete_sheet_async(self, sheet_id: str) -> None:
        """Remove a sheet's stored file and its database record."""
        sheet = await self._get_sheet_async(sheet_id)

        if sheet is None:
            raise LookupError("Sheet not found.")

        self._storage.delete(sheet.stored_filename)
        async with self._sheets:
            await self._sheets.delete_async(sheet_id)

    async def generate_avatar_async(self, agent_id: str) -> str:
        """Generate a profile picture from the agent's latest sheet via the provider."""
        sheets = await self._sheets_of_agent_async(agent_id)

        if not sheets:
            raise LookupError(
                "Upload a character sheet before generating a profile picture."
            )

        return await self._provider.generate_async(agent_id, sheets[0])

    async def _get_sheet_async(self, sheet_id: str) -> Optional[CharacterSheet]:
        """Fetch one sheet record by id through the injected repository."""
        async with self._sheets:
            return await self._sheets.get_async(sheet_id)

    async def _sheets_of_agent_async(self, agent_id: str) -> List[CharacterSheet]:
        """Return every sheet for the agent, newest first."""
        async with self._sheets:
            sheets = await self._sheets.get_all_async()

        return sorted(
            (sheet for sheet in sheets if str(sheet.agent_id) == str(agent_id)),
            key=lambda sheet: sheet.created_at or datetime.min,
            reverse=True,
        )