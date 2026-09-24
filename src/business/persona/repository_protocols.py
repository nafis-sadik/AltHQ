"""Framework-independent collaborator contracts owned by the business layer (no Layer 3 imports)."""

from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol, runtime_checkable


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
