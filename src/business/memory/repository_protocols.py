"""Framework-independent repository contracts owned by the memory business layer (no Layer 3 imports)."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class IEventLogRepository(ABC):
    """Contract the memory layer uses to reach event node persistence.

    Implemented structurally by Layer 3's ``EventLogRepository``; defined here so
    business logic never imports SQLAlchemy or any Layer 3 storage module.
    """

    @abstractmethod
    async def create_schema_async(self) -> Any:
        """Create the persistence schema when it does not exist yet."""
        ...

    @abstractmethod
    async def insert_async(self, entity: Any) -> Any:
        """Insert a new event node and return it with refreshed state."""
        ...

    @abstractmethod
    async def get_async(self, entity_id: str) -> Optional[Any]:
        """Fetch the event node with the given id, or None if it does not exist."""
        ...

    @abstractmethod
    async def get_timeline_async(self, agent_id: str) -> List[Any]:
        """Return every event node for the agent, oldest sequence first."""
        ...

    @abstractmethod
    async def get_active_by_agent_async(self, agent_id: str) -> List[Any]:
        """Return the agent's active event nodes, oldest sequence first."""
        ...

    @abstractmethod
    async def update_async(self, entity_id: str, values: dict) -> Any:
        """Update the event node with the given id and return the updated row."""
        ...

    async def delete_if_empty_async(self, entity_id: str) -> bool:
        """Delete an event node only when no messages are attached to it."""
        ...

    async def delete_async(self, entity_id: str) -> None:
        """Delete an event node after the empty-node guard succeeds."""
        ...


class IMessageRepository(ABC):
    """Contract for persistence of dialogue messages attached to event nodes."""

    @abstractmethod
    async def insert_async(self, entity: Any) -> Any:
        """Insert a new message and return it with refreshed state."""
        ...

    @abstractmethod
    async def get_async(self, entity_id: str) -> Optional[Any]:
        """Fetch one message by id, or None when it does not exist."""
        ...

    @abstractmethod
    async def get_by_node_async(self, node_id: str) -> List[Any]:
        """Return every message attached to the node in explicit sequence order."""
        ...

    @abstractmethod
    async def update_async(self, entity_id: str, values: dict) -> Any:
        """Update the message with the given id and return the updated row."""
        ...

    @abstractmethod
    async def delete_async(self, entity_id: str) -> None:
        """Delete one message."""
        ...