"""Phase 1 exit-gate tests: repository CRUD, config manager, persona logic, and layer isolation."""

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.dtos.db_entities import Agent
from core.repositories.agent_repository import AgentRepository
from core.repositories.json_config_repository import JsonConfigRepository
from core.db_engine import create_sqlite_engine
from core.repositories.db_sql_repo.sql_alchemy_repository import SQLAlchemyRepository
from business.persona import (
    PersonaService,
    PersonaUpdate,
)


@pytest.fixture()
def db_url(tmp_path):
    """Provide a per-test SQLite URL on disk so WAL sidecar files stay isolated."""
    return f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}"


@pytest.fixture()
def config_path(tmp_path):
    """Provide an isolated config.json path per test."""
    return str(tmp_path / "config.json")


def run(coro):
    """Run an async repository/service call to completion and return its result."""
    return asyncio.run(coro)


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ---------------------------------------------------------------------------
# Task 1: Database & Persistence Setup
# ---------------------------------------------------------------------------


def test_sqlite_engine_initializes_wal_and_busy_timeout(db_url):
    """Every new connection must run WAL journaling with a 5000ms busy timeout."""
    from sqlalchemy import text

    engine = create_sqlite_engine(db_url)

    async def check():
        async with engine.connect() as conn:
            journal_mode = (await conn.execute(text("PRAGMA journal_mode;"))).scalar()
            busy_timeout = (await conn.execute(text("PRAGMA busy_timeout;"))).scalar()
            foreign_keys = (await conn.execute(text("PRAGMA foreign_keys;"))).scalar()
        await engine.dispose()
        return journal_mode, busy_timeout, foreign_keys

    journal_mode, busy_timeout, foreign_keys = asyncio.run(check())
    assert journal_mode == "wal"
    assert busy_timeout == 5000
    assert foreign_keys == 1


