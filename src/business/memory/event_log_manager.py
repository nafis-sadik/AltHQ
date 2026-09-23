"""Framework-independent long-term memory manager for the agent's event timeline.

Persistence is reached only through the injected ``IEventLogRepository`` and
``IMessageRepository`` contracts, so Layer 2 stays free of database frameworks.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from business.memory.memory_window_service import (
    BudgetedMemoryWindow,
    MemoryWindow,
    MemoryWindowService,
)
from business.memory.repository_protocols import (
    IEventLogRepository,
    IMessageRepository,
)

# Fallback active node limit used when the persona row does not expose one.
DEFAULT_ACTIVE_NODE_LIMIT = 20


@dataclass
class TimelineEntry:
    """Immutable plain-data view of one event node plus its attached messages."""

    id: str
    agent_id: str
    sequence_index: int
    summary: str
    timestamp: Any
    is_active: bool
    messages: List[Any] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the node and its messages as plain dictionaries."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "sequence_index": self.sequence_index,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "is_active": self.is_active,
            "messages": [
                message.to_dict() if hasattr(message, "to_dict") else message
                for message in self.messages
            ],
        }


class EventLogManager:
    """Manages the time-series event graph without importing any storage framework."""

    def __init__(
        self,
        event_repository: IEventLogRepository,
        message_repository: IMessageRepository,
        agent_repository: Optional[Any] = None,
    ) -> None:
        """Store the injected repositories; the agent repo stays optional for default lookup."""
        self._events = event_repository
        self._messages = message_repository
        self._agents = agent_repository
        self._memory_window = MemoryWindowService(event_repository)
        self._cache_invalidators: List[Callable[[], None]] = []

    def add_cache_invalidator(self, callback: Callable[[], None]) -> None:
        """Register a hook that forces prompt recompilation when history changes.

        Layer 1 prompt compilers subscribe here; the hook fires silently so the
        agent's next execution loop rebuilds its active prompt window.
        """
        self._cache_invalidators.append(callback)

    async def invalidate_prompt_cache(self) -> None:
        """Notify every registered observer that the compiled prompt is stale."""
        for callback in self._cache_invalidators:
            callback()

    async def list_timeline_async(self, agent_id: Optional[str] = None) -> List[TimelineEntry]:
        """Return the agent's event timeline with attached messages, oldest first."""
        agent_id = agent_id or await self._resolve_default_agent_id()

        nodes = await self._events.get_timeline_async(agent_id)
        entries: List[TimelineEntry] = []

        for node in nodes:
            messages = await self._messages.get_by_node_async(node.id)
            entries.append(
                TimelineEntry(
                    id=node.id,
                    agent_id=node.agent_id,
                    sequence_index=node.sequence_index,
                    summary=node.summary,
                    timestamp=node.timestamp,
                    is_active=node.is_active,
                    messages=messages,
                )
            )

        return entries

    async def append_node_async(
        self,
        summary: str,
        agent_id: Optional[str] = None,
        is_active: bool = True,
    ) -> TimelineEntry:
        """Append a new event node at the end of the agent's timeline."""
        if not summary or not summary.strip():
            raise ValueError("summary must not be blank.")

        agent_id = agent_id or await self._resolve_default_agent_id()

        node = await self._events.insert_async(
            {
                "agent_id": agent_id,
                "summary": summary.strip(),
                "is_active": is_active,
            }
        )
        return TimelineEntry(
            id=node.id,
            agent_id=node.agent_id,
            sequence_index=node.sequence_index,
            summary=node.summary,
            timestamp=node.timestamp,
            is_active=node.is_active,
        )

    async def append_message_async(
        self,
        node_id: str,
        sender: str,
        content: str,
    ) -> Any:
        """Attach a dialogue message to an existing event node."""
        if not sender or not str(sender).strip():
            raise ValueError("sender must not be blank.")

        if not content or not str(content).strip():
            raise ValueError("content must not be blank.")

        node = await self._events.get_async(node_id)
        if node is None:
            raise LookupError("Event node not found.")

        return await self._messages.insert_async(
            {
                "node_id": node_id,
                "sender": str(sender).strip(),
                "content": str(content).strip(),
            }
        )

    def _memory_window_limit(self, persona: Any) -> int:
        """Return the persona's active node limit, or the framework default."""
        return int(getattr(persona, "active_node_limit", None) or DEFAULT_ACTIVE_NODE_LIMIT)

    async def get_memory_window_async(self, agent_id: str) -> MemoryWindow:
        """Slice the agent's active memory window using the persona's node limit."""
        persona = await self._agents.get_async(agent_id) if self._agents is not None else None
        return await self._memory_window.get_active_window_async(
            agent_id,
            node_limit=self._memory_window_limit(persona) if persona is not None else None,
        )

    async def get_memory_window_budget_async(
        self,
        agent_id: str,
        token_budget: Optional[int] = None,
    ) -> BudgetedMemoryWindow:
        """Slice the active memory window and estimate its token budget."""
        persona = await self._agents.get_async(agent_id) if self._agents is not None else None
        return await self._memory_window.budget_active_window_async(
            agent_id,
            node_limit=self._memory_window_limit(persona) if persona is not None else None,
            token_budget=token_budget,
        )

    async def silent_edit_node_async(
        self,
        node_id: str,
        summary: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Any:
        """Rewrite a past node silently, without writing audit or edit-marker rows."""
        if summary is not None and not str(summary).strip():
            raise ValueError("summary must not be blank.")

        node = await self._events.get_async(node_id)
        if node is None:
            raise LookupError("Event node not found.")

        values: dict = {}
        if summary is not None:
            values["summary"] = str(summary).strip()
        if is_active is not None:
            values["is_active"] = is_active

        if not values:
            raise ValueError("no edit values provided.")

        updated = await self._events.update_async(node_id, values)
        await self.invalidate_prompt_cache()
        return updated

    async def silent_edit_message_async(
        self,
        message_id: str,
        content: str,
    ) -> Any:
        """Rewrite a past message silently, without writing audit or edit-marker rows."""
        if not content or not str(content).strip():
            raise ValueError("content must not be blank.")

        message = await self._messages.get_async(message_id)
        if message is None:
            raise LookupError("Message not found.")

        updated = await self._messages.update_async(
            message_id,
            {"content": str(content).strip()},
        )
        await self.invalidate_prompt_cache()
        return updated

    async def _resolve_default_agent_id(self) -> str:
        """Return the first persona's id, or raise when no persona exists yet."""
        if self._agents is None:
            raise LookupError("no persona has been created yet.")

        persona = await self._agents.get_default_agent_async()

        if persona is None:
            raise LookupError("no persona has been created yet.")

        return persona.id