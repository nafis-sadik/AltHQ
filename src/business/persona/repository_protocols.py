"""Framework-independent repository contracts owned by the business layer (no Layer 3 imports)."""

from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol, runtime_checkable


class IPersonaRepository(ABC):
    """Contract the business layer uses to reach persona persistence.

    Implemented structurally by Layer 3's ``AgentRepository``; defined here so
    business logic never imports SQLAlchemy or any Layer 3 storage module.
    """

    @abstractmethod
    def insert_async(self, entity: Any) -> Any:
        """Insert a new persona row and return it with refreshed state."""
        ...

    @abstractmethod
    def create_schema_async(self) -> Any:
        """Create the persistence schema when it does not exist yet."""
        ...

    @abstractmethod
    def get_async(self, entity_id: str) -> Optional[Any]:
        """Fetch the persona row with the given id, or None if it does not exist."""
        ...

    @abstractmethod
    def get_all_async(self) -> Any:
        """Return every persona row in the table."""
        ...

    @abstractmethod
    def update_async(self, entity_id: str, values: dict) -> Any:
        """Update the persona row with the given id and return the updated row."""
        ...

    @abstractmethod
    def delete_async(self, entity_id: str) -> None:
        """Delete the persona row with the given id."""
        ...


class ICharacterSheetRepository(ABC):
    """Contract for reading and removing stored character reference sheet records."""

    @abstractmethod
    def get_by_agent_async(self, agent_id: str) -> Any:
        """Return every sheet uploaded for the given agent, newest first."""
        ...

    @abstractmethod
    def get_async(self, entity_id: str) -> Optional[Any]:
        """Fetch one sheet record by id, or None when absent."""
        ...

    @abstractmethod
    def insert_async(self, entity: Any) -> Any:
        """Insert a sheet record (entity or values dict) and return it."""
        ...

    @abstractmethod
    def delete_async(self, entity_id: str) -> None:
        """Delete one sheet record."""
        ...


class IFileStorage(ABC):
    """Contract for raw file persistence used by uploads and generated images."""

    @abstractmethod
    def save_bytes(self, original_filename: str, data: bytes) -> str:
        """Persist raw bytes and return the generated stored filename."""
        ...

    @abstractmethod
    def open(self, filename: str) -> Optional[bytes]:
        """Return stored bytes for a filename, or None when absent."""
        ...

    @abstractmethod
    def delete(self, filename: str) -> None:
        """Remove the stored file if present."""
        ...


class IImageProvider(ABC):
    """Strategy contract for profile picture generation (plug-n-play later)."""

    @abstractmethod
    def generate_async(self, agent_id: str, sheet: Any) -> str:
        """Generate a profile picture for the agent and return its stored filename."""
        ...


@runtime_checkable
class IRuntimeConfig(Protocol):
    """Structural contract for runtime configuration access used by business services.

    Satisfied structurally by Layer 3's ``JsonConfigRepository``.
    """

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return the value stored under a dotted key path, or default when absent."""
        ...
