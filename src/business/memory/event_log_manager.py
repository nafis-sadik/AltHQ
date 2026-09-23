"""Framework-independent manager for the chronological Line of Truth timeline."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
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

# A message may only be attributed to the local user or the selected agent.
MESSAGE_SENDER_USER = "user"


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
    """Coordinates explicit node and message operations through injected repositories."""

    def __init__(
        self,
        event_repository: IEventLogRepository,
        message_repository: IMessageRepository,
        agent_repository: Optional[Any] = None,
    ) -> None:
        """Store injected repositories and build the framework-free memory helper."""
        self._events = event_repository
        self._messages = message_repository
        self._agents = agent_repository
        self._memory_window = MemoryWindowService(event_repository)
        self._cache_invalidators: List[Callable[[], None]] = []

    def add_cache_invalidator(self, callback: Callable[[], None]) -> None:
        """Register a hook that recompiles prompt context after timeline changes."""
        self._cache_invalidators.append(callback)

    async def invalidate_prompt_cache(self) -> None:
        """Notify observers that the compiled prompt is stale after an explicit edit."""
        for callback in self._cache_invalidators:
            callback()

    async def list_timeline_async(self, agent_id: Optional[str] = None) -> List[TimelineEntry]:
        """Return every node for the agent in chronological sequence order."""
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

    async def add_node_async(
        self,
        summary: str,
        agent_id: Optional[str] = None,
        is_active: bool = True,
    ) -> TimelineEntry:
        """Append a node; ``is_active`` is an internal prompt-context flag only."""
        if not summary or not summary.strip():
            raise ValueError("summary must not be blank.")

        agent_id = agent_id or await self._resolve_default_agent_id()
        await self._ensure_agent_exists_async(agent_id)

        node = await self._events.insert_async(
            {
                "agent_id": agent_id,
                "summary": summary.strip(),
                "is_active": is_active,
            }
        )
        await self.invalidate_prompt_cache()
        return TimelineEntry(
            id=node.id,
            agent_id=node.agent_id,
            sequence_index=node.sequence_index,
            summary=node.summary,
            timestamp=node.timestamp,
            is_active=node.is_active,
        )

    async def append_node_async(
        self,
        summary: str,
        agent_id: Optional[str] = None,
        is_active: bool = True,
    ) -> TimelineEntry:
        """Backward-compatible name for :meth:`add_node_async`."""
        return await self.add_node_async(summary, agent_id, is_active)

    async def update_node_async(
        self,
        node_id: str,
        summary: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Any:
        """Apply an explicit node summary edit for the selected agent."""
        node = await self._events.get_async(node_id)
        if node is None:
            raise LookupError("Event node not found.")
        await self._assert_node_agent_async(node, agent_id)

        values: dict = {}
        if summary is not None:
            if not str(summary).strip():
                raise ValueError("summary must not be blank.")
            values["summary"] = str(summary).strip()
        if not values:
            raise ValueError("no node edit values provided.")

        updated = await self._events.update_async(node_id, values)
        await self.invalidate_prompt_cache()
        return updated

    async def delete_node_async(
        self,
        node_id: str,
        agent_id: Optional[str] = None,
    ) -> None:
        """Delete an empty node belonging to the selected agent."""
        node = await self._events.get_async(node_id)
        if node is None:
            raise LookupError("Event node not found.")
        await self._assert_node_agent_async(node, agent_id)

        delete_if_empty = getattr(self._events, "delete_if_empty_async", None)
        if delete_if_empty is not None:
            deleted = await delete_if_empty(node_id)
            if not deleted:
                raise ValueError(
                    "A node with messages cannot be deleted. "
                    "Move or delete its messages first."
                )
        else:
            messages = await self._messages.get_by_node_async(node_id)
            if messages:
                raise ValueError(
                    "A node with messages cannot be deleted. "
                    "Move or delete its messages first."
                )
            await self._events.delete_async(node_id)

        await self.invalidate_prompt_cache()

    async def append_message_async(
        self,
        node_id: str,
        sender: str,
        content: str,
        timestamp: Optional[datetime] = None,
        agent_id: Optional[str] = None,
    ) -> Any:
        """Attach a user/agent message to a node with explicit order and time."""
        node = await self._events.get_async(node_id)
        if node is None:
            raise LookupError("Event node not found.")
        effective_agent_id = agent_id or node.agent_id
        await self._assert_node_agent_async(node, effective_agent_id)

        values = {
            "node_id": node_id,
            "sender": self._normalize_sender(sender, effective_agent_id),
            "content": self._normalize_content(content),
            "position": self._next_message_position(
                await self._messages.get_by_node_async(node_id)
            ),
        }
        normalized_timestamp = self._normalize_timestamp(timestamp)
        if normalized_timestamp is not None:
            values["timestamp"] = normalized_timestamp

        message = await self._messages.insert_async(values)
        await self.invalidate_prompt_cache()
        return message

    async def add_message_async(
        self,
        node_id: str,
        sender: str,
        content: str,
        timestamp: Optional[datetime] = None,
        agent_id: Optional[str] = None,
    ) -> Any:
        """Alias for :meth:`append_message_async` using CRUD terminology."""
        return await self.append_message_async(
            node_id,
            sender,
            content,
            timestamp,
            agent_id,
        )

    async def update_message_async(
        self,
        message_id: str,
        sender: Optional[str] = None,
        content: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        node_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Any:
        """Edit a message and optionally move it within the selected agent."""
        message = await self._messages.get_async(message_id)
        if message is None:
            raise LookupError("Message not found.")
        source_node = await self._get_message_node_async(message)
        effective_agent_id = agent_id or source_node.agent_id
        await self._assert_node_agent_async(source_node, effective_agent_id)

        values: dict = {}
        if sender is not None:
            values["sender"] = self._normalize_sender(sender, effective_agent_id)
        if content is not None:
            values["content"] = self._normalize_content(content)
        if timestamp is not None:
            values["timestamp"] = self._normalize_timestamp(timestamp)
        if node_id is not None:
            target_node_id = str(node_id).strip()
            if not target_node_id:
                raise ValueError("node_id must not be blank.")
            if target_node_id != message.node_id:
                target_node = await self._events.get_async(target_node_id)
                if target_node is None:
                    raise LookupError("Target event node not found.")
                await self._assert_node_agent_async(target_node, effective_agent_id)
                values["node_id"] = target_node_id
                values["position"] = self._next_message_position(
                    await self._messages.get_by_node_async(target_node_id)
                )

        if not values:
            if node_id is not None and str(node_id).strip() == message.node_id:
                return message
            raise ValueError("no message edit values provided.")

        updated = await self._messages.update_async(message_id, values)
        await self.invalidate_prompt_cache()
        return updated

    async def move_message_async(
        self,
        message_id: str,
        target_node_id: str,
        agent_id: Optional[str] = None,
    ) -> Any:
        """Move a message to another node belonging to the selected agent."""
        return await self.update_message_async(
            message_id,
            node_id=target_node_id,
            agent_id=agent_id,
        )

    async def move_message_position_async(
        self,
        message_id: str,
        direction: str,
        agent_id: Optional[str] = None,
    ) -> Any:
        """Move a message one position up or down within its current node."""
        normalized_direction = str(direction).strip().lower()
        if normalized_direction not in {"up", "down"}:
            raise ValueError("direction must be 'up' or 'down'.")

        message = await self._messages.get_async(message_id)
        if message is None:
            raise LookupError("Message not found.")
        node = await self._get_message_node_async(message)
        await self._assert_node_agent_async(node, agent_id or node.agent_id)

        ordered = await self._messages.get_by_node_async(message.node_id)
        current_index = next(
            (index for index, item in enumerate(ordered) if item.id == message_id),
            None,
        )
        if current_index is None:
            raise LookupError("Message not found in its node.")

        target_index = current_index - 1 if normalized_direction == "up" else current_index + 1
        if target_index < 0 or target_index >= len(ordered):
            return message

        ordered.insert(target_index, ordered.pop(current_index))
        for position, item in enumerate(ordered):
            if getattr(item, "position", None) != position:
                await self._messages.update_async(item.id, {"position": position})

        await self.invalidate_prompt_cache()
        return await self._messages.get_async(message_id)

    async def delete_message_async(
        self,
        message_id: str,
        agent_id: Optional[str] = None,
    ) -> Any:
        """Delete a message so its owning node can eventually become empty."""
        message = await self._messages.get_async(message_id)
        if message is None:
            raise LookupError("Message not found.")
        node = await self._get_message_node_async(message)
        await self._assert_node_agent_async(node, agent_id or node.agent_id)

        await self._messages.delete_async(message_id)
        await self.invalidate_prompt_cache()
        return message

    async def get_memory_window_async(self, agent_id: str) -> MemoryWindow:
        """Return the non-prompt context window used by the agent's memory engine."""
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
        """Return the active context window plus its estimated token budget."""
        persona = await self._agents.get_async(agent_id) if self._agents is not None else None
        return await self._memory_window.budget_active_window_async(
            agent_id,
            node_limit=self._memory_window_limit(persona) if persona is not None else None,
            token_budget=token_budget,
        )

    async def _ensure_agent_exists_async(self, agent_id: str) -> None:
        """Ensure an explicitly selected agent exists before writing its timeline."""
        if self._agents is None:
            return
        if await self._agents.get_async(agent_id) is None:
            raise LookupError("Agent not found.")

    async def _assert_node_agent_async(self, node: Any, agent_id: Optional[str]) -> None:
        """Reject cross-agent timeline mutations."""
        if agent_id is not None and str(node.agent_id) != str(agent_id):
            raise LookupError("Event node does not belong to the selected agent.")

    async def _get_message_node_async(self, message: Any) -> Any:
        """Resolve and validate the node that currently owns a message."""
        node = await self._events.get_async(message.node_id)
        if node is None:
            raise LookupError("Event node not found for message.")
        return node

    def _memory_window_limit(self, persona: Any) -> int:
        """Return the persona's active node limit, or the framework default."""
        return int(getattr(persona, "active_node_limit", None) or DEFAULT_ACTIVE_NODE_LIMIT)

    @staticmethod
    def _normalize_sender(sender: str, agent_id: str) -> str:
        """Restrict message authors to the user or the selected agent."""
        if sender is None or not str(sender).strip():
            raise ValueError("sender must not be blank.")
        normalized = str(sender).strip()
        if len(normalized) > 60:
            raise ValueError("sender must not exceed 60 characters.")
        allowed = {MESSAGE_SENDER_USER, str(agent_id)}
        if normalized not in allowed:
            raise ValueError("sender must be the user or the selected agent.")
        return normalized

    @staticmethod
    def _normalize_content(content: str) -> str:
        """Validate and normalize message text."""
        if content is None or not str(content).strip():
            raise ValueError("content must not be blank.")
        return str(content).strip()

    @staticmethod
    def _normalize_timestamp(timestamp: Optional[datetime]) -> Optional[datetime]:
        """Convert supported timestamp values to a naive UTC datetime for SQLite."""
        if timestamp is None:
            return None
        if isinstance(timestamp, str):
            value = timestamp.strip()
            try:
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("timestamp must be a valid date and time.") from error
        if not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a valid date and time.")
        if timestamp.tzinfo is not None:
            return timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        return timestamp

    @staticmethod
    def _next_message_position(messages: List[Any]) -> int:
        """Return the next explicit position for a node's message sequence."""
        positions = []
        for message in messages:
            position = getattr(message, "position", None)
            if position is not None:
                try:
                    positions.append(int(position))
                except (TypeError, ValueError):
                    continue
        return max(positions, default=-1) + 1

    async def _resolve_default_agent_id(self) -> str:
        """Return the first persona's id, or raise when no persona exists yet."""
        if self._agents is None:
            raise LookupError("no persona has been created yet.")

        persona = await self._agents.get_default_agent_async()
        if persona is None:
            raise LookupError("no persona has been created yet.")

        return persona.id
