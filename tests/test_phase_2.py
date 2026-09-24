"""Phase 2 tests: chronological node and message persistence plus memory services.

The Line of Truth is an explicit, editable node list. Message ordering is
independent from the user-editable conversation timestamp.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from core.dtos.db_entities import Agent, EventLogNode, Message
from core.db_engine import create_sqlite_engine
from core.repositories.db_sql_repo.sql_alchemy_repository import SQLAlchemyRepository


def run(coro):
    """Run an async repository/service call to completion and return its result."""
    return asyncio.run(coro)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture()
def db_url(tmp_path):
    """Provide a per-test SQLite URL on disk so WAL sidecar files stay isolated."""
    return f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}"


def _session_repositories(db_url):
    """Build one shared engine plus the three generic repositories (schema created)."""
    engine = create_sqlite_engine(db_url)
    agents = SQLAlchemyRepository[Agent](Agent, engine)
    events = SQLAlchemyRepository[EventLogNode](EventLogNode, engine)
    messages = SQLAlchemyRepository[Message](Message, engine)
    run(agents.create_schema())
    return agents, events, messages


# ---------------------------------------------------------------------------
# Task 1: Event Log & Message Schema
# ---------------------------------------------------------------------------


def test_event_log_node_schema_matches_spec():
    """The event_log_nodes entity must expose the timeline columns and Agent FK."""
    columns = {column.name for column in EventLogNode.__table__.columns}
    assert columns == {
        "id",
        "agent_id",
        "sequence_index",
        "summary",
        "timestamp",
        "is_active",
    }
    assert any(
        foreign_key.target_fullname == "agents.id"
        for foreign_key in EventLogNode.__table__.foreign_keys
    )


def test_event_timelines_are_scoped_to_agent_foreign_key(db_url):
    """Event nodes must belong to an existing Agent and remain agent-scoped."""
    agents, events, messages = _session_repositories(db_url)

    async def scenario():
        try:
            async with agents:
                first = await agents.insert_async(
                    Agent(
                        name="Aria",
                        gender="female",
                        profile_picture="x",
                        bio="A",
                        background_story="A",
                    )
                )
                second = await agents.insert_async(
                    Agent(
                        name="Beacon",
                        gender="non_binary",
                        profile_picture="x",
                        bio="B",
                        background_story="B",
                    )
                )

            async with events:
                await events.insert_async(
                    EventLogNode(
                        agent_id=first.id,
                        sequence_index=1,
                        summary="Aria event.",
                    )
                )
                await events.insert_async(
                    EventLogNode(
                        agent_id=second.id,
                        sequence_index=1,
                        summary="Beacon event.",
                    )
                )

                first_nodes = list(
                    (
                        await events.execute_query_async(
                            events.base_query()
                            .where(EventLogNode.agent_id == first.id)
                            .order_by(EventLogNode.sequence_index)
                        )
                    ).scalars().all()
                )
                assert [node.summary for node in first_nodes] == ["Aria event."]

                second_nodes = list(
                    (
                        await events.execute_query_async(
                            events.base_query()
                            .where(EventLogNode.agent_id == second.id)
                            .order_by(EventLogNode.sequence_index)
                        )
                    ).scalars().all()
                )
                assert [node.summary for node in second_nodes] == ["Beacon event."]

                with pytest.raises(IntegrityError):
                    await events.insert_async(
                        EventLogNode(
                            agent_id="missing-agent",
                            sequence_index=1,
                            summary="Orphan.",
                        )
                    )
        finally:
            await agents.dispose()

    run(scenario())


def test_message_schema_matches_spec():
    """The messages entity must expose exactly the Phase 2 columns."""
    columns = {column.name for column in Message.__table__.columns}
    assert columns == {
        "id",
        "node_id",
        "sender",
        "content",
        "position",
        "timestamp",
    }
    assert any(
        foreign_key.target_fullname == "event_log_nodes.id"
        for foreign_key in Message.__table__.foreign_keys
    )


def _agent_id(db_url):
    """Insert the minimal persona row needed by the event repositories."""
    agents = SQLAlchemyRepository[Agent](Agent, create_sqlite_engine(db_url))

    async def setup():
        try:
            await agents.create_schema()
            async with agents:
                agent = await agents.insert_async(
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
            await agents.dispose()

    return run(setup())


def test_event_log_manager_auto_sequences_and_timeline_order(db_url):
    """Sequence indices must auto-increment per agent and the timeline return them in order."""
    agent_id = _agent_id(db_url)
    from business.memory.event_log_manager import EventLogManager

    agents, events, messages = _session_repositories(db_url)
    manager = EventLogManager(
        event_repository=events,
        message_repository=messages,
        agent_repository=agents,
    )

    async def scenario():
        try:
            first = await manager.add_node_async("Woke up.", agent_id=agent_id)
            second = await manager.add_node_async("Checked the garden.", agent_id=agent_id)

            assert first.sequence_index == 1
            assert second.sequence_index == 2
            assert first.is_active is True

            timeline = await manager.list_timeline_async(agent_id)
            assert [node.summary for node in timeline] == [
                "Woke up.",
                "Checked the garden.",
            ]
        finally:
            await agents.dispose()

    run(scenario())


def test_event_active_flag_and_update(db_url):
    """Archived nodes must leave the active window; update_async must rewrite state."""
    agent_id = _agent_id(db_url)
    from business.memory.event_log_manager import EventLogManager

    agents, events, messages = _session_repositories(db_url)
    manager = EventLogManager(
        event_repository=events,
        message_repository=messages,
        agent_repository=agents,
    )

    async def scenario():
        try:
            node = await manager.add_node_async("An old memory.", agent_id=agent_id)
            async with events:
                updated = await events.update_async(
                    node.id,
                    {"summary": "A revised memory.", "is_active": False},
                )
            assert updated.summary == "A revised memory."
            assert updated.is_active is False

            window = await manager.get_memory_window_async(agent_id)
            assert window.active_nodes == []
        finally:
            await agents.dispose()

    run(scenario())


def test_message_repository_attaches_messages_to_node(db_url):
    """Messages must persist and come back attached to their node, oldest first."""
    agent_id = _agent_id(db_url)
    from business.memory.event_log_manager import EventLogManager

    agents, events, messages = _session_repositories(db_url)
    manager = EventLogManager(
        event_repository=events,
        message_repository=messages,
        agent_repository=agents,
    )

    async def scenario():
        try:
            node = await manager.add_node_async("Met a stranger.", agent_id=agent_id)
            async with messages:
                await messages.insert_async(
                    Message(node_id=node.id, sender="user", content="Hello?", position=0)
                )
                await messages.insert_async(
                    Message(node_id=node.id, sender="agent-1", content="Hi there.", position=1)
                )

            timeline = await manager.list_timeline_async(agent_id)
            assert [message.sender for message in timeline[0].messages] == [
                "user",
                "agent-1",
            ]
            assert [message.position for message in timeline[0].messages] == [0, 1]
        finally:
            await agents.dispose()

    run(scenario())


def test_event_manager_blocks_delete_when_messages_exist(db_url):
    """The manager must refuse to delete a node with attached messages."""
    agent_id = _agent_id(db_url)
    from business.memory.event_log_manager import EventLogManager

    agents, events, messages = _session_repositories(db_url)
    manager = EventLogManager(
        event_repository=events,
        message_repository=messages,
        agent_repository=agents,
    )

    async def scenario():
        try:
            node = await manager.add_node_async("Has a message.", agent_id=agent_id)
            message = await manager.append_message_async(
                node.id, "user", "Hello.", agent_id=agent_id
            )

            with pytest.raises(ValueError, match="messages"):
                await manager.delete_node_async(node.id, agent_id=agent_id)
            await manager.delete_message_async(message.id, agent_id=agent_id)
            await manager.delete_node_async(node.id, agent_id=agent_id)
            assert await manager.list_timeline_async(agent_id) == []
        finally:
            await agents.dispose()

    run(scenario())


def test_message_repository_reorders_by_explicit_position(db_url):
    """Message order must follow position even when timestamps are edited independently."""
    agent_id = _agent_id(db_url)
    from business.memory.event_log_manager import EventLogManager

    agents, events, messages = _session_repositories(db_url)
    manager = EventLogManager(
        event_repository=events,
        message_repository=messages,
        agent_repository=agents,
    )

    async def scenario():
        try:
            node = await manager.add_node_async("Conversation.", agent_id=agent_id)
            async with messages:
                first = await messages.insert_async(
                    Message(
                        node_id=node.id,
                        sender="user",
                        content="First",
                        position=0,
                        timestamp=datetime(2024, 1, 1, 12, 0),
                    )
                )
                second = await messages.insert_async(
                    Message(
                        node_id=node.id,
                        sender="agent-1",
                        content="Second",
                        position=1,
                        timestamp=datetime(2024, 1, 1, 11, 0),
                    )
                )

                await messages.update_async(first.id, {"position": 1})
                await messages.update_async(second.id, {"position": 0})

            timeline = await manager.list_timeline_async(agent_id)
            assert [message.content for message in timeline[0].messages] == ["Second", "First"]
        finally:
            await agents.dispose()

    run(scenario())


def test_event_repository_drop_schema_clears_tables(db_url):
    """drop_schema must leave the database without the event tables."""
    agent_id = _agent_id(db_url)
    agents, events, messages = _session_repositories(db_url)

    async def scenario():
        try:
            async with events:
                await events.insert_async(
                    EventLogNode(agent_id=agent_id, sequence_index=1, summary="Will be wiped.")
                )
                assert await events.get_all_async()
                await events.drop_schema()

                from sqlalchemy import inspect

                async def tables_exist():
                    async with events._engine.connect() as conn:
                        return await conn.run_sync(
                            lambda sync_conn: inspect(sync_conn).has_table("event_log_nodes")
                        )

                assert await tables_exist() is False

                await events.create_schema()
                assert await events.get_all_async() == []
        finally:
            await agents.dispose()

    run(scenario())


class StubAgentRepository:
    """In-memory default-agent lookup used to keep the memory service tests storage-free."""

    def __init__(self, agent_id="agent-1", name="Aria", active_node_limit=20):
        self._agent_id = agent_id
        self._name = name
        self._active_node_limit = active_node_limit

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def get_async(self, entity_id):
        if str(entity_id) != str(self._agent_id):
            return None
        return type(
            "Agent",
            (),
            {
                "id": self._agent_id,
                "name": self._name,
                "active_node_limit": self._active_node_limit,
            },
        )()

    async def get_all_async(self):
        return [await self.get_async(self._agent_id)]


class StubEventRepository:
    """In-memory event node repository for framework-free business tests."""

    def __init__(self):
        self.nodes = []
        self.next_id = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

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

    async def get_all_async(self):
        return list(self.nodes)

    async def update_async(self, entity_id, values):
        node = await self.get_async(entity_id)
        if node is None:
            raise ValueError("EventLogNode not found")
        for key, value in values.items():
            setattr(node, key, value)
        return node

    async def delete_async(self, entity_id):
        self.nodes = [node for node in self.nodes if node.id != entity_id]


class StubMessageRepository:
    """In-memory message repository for framework-free business tests."""

    def __init__(self):
        self.messages = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def insert_async(self, entity):
        if isinstance(entity, dict):
            entity = Message(**entity)
        entity.id = f"msg-{len(self.messages) + 1}"
        if entity.position is None:
            entity.position = len(await self.get_by_node_async(entity.node_id))
        self.messages.append(entity)
        return entity

    async def get_async(self, entity_id):
        return next((msg for msg in self.messages if msg.id == entity_id), None)

    async def get_all_async(self):
        return list(self.messages)

    async def get_by_node_async(self, node_id):
        messages = [msg for msg in self.messages if msg.node_id == node_id]
        return sorted(
            messages,
            key=lambda message: (
                getattr(message, "position", None)
                if getattr(message, "position", None) is not None
                else 0,
                message.timestamp or datetime.min,
                message.id,
            ),
        )

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
                EventLogNode(
                    agent_id="agent-1",
                    sequence_index=index,
                    summary=f"Memory {index}",
                )
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
            EventLogNode(
                agent_id="agent-1",
                sequence_index=1,
                summary="Old memory",
                is_active=False,
            )
        )
        await events.insert_async(
            EventLogNode(
                agent_id="agent-1",
                sequence_index=2,
                summary="Fresh memory",
                is_active=True,
            )
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
                EventLogNode(
                    agent_id="agent-1",
                    sequence_index=index,
                    summary=f"Event memory number {index}.",
                )
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
# Explicit timeline CRUD and message conversation management
# ---------------------------------------------------------------------------


def test_explicit_node_edit_updates_timeline_and_invalidates_cache():
    """A normal node edit persists visibly and invalidates prompt context."""
    from business.memory.event_log_manager import EventLogManager

    manager = EventLogManager(
        event_repository=StubEventRepository(),
        message_repository=StubMessageRepository(),
        agent_repository=StubAgentRepository(),
    )
    invalidation_hits = []
    manager.add_cache_invalidator(lambda: invalidation_hits.append("cache"))

    async def scenario():
        node = await manager.add_node_async("Original memory.")
        invalidation_hits.clear()

        updated = await manager.update_node_async(
            node.id,
            summary="The corrected memory.",
        )
        assert updated.summary == "The corrected memory."
        assert invalidation_hits == ["cache"]

        timeline = await manager.list_timeline_async()
        assert timeline[0].summary == "The corrected memory."

        with pytest.raises(LookupError):
            await manager.update_node_async("missing-node", summary="Bogus.")

    run(scenario())


def test_message_crud_supports_speaker_text_and_manual_timestamp():
    """Messages can be added, explicitly edited, and given a conversation time."""
    from business.memory.event_log_manager import EventLogManager

    manager = _memory_manager()

    async def scenario():
        node = await manager.add_node_async("A conversation happened.")
        first_time = datetime(2024, 5, 4, 10, 30)
        message = await manager.append_message_async(
            node.id,
            sender="user",
            content="What happened?",
            timestamp=first_time,
        )
        assert message.sender == "user"
        assert message.timestamp == first_time
        assert message.position == 0

        with pytest.raises(ValueError, match="selected agent"):
            await manager.append_message_async(node.id, "other", "Not allowed.")

        second_time = datetime(2024, 5, 4, 10, 35)
        updated = await manager.update_message_async(
            message.id,
            sender="agent-1",
            content="I remembered the garden.",
            timestamp=second_time,
        )
        assert updated.sender == "agent-1"
        assert updated.content == "I remembered the garden."
        assert updated.timestamp == second_time

        await manager.delete_message_async(message.id)
        timeline = await manager.list_timeline_async()
        assert timeline[0].messages == []

    run(scenario())


def test_messages_can_reorder_and_move_between_nodes():
    """Explicit message positions support up/down movement and node reassignment."""
    manager = _memory_manager()

    async def scenario():
        first_node = await manager.add_node_async("First node.")
        second_node = await manager.add_node_async("Second node.")
        first = await manager.append_message_async(first_node.id, "user", "One")
        second = await manager.append_message_async(first_node.id, "agent-1", "Two")
        third = await manager.append_message_async(first_node.id, "user", "Three")

        await manager.move_message_position_async(third.id, "up")
        timeline = await manager.list_timeline_async()
        assert [message.content for message in timeline[0].messages] == [
            "One",
            "Three",
            "Two",
        ]
        assert [message.position for message in timeline[0].messages] == [0, 1, 2]

        await manager.move_message_async(third.id, second_node.id)
        timeline = await manager.list_timeline_async()
        assert [message.content for message in timeline[0].messages] == ["One", "Two"]
        assert [message.content for message in timeline[1].messages] == ["Three"]
        assert timeline[1].messages[0].position == 0

    run(scenario())


def test_node_deletion_requires_all_messages_to_be_removed_or_moved():
    """A node cannot be deleted until its message collection is empty."""
    manager = _memory_manager()

    async def scenario():
        source = await manager.add_node_async("Source node.")
        target = await manager.add_node_async("Target node.")
        message = await manager.append_message_async(source.id, "user", "Move me.")

        with pytest.raises(ValueError, match="messages"):
            await manager.delete_node_async(source.id)

        await manager.move_message_async(message.id, target.id)
        await manager.delete_node_async(source.id)
        timeline = await manager.list_timeline_async()
        assert [node.summary for node in timeline] == ["Target node."]

    run(scenario())


def test_timeline_mutations_reject_invalid_values():
    """CRUD methods reject missing records, blank fields, and invalid directions."""
    manager = _memory_manager()

    async def scenario():
        with pytest.raises(LookupError):
            await manager.update_node_async("missing-node", summary="Nope.")

        node = await manager.add_node_async("Keep me.")
        with pytest.raises(ValueError):
            await manager.update_node_async(node.id, summary="   ")
        with pytest.raises(ValueError):
            await manager.update_node_async(node.id)

        message = await manager.append_message_async(node.id, "user", "Hello.")
        with pytest.raises(ValueError):
            await manager.update_message_async(message.id, content="   ")
        with pytest.raises(ValueError):
            await manager.move_message_position_async(message.id, "sideways")
        with pytest.raises(LookupError):
            await manager.delete_message_async("missing-message")

    run(scenario())