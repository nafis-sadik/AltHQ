"""Abstract NoSQL repository interface for CRUD operations on a generic entity type."""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


class INoSQLRepository(ABC, Generic[T]):
    """Contract that every NoSQL-backed repository must implement."""

    @abstractmethod
    def add(self, entity_id: str, entity: T) -> None:
        """Insert a new entity under the given id."""
        pass

    @abstractmethod
    def get(self, entity_id: str) -> Optional[T]:
        """Fetch the entity with the given id, or None if it does not exist."""
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """Return every entity stored in the collection."""
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> None:
        """Remove the entity with the given id, if present."""
        pass

    @abstractmethod
    def update(self, entity_id: str, entity: T) -> None:
        """Replace the entity stored under the given id with the new entity."""
        pass