"""Phase 2 Task 1 tests: event log schema, repositories, and the memory service wiring.

Task 2 (sliding-window budgeting) and Task 3 (God-Mode edits + cache invalidation)
are covered by their own phase tests added in the relevant sprints.
"""

import asyncio
import sys
from pathlib import Path

import pytest

from core.dtos.db_entities import Agent, EventLogNode, Message
from core.repositories.event_log_repository import EventLogRepository
from core.repositories.message_repository import MessageRepository


def run(coro):
    """Run an async repository/service call to completion and return its result."""
    return asyncio.run(coro)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture()
def db_url(tmp_path):
    """Provide a per-test SQLite URL on disk so WAL sidecar files stay isolated."""
    return f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}"


# ---------------------------------------------------------------------------
# Task 1: Event Log & Message Schema
# ---------------------------------------------------------------------------


def test_event_log_node_schema_matches_spec():
    """The event_log_nodes entity must expose exactly the Phase 2 columns."""
    columns = {column.name for column in EventLogNode.__table__.columns}
    assert columns == {
        "id",
        "agent_id",
        "sequence_index",
        "summary",
        "timestamp",
        "is_active",
    }


def test_message_schema_matches_spec():
    """The messages entity must expose exactly the Phase 2 columns."""
    columns = {column.name for column in Message.__table__.columns}
    assert columns == {
        "id",
        "node_id",
        "sender",
        "content",
        "timestamp",
    }


def _agent_id(db_url):
    """Insert the minimal persona row needed by the event repositories."""
    from core.repositories.agent_repository import AgentRepository

    async def setup():
        agent_repository = AgentRepository(db_url)
        try:
            await agent_repository.create_schema()
            async with agent_repository:
                agent = await agent_repository.insert_async(
                    Agent(
                        name="Aria",
                        gender="female",
                        profile_picture="assets/aria.png",
                        bio="A warm companion.",
                        background_story="Home lab origin.",
                        active_node_limit=20,
                    )
                )
                return agent.id
        finally:
            await agent_repository.dispose()

    return run(setup())


def test_event_repository_insert_auto_sequences_and_timeline_order(db_url):
    """Sequence indices must auto-increment per agent and the timeline return them in order."""
    agent_id = _agent_id(db_url)

    async def scenario():
        repository = EventLogRepository(db_url)
        try:
            await repository.create_schema()
            async with repository:
                first = await repository.insert_async(
                    {"agent_id": agent_id, "summary": "Woke up."}
                )
                second = await repository.insert_async(
                    {"agent_id": agent_id, "summary": "Checked the garden."}
                )

                assert first.sequence_index == 1
                assert second.sequence_index == 2
                assert first.is_active is True

                timeline = await repository.get_timeline_async(agent_id)
                assert [node.summary for node in timeline] == [
                    "Woke up.",
                    "Checked the garden.",
                ]
        finally:
            await repository.dispose()

    run(scenario())


def test_event_repository_active_and_update(db_url):
    """get_active_by_agent_async must exclude archived nodes; update_async must rewrite state."""
    agent_id = _agent_id(db_url)

    async def scenario():
        repository = EventLogRepository(db_url)
        try:
            await repository.create_schema()
            async with repository:
                node = await repository.insert_async(
                    {"agent_id": agent_id, "summary": "An old memory."}
                )
                await repository.update_async(
                    node.id,
                    {"summary": "A revised memory.", "is_active": False},
                )

                updated = await repository.get_async(node.id)
                assert updated.summary == "A revised memory."
                assert updated.is_active is False

                assert await repository.get_active_by_agent_async(agent_id) == []
        finally:
            await repository.dispose()

    run(scenario())


