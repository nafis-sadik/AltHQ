"""Framework-independent sliding-window memory engine for active event context."""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from business.memory.token_budget import estimate_node_tokens
from core.dtos.db_entities import EventLogNode
from core.repositories.db_sql_repo.sql_repository import ISQLRepository

# Default cap for the active prompt window when no explicit budget is supplied.
DEFAULT_TOKEN_BUDGET = 4096


@dataclass
class MemoryWindow:
    """The active sliding window: the newest nodes that fit the configured limit."""

    active_nodes: List[Any] = field(default_factory=list)
    node_limit: int = 0
    archived_count: int = 0
    total_count: int = 0

    def node_ids(self) -> List[str]:
        """Return the ids of the active node rows."""
        return [node.id for node in self.active_nodes]

    def as_prompt_blocks(self) -> List[str]:
        """Compile the active nodes into ordered prompt blocks for prompt assembly."""
        return [
            f"[EVENT #{node.sequence_index}]\n{node.summary}"
            for node in self.active_nodes
        ]


@dataclass
class BudgetedMemoryWindow:
    """The active sliding window plus its token budget breakdown."""

    window: MemoryWindow
    estimated_tokens: int = 0
    token_budget: int = 0
    remaining_tokens: int = 0

    def within_budget(self) -> bool:
        """Return True when the active window fits inside the token budget."""
        return self.remaining_tokens >= 0


class MemoryWindowService:
    """Slices the agent's event log into an active window and budgets its tokens.

    Older nodes remain preserved in storage but are archived out of the window
    once the configured node limit is exceeded.
    """

    def __init__(self, event_repository: ISQLRepository[EventLogNode]) -> None:
        """Store the repository contract without importing any storage framework."""
        self._events = event_repository

    async def get_active_window_async(
        self,
        agent_id: str,
        node_limit: Optional[int] = None,
    ) -> MemoryWindow:
        """Return the newest ``node_limit`` active nodes, oldest sequence first."""
        async with self._events:
            nodes = await self._events.get_all_async()

        active = sorted(
            (
                node
                for node in nodes
                if str(node.agent_id) == str(agent_id) and node.is_active
            ),
            key=lambda node: node.sequence_index,
        )

        if node_limit is None or node_limit < 1:
            node_limit = len(active) or 0

        if node_limit == 0:
            return MemoryWindow(
                active_nodes=[],
                node_limit=0,
                archived_count=0,
                total_count=0,
            )

        window_nodes = active[-node_limit:]
        return MemoryWindow(
            active_nodes=window_nodes,
            node_limit=node_limit,
            archived_count=max(0, len(active) - node_limit),
            total_count=len(active),
        )

    async def budget_active_window_async(
        self,
        agent_id: str,
        node_limit: Optional[int] = None,
        token_budget: Optional[int] = None,
    ) -> BudgetedMemoryWindow:
        """Slice the active window and estimate its prompt token footprint."""
        window = await self.get_active_window_async(agent_id, node_limit)

        estimated = sum(
            estimate_node_tokens(
                node.summary,
                getattr(node, "messages", None),
            )
            for node in window.active_nodes
        )

        if token_budget is None:
            token_budget = DEFAULT_TOKEN_BUDGET

        return BudgetedMemoryWindow(
            window=window,
            estimated_tokens=estimated,
            token_budget=token_budget,
            remaining_tokens=token_budget - estimated,
        )