def test_agent_entity_schema_matches_spec():
    """The agents entity must expose exactly the Phase 1 persona columns."""
    columns = {column.name for column in Agent.__table__.columns}
    assert columns == {
        "id",
        "name",
        "gender",
        "profile_picture",
        "bio",
        "background_story",
        "active_node_limit",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_sql_repository_crud_roundtrip(db_url):
    """add/get/update/delete must roundtrip a persona row through the generic repository."""
    engine = create_sqlite_engine(db_url)
    repository = SQLAlchemyRepository[Agent](Agent, engine)

    async def scenario():
        try:
            await repository.create_schema()
            async with repository:
                agent = Agent(
                    name="Aria",
                    gender="female",
                    profile_picture="assets/aria.png",
                    bio="A warm, curious companion.",
                    background_story="Built in a small home lab.",
                    active_node_limit=25,
                )
                saved = await repository.insert_async(agent)
                assert saved.id
                assert saved.is_active is False
                assert saved.to_dict()["is_active"] is False

                fetched = await repository.get_async(saved.id)
                assert fetched is not None
                assert fetched.name == "Aria"
                assert fetched.active_node_limit == 25

                updated = await repository.update_async(
                    saved.id,
                    {"name": "Aria Prime", "active_node_limit": 40},
                )
                assert updated.name == "Aria Prime"
                assert updated.active_node_limit == 40

                await repository.delete_async(saved.id)
                assert await repository.get_async(saved.id) is None
        finally:
            await repository.dispose()

    run(scenario())


def test_persona_service_resolves_persisted_active_agent(db_url):
    """GetByIdAsync with no id must resolve the explicitly persisted active agent."""
    engine = create_sqlite_engine(db_url)
    agent_store = SQLAlchemyRepository[Agent](Agent, engine)
    repository = AgentRepository(agent_store)
    service = PersonaService(
        persona_repository=repository,
        config=JsonConfigRepository(str(db_url) + ".json"),
    )

    async def scenario():
        try:
            await agent_store.create_schema()
            assert await service.GetByIdAsync(None) is None

            await repository.insert_async(
                Agent(
                    name="Aria",
                    gender="female",
                    profile_picture="assets/aria.png",
                    bio="A warm companion.",
                    background_story="Home lab origin.",
                    active_node_limit=20,
                )
            )
            beacon = await repository.insert_async(
                Agent(
                    name="Beacon",
                    gender="non_binary",
                    profile_picture="assets/beacon.png",
                    bio="A steady guide.",
                    background_story="Quiet observatory origin.",
                    active_node_limit=20,
                )
            )

            assert await service.GetByIdAsync(None) is None
            await service.set_active_async(beacon.id)
            persona = await service.GetByIdAsync(None)
            assert persona is not None
            assert persona.name == "Beacon"
            assert [agent.name for agent in await service.list_agents_async()] == [
                "Aria",
                "Beacon",
            ]
        finally:
            await agent_store.dispose()

    run(scenario())


def test_agent_repository_switches_active_atomically(db_url):
    """Active-agent switching must leave exactly the requested agent selected."""
    engine = create_sqlite_engine(db_url)
    agent_store = SQLAlchemyRepository[Agent](Agent, engine)
    repository = AgentRepository(agent_store)

    async def scenario():
        try:
            await agent_store.create_schema()
            first = await repository.insert_async(
                Agent(
                    name="Aria",
                    gender="female",
                    profile_picture="",
                    bio="First",
                    background_story="First origin",
                )
            )
            second = await repository.insert_async(
                Agent(
                    name="Beacon",
                    gender="non_binary",
                    profile_picture="",
                    bio="Second",
                    background_story="Second origin",
                )
            )

            assert await repository.get_active_async() is None
            await repository.set_active_async(first.id)
            assert (await repository.get_active_async()).id == first.id
            await repository.set_active_async(second.id)

            active = await repository.get_active_async()
            assert active is not None
            assert active.id == second.id

            with pytest.raises(LookupError):
                await repository.set_active_async("missing-agent")
            assert (await repository.get_active_async()).id == second.id
        finally:
            await agent_store.dispose()

    run(scenario())


def test_agent_table_rejects_multiple_active_agents_at_database_level(db_url):
    """The partial unique index must reject a second persisted active agent."""
    engine = create_sqlite_engine(db_url)
    agent_store = SQLAlchemyRepository[Agent](Agent, engine)
    repository = AgentRepository(agent_store)

    async def scenario():
        try:
            await agent_store.create_schema()
            first = await repository.insert_async(
                Agent(
                    name="Aria",
                    gender="female",
                    profile_picture="",
                    bio="First",
                    background_story="First origin",
                )
            )
            await repository.insert_async(
                Agent(
                    name="Beacon",
                    gender="non_binary",
                    profile_picture="",
                    bio="Second",
                    background_story="Second origin",
                )
            )
            await repository.set_active_async(first.id)

            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text("UPDATE agents SET is_active = 1 WHERE name = 'Beacon'")
                    )
        finally:
            await agent_store.dispose()

    run(scenario())


# ---------------------------------------------------------------------------
# Task 2: Local JSON Config Manager
# ---------------------------------------------------------------------------


def test_json_config_manager_roundtrip_and_defaults(config_path):
    """set/get must persist values; missing keys fall back; defaults apply on fresh files."""
    repository = JsonConfigRepository(config_path)

    assert repository.get("database_path") == "agent.db"
    assert repository.get("runtime.language") == "en"
    assert repository.get("missing.key", "fallback") == "fallback"

    repository.set("persona.max_active_node_limit", 120)
    reloaded = JsonConfigRepository(config_path)
    assert reloaded.get("persona.max_active_node_limit") == 120
    assert reloaded.get("log_level") == "INFO"


def test_json_config_manager_survives_corrupt_file(config_path):
    """A corrupt config file must fall back to defaults instead of crashing the agent."""
    with open(config_path, "w", encoding="utf-8") as file_handle:
        file_handle.write("{not valid json")

    repository = JsonConfigRepository(config_path)
    assert repository.get("database_path") == "agent.db"

    repository.set("log_level", "DEBUG")
    assert JsonConfigRepository(config_path).get("log_level") == "DEBUG"


# ---------------------------------------------------------------------------
# Task 3: Persona Business Core
# ---------------------------------------------------------------------------


