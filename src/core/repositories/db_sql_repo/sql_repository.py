"""Abstract async SQL repository interface for CRUD operations on a generic entity type."""

from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, Sequence, TypeVar

TEntity = TypeVar("TEntity")

class ISQLRepository(ABC, Generic[TEntity]):
    """Contract that every async SQL-backed repository must implement."""

    @abstractmethod
    async def insert_async(self, entity: TEntity) -> TEntity:
        """Insert a new entity and return it with refreshed state."""
        pass

    @abstractmethod
    async def bulk_insert_async(self, entities: List[TEntity]) -> List[TEntity]:
        """Insert several entities in a single transaction and return them refreshed."""
        pass

    @abstractmethod
    async def get_async(self, entity_id: str) -> Optional[TEntity]:
        """Fetch the entity with the given id, or None if it does not exist."""
        pass

    @abstractmethod
    async def get_by_expression_async(self, criterion: Any) -> Sequence[TEntity]:
        """Fetch every entity matching the given SQLAlchemy criterion."""
        pass

    @abstractmethod
    async def get_all_async(self) -> List[TEntity]:
        """Return every entity in the table."""
        pass

    @abstractmethod
    async def update_async(self, entity_id: str, values: dict) -> TEntity:
        """Update the entity with the given id using the provided values and return it."""
        pass

    @abstractmethod
    async def update_by_expression_async(self, criterion: Any, values: dict) -> List[TEntity]:
        """Update every entity matching the criterion and return the updated rows."""
        pass

    @abstractmethod
    async def delete_async(self, entity_id: str) -> None:
        """Delete the entity with the given id."""
        pass