def test_message_repository_attaches_messages_to_node(db_url):
    """Messages must persist and come back attached to their node, oldest first."""
    agent_id = _agent_id(db_url)

    async def scenario():
        event_repository = EventLogRepository(db_url)
        message_repository = MessageRepository(db_url)
        try:
            await event_repository.create_schema()
            async with event_repository, message_repository:
                node = await event_repository.insert_async(
                    {"agent_id": agent_id, "summary": "Met a stranger."}
                )
                await message_repository.insert_async(
                    {"node_id": node.id, "sender": "user", "content": "Hello?"}
                )
                await message_repository.insert_async(
                    {"node_id": node.id, "sender": "archetype", "content": "Hi there."}
                )

                messages = await message_repository.get_by_node_async(node.id)
                assert [message.sender for message in messages] == [
                    "user",
                    "archetype",
                ]
        finally:
            await event_repository.dispose()
            await message_repository.dispose()

    run(scenario())


def test_event_repository_drop_schema_clears_tables(db_url):
    """drop_schema_async must leave the database without the event tables."""
    agent_id = _agent_id(db_url)

    async def scenario():
        repository = EventLogRepository(db_url)
        try:
            await repository.create_schema()
            async with repository:
                await repository.insert_async(
                    {"agent_id": agent_id, "summary": "Will be wiped."}
                )
                assert await repository.get_all_async()
                await repository.drop_schema_async()

                from sqlalchemy import inspect

                async def tables_exist():
                    async with repository._engine.connect() as conn:
                        return await conn.run_sync(
                            lambda sync_conn: inspect(sync_conn).has_table("event_log_nodes")
                        )

                assert await tables_exist() is False

                await repository.create_schema()
                assert await repository.get_all_async() == []
        finally:
            await repository.dispose()

    run(scenario())


class StubAgentRepository:
    """In-memory default-agent lookup used to keep the memory service tests storage-free."""

    def __init__(self, agent_id="agent-1", active_node_limit=20):
        self._agent_id = agent_id
        self._active_node_limit = active_node_limit

    async def get_default_agent_async(self):
        return type(
            "Agent",
            (),
            {"id": self._agent_id, "active_node_limit": self._active_node_limit},
        )()

    async def get_async(self, entity_id):
        return type(
            "Agent",
            (),
            {"id": entity_id, "active_node_limit": self._active_node_limit},
        )()


class StubEventRepository:
    """In-memory event node repository for framework-free business tests."""

    def __init__(self):
        self.nodes = []
        self.next_id = 1

    async def create_schema_async(self):
        pass

    async def insert_async(self, entity):
        if isinstance(entity, dict):
            entity = EventLogNode(**entity)
        if entity.id is None or not entity.id:
            entity.id = f"node-{self.next_id}"
            self.next_id += 1
        if entity.sequence_index is None:
            entity.sequence_index = (self.nodes[-1].sequence_index + 1) if self.nodes else 1
        if entity.is_active is None:
            entity.is_active = True
        self.nodes.append(entity)
        return entity

    async def get_async(self, entity_id):
        return next((node for node in self.nodes if node.id == entity_id), None)

    async def get_timeline_async(self, agent_id):
        return sorted(
            (node for node in self.nodes if node.agent_id == agent_id),
            key=lambda node: node.sequence_index,
        )

    async def get_active_by_agent_async(self, agent_id):
        return [
            node
            for node in await self.get_timeline_async(agent_id)
            if node.is_active
        ]

    async def update_async(self, entity_id, values):
        node = await self.get_async(entity_id)
        if node is None:
            raise ValueError("EventLogNode not found")
        for key, value in values.items():
            setattr(node, key, value)
        return node


class StubMessageRepository:
    """In-memory message repository for framework-free business tests."""

    def __init__(self):
        self.messages = []

    async def insert_async(self, entity):
        if isinstance(entity, dict):
            entity = Message(**entity)
        entity.id = f"msg-{len(self.messages) + 1}"
        self.messages.append(entity)
        return entity

    async def get_async(self, entity_id):
        return next((msg for msg in self.messages if msg.id == entity_id), None)

    async def get_by_node_async(self, node_id):
        return [msg for msg in self.messages if msg.node_id == node_id]

    async def update_async(self, entity_id, values):
        msg = await self.get_async(entity_id)
        if msg is None:
            raise ValueError("Message not found")
        for key, value in values.items():
            setattr(msg, key, value)
        return msg

    async def delete_async(self, entity_id):
        self.messages = [msg for msg in self.messages if msg.id != entity_id]