class StubPersonaRepository:
    """In-memory persona repository used to keep the business tests storage-free."""

    def __init__(self):
        self.rows = {}
        self.next_id = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def insert_async(self, entity):
        if isinstance(entity, dict):
            entity = Agent(**entity)
        entity.id = str(self.next_id)
        entity.is_active = bool(getattr(entity, "is_active", False))
        self.next_id += 1
        self.rows[entity.id] = entity
        return entity

    async def get_async(self, entity_id):
        return self.rows.get(entity_id)

    async def get_all_async(self):
        return list(self.rows.values())

    async def get_active_async(self):
        return next(
            (entity for entity in self.rows.values() if entity.is_active),
            None,
        )

    async def set_active_async(self, agent_id):
        if agent_id not in self.rows:
            raise LookupError("Persona not found.")
        for entity in self.rows.values():
            entity.is_active = entity.id == agent_id
        return self.rows[agent_id]

    async def update_async(self, entity_id, values):
        if entity_id not in self.rows:
            raise ValueError("Agent not found")
        for key, value in values.items():
            setattr(self.rows[entity_id], key, value)
        return self.rows[entity_id]

    async def delete_async(self, entity_id):
        self.rows.pop(entity_id, None)


class StubRuntimeConfig:
    """In-memory runtime config used to keep the business tests storage-free."""

    def __init__(self, values=None):
        self.values = dict(
            values or {"persona": {"max_active_node_limit": 200}}
        )

    def get(self, key, default=None):
        node = self.values
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, key, value):
        self.values[key] = value

    def reset_to_defaults(self):
        self.values = {}

    def load(self):
        return dict(self.values)


@pytest.fixture()
def persona_service():
    """Provide a PersonaService wired to in-memory stubs."""
    return PersonaService(
        persona_repository=StubPersonaRepository(),
        config=StubRuntimeConfig(),
    )


def _sample_persona():
    return Agent(
        name="Aria",
        gender="female",
        profile_picture="assets/aria.png",
        bio="A warm companion.",
        background_story="Born in a quiet home lab.",
        active_node_limit=25,
    )


def test_persona_service_rejects_invalid_metadata(persona_service):
    """Blank, oversized, and malformed fields must fail validation with clear errors."""
    result = persona_service.ValidatePersona(
        PersonaUpdate(
            name="",
            gender="x" * 40,
            bio="y" * 501,
            active_node_limit=0,
        )
    )
    assert not result.valid
    assert any("name" in error for error in result.errors)
    assert any("gender" in error for error in result.errors)
    assert any("bio" in error for error in result.errors)
    assert any("active_node_limit" in error for error in result.errors)


def test_persona_service_validates_and_normalizes_update(persona_service):
    """Valid input must normalize (trim) and keep every provided field."""
    result = persona_service.ValidatePersona(
        PersonaUpdate(
            name="  Aria Prime  ",
            gender=" female ",
            bio="  Warm. Curious. Loyal.  ",
            background_story="  Quiet lab origins.  ",
            active_node_limit=50,
        )
    )
    assert result.valid
    values = result.normalized.to_dict()
    assert values["name"] == "Aria Prime"
    assert values["gender"] == "female"
    assert values["bio"] == "Warm. Curious. Loyal."
    assert values["background_story"] == "Quiet lab origins."
    assert values["active_node_limit"] == 50


def test_persona_service_enforces_configured_node_limit():
    """The configured maximum must cap the creation default and stay UI-readable."""
    service = PersonaService(
        persona_repository=StubPersonaRepository(),
        config=StubRuntimeConfig({"persona": {"max_active_node_limit": 60}}),
    )

    async def create():
        return await service.AddNewAsync(
            PersonaUpdate(name="Cap Test", bio="Cap test persona.")
        )

    created = run(create())
    assert created.active_node_limit == 60
    assert service._config.get("persona.max_active_node_limit") == 60


def test_persona_service_does_not_promote_new_agents(persona_service):
    """A new persona must wait for an explicit persisted active-agent selection."""
    created = run(
        persona_service.AddNewAsync(
            PersonaUpdate(name="Aria", bio="A warm companion.")
        )
    )

    assert created.is_active is False
    assert run(persona_service.GetByIdAsync(None)) is None


def test_persona_service_update_persona_applies_changes(persona_service):
    """UpdateExistingAsync must persist normalized changes through the injected repository."""

    async def scenario():
        persona = await persona_service._persona_repository.insert_async(_sample_persona())
        updated = await persona_service.UpdateExistingAsync(
            persona.id,
            PersonaUpdate(name="Aria Prime", active_node_limit=75),
        )
        assert updated.name == "Aria Prime"
        assert updated.active_node_limit == 75
        assert updated.bio == "A warm companion."

        with pytest.raises(ValueError):
            await persona_service.UpdateExistingAsync(
                persona.id,
                PersonaUpdate(name="   "),
            )

    run(scenario())


def test_persona_state_serialization_and_prompt_compilation(persona_service):
    """CompilePromptSegments must produce ordered persona prompt blocks."""
    persona = _sample_persona()
    segments = persona_service.CompilePromptSegments(persona)

    assert segments.identity == "Aria (female)"
    assert segments.bio == "A warm companion."
    assert segments.background_story == "Born in a quiet home lab."
    assert segments.active_node_limit == 25

    blocks = segments.as_prompt_blocks()
    assert blocks[0].startswith("[IDENTITY]")
    assert "Aria (female)" in blocks[0]
    assert blocks[1].startswith("[BIO]")
    assert blocks[2].startswith("[BACKGROUND STORY]")


def test_persona_service_end_to_end_with_real_layer3(db_url, config_path):
    """PersonaService wired to the real Layer 3 stack must update and compile prompts."""
    engine = create_sqlite_engine(db_url)
    agent_store = SQLAlchemyRepository[Agent](Agent, engine)
    repository = AgentRepository(agent_store)
    service = PersonaService(
        persona_repository=repository,
        config=JsonConfigRepository(config_path),
    )

    async def scenario():
        try:
            await agent_store.create_schema()
            persona = await repository.insert_async(_sample_persona())
            await service.UpdateExistingAsync(
                persona.id,
                PersonaUpdate(bio="Rewritten with care."),
            )
            await service.set_active_async(persona.id)
            current = await service.GetByIdAsync(persona.id)
            assert current.bio == "Rewritten with care."

            segments = await service.CompileBasePrompt()
            assert segments.identity.startswith("Aria")
        finally:
            await agent_store.dispose()

    run(scenario())


def test_persona_service_pages_personas_with_totals(db_url):
    """GetPagedPersona must order by name and return paging totals."""
    engine = create_sqlite_engine(db_url)
    agent_store = SQLAlchemyRepository[Agent](Agent, engine)
    repository = AgentRepository(agent_store)
    service = PersonaService(
        persona_repository=repository,
        config=JsonConfigRepository(str(db_url) + ".json"),
    )

    async def scenario():
        try:
            await agent_store.create_schema()
            for name in ("Zed", "Aria", "Moon"):
                await repository.insert_async(Agent(
                    name=name,
                    gender="female",
                    profile_picture="assets/aria.png",
                    bio="A warm companion.",
                    background_story="Home lab origin.",
                ))

            page = await service.GetPagedPersona(1, 2)
            assert page.total_items == 3
            assert [row.name for row in page.source_data] == ["Aria", "Moon"]
            assert page.source_data[0].id

            second_page = await service.GetPagedPersona(2, 2)
            assert [row.name for row in second_page.source_data] == ["Zed"]
        finally:
            await agent_store.dispose()

    run(scenario())


# ---------------------------------------------------------------------------
# Guard: Layer 2 framework independence (runtime-proof)
# ---------------------------------------------------------------------------


def test_layer2_imports_load_no_framework_modules():
    """Importing business logic must not load a web framework, NoSQL store, or driver.

    Layer 2 reuses Layer 3 DTOs for its public value objects, but it must stay
    free of any web framework, NoSQL database store (tinydb/unqlite), or the
    aiosqlite driver.
    """
    snippet = (
        "import sys; sys.path.insert(0, r'{src}'); "
        "from business.persona import PersonaService; "
        "from business.memory import EventLogManager; "
        "banned = [m for m in sys.modules if m.split('.')[0] in "
        "('django', 'flask', 'fastapi', 'tinydb', 'unqlite', 'aiosqlite')]; "
        "sys.exit(1 if banned else 0)"
    ).format(src=str(Path(__file__).resolve().parents[1] / "src"))

    result = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Layer 2 imports pulled in framework modules: "
        f"{result.stdout} {result.stderr}"
    )