def _memory_manager():
    from business.memory.event_log_manager import EventLogManager

    return EventLogManager(
        event_repository=StubEventRepository(),
        message_repository=StubMessageRepository(),
        agent_repository=StubAgentRepository(),
    )


def test_memory_service_lists_timeline_as_plain_entries():
    """The event log manager must return timeline plain-data entries with attached messages."""
    from business.memory.event_log_manager import EventLogManager

    manager: EventLogManager = _memory_manager()

    async def scenario():
        first = await manager.append_node_async("Morning routine.")
        second = await manager.append_node_async("Long walk.", is_active=False)
        await manager.append_message_async(first.id, "user", "Good morning!")

        timeline = await manager.list_timeline_async()

        assert [entry.sequence_index for entry in timeline] == [1, 2]
        assert [entry.summary for entry in timeline] == [
            "Morning routine.",
            "Long walk.",
        ]
        assert timeline[1].is_active is False

        assert len(timeline[0].messages) == 1
        payload = timeline[0].to_dict()
        assert payload["id"] == first.id
        assert payload["messages"][0]["sender"] == "user"

    run(scenario())


def test_memory_service_validation_and_missing_default_agent():
    """Blank input must raise and a missing persona must surface a clear lookup error."""
    from business.memory.event_log_manager import EventLogManager

    manager = EventLogManager(
        event_repository=StubEventRepository(),
        message_repository=StubMessageRepository(),
        agent_repository=None,
    )

    async def scenario():
        with pytest.raises(ValueError):
            await manager.append_node_async("   ")

        with pytest.raises(LookupError):
            await manager.list_timeline_async()

    run(scenario())


# ---------------------------------------------------------------------------
# Task 2: Sliding-Window Memory Engine
# ---------------------------------------------------------------------------


def test_memory_window_service_slices_to_the_newest_limit():
    """The active window must keep the newest nodes and archive the rest."""
    from business.memory.memory_window_service import MemoryWindowService

    events = StubEventRepository()
    service = MemoryWindowService(events)

    async def scenario():
        for index in range(1, 6):
            await events.insert_async(
                {"agent_id": "agent-1", "summary": f"Memory {index}"}
            )

        window = await service.get_active_window_async("agent-1", node_limit=3)
        assert window.total_count == 5
        assert window.archived_count == 2
        assert len(window.active_nodes) == 3
        assert [node.sequence_index for node in window.active_nodes] == [3, 4, 5]

        blocks = window.as_prompt_blocks()
        assert blocks[0].startswith("[EVENT #3]")

    run(scenario())


def test_memory_window_service_treats_archived_nodes_as_inactive():
    """Archived (is_active=False) nodes must never enter the active window."""
    from business.memory.memory_window_service import MemoryWindowService

    events = StubEventRepository()
    service = MemoryWindowService(events)

    async def scenario():
        await events.insert_async(
            {"agent_id": "agent-1", "summary": "Old memory", "is_active": False}
        )
        await events.insert_async(
            {"agent_id": "agent-1", "summary": "Fresh memory", "is_active": True}
        )

        window = await service.get_active_window_async("agent-1", node_limit=5)
        assert len(window.active_nodes) == 1
        assert window.active_nodes[0].summary == "Fresh memory"
        assert window.total_count == 1

    run(scenario())


def test_budgeted_window_estimates_tokens_and_stays_within_default_budget():
    """Token estimation must be positive and the default budget must fit the window."""
    from business.memory.memory_window_service import MemoryWindowService

    events = StubEventRepository()
    service = MemoryWindowService(events)

    async def scenario():
        for index in range(1, 4):
            await events.insert_async(
                {"agent_id": "agent-1", "summary": f"Event memory number {index}."}
            )

        budgeted = await service.budget_active_window_async(
            "agent-1",
            node_limit=20,
            token_budget=4096,
        )
        assert budgeted.window.active_nodes
        assert budgeted.estimated_tokens > 0
        assert budgeted.token_budget == 4096
        assert budgeted.remaining_tokens == 4096 - budgeted.estimated_tokens
        assert budgeted.within_budget() is True

    run(scenario())


def test_manager_resolves_persona_node_limit_for_the_active_window():
    """get_memory_window_async must slice using the persona's active node limit."""
    from business.memory.event_log_manager import EventLogManager

    events = StubEventRepository()
    manager = EventLogManager(
        event_repository=events,
        message_repository=StubMessageRepository(),
        agent_repository=StubAgentRepository(active_node_limit=2),
    )

    async def scenario():
        for index in range(1, 5):
            await manager.append_node_async(f"Memory {index}")

        window = await manager.get_memory_window_async("agent-1")
        assert window.node_limit == 2
        assert len(window.active_nodes) == 2
        assert window.archived_count == 2

    run(scenario())


# ---------------------------------------------------------------------------
# Task 3: God-Mode Stealth Editor & Cache Invalidation
# ---------------------------------------------------------------------------


def test_god_mode_edit_rewrites_node_silently_and_invalidates_cache():
    """A stealth node rewrite must persist, list invisibly, and fire invalidation hooks."""
    from business.memory.event_log_manager import EventLogManager

    manager = EventLogManager(
        event_repository=StubEventRepository(),
        message_repository=StubMessageRepository(),
        agent_repository=StubAgentRepository(),
    )
    invalidation_hits = []
    manager.add_cache_invalidator(lambda: invalidation_hits.append("cache"))

    async def scenario():
        node = await manager.append_node_async("Original memory.")
        assert invalidation_hits == []

        updated = await manager.silent_edit_node_async(
            node.id,
            summary="The accepted reality.",
        )
        assert updated.summary == "The accepted reality."
        assert invalidation_hits == ["cache"]

        timeline = await manager.list_timeline_async()
        assert timeline[0].summary == "The accepted reality."

        with pytest.raises(LookupError):
            await manager.silent_edit_node_async("missing-node", summary="Bogus.")

    run(scenario())


def test_god_mode_edit_rewrites_message_silently_and_detaches_audit():
    """A stealth message rewrite must persist and trigger the invalidation hook."""
    from business.memory.event_log_manager import EventLogManager

    manager = EventLogManager(
        event_repository=StubEventRepository(),
        message_repository=StubMessageRepository(),
        agent_repository=StubAgentRepository(),
    )
    invalidation_hits = []
    manager.add_cache_invalidator(lambda: invalidation_hits.append("cache"))

    async def scenario():
        node = await manager.append_node_async("Walking in the rain.")
        message = await manager.append_message_async(
            node.id,
            sender="user",
            content="Tell me about yourself.",
        )

        updated = await manager.silent_edit_message_async(
            message.id,
            content="How did you sleep?",
        )
        assert updated.content == "How did you sleep?"
        assert invalidation_hits == ["cache"]

        timeline = await manager.list_timeline_async()
        assert timeline[0].messages[0].content == "How did you sleep?"

    run(scenario())


def test_silent_edits_reject_invalid_partial_values():
    """Silent edits must validate partial input and refuse empty changes."""
    from business.memory.event_log_manager import EventLogManager

    manager = _memory_manager()

    async def scenario():
        with pytest.raises(ValueError):
            await manager.silent_edit_node_async("node-x", summary="   ")

        with pytest.raises(ValueError):
            await manager.silent_edit_message_async("msg-x", content="   ")

        node = await manager.append_node_async("Keep me.")
        with pytest.raises(ValueError):
            await manager.silent_edit_node_async(node.id)

    run(scenario())