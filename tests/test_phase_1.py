"""Phase 1 exit-gate tests: repository CRUD, config manager, persona logic, and layer isolation."""

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from core.dtos.db_entities import Agent
from core.repositories.agent_repository import AgentRepository
from core.repositories.json_config_repository import JsonConfigRepository
from core.db_engine import create_sqlite_engine
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
        "created_at",
        "updated_at",
    }


def test_agent_repository_crud_roundtrip(db_url):
    """add/get/update/delete must roundtrip a persona row through the repository."""
    async def scenario():
        repository = AgentRepository(db_url)
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


def test_agent_repository_get_default_agent_async(db_url):
    """The default-persona helper must return the single row or None when empty."""
    async def scenario():
        repository = AgentRepository(db_url)
        try:
            await repository.create_schema()
            async with repository:
                assert await repository.get_default_agent_async() is None

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
                persona = await repository.get_default_agent_async()
                assert persona is not None
                assert persona.name == "Aria"
        finally:
            await repository.dispose()

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

    async def insert_async(self, entity):
        if isinstance(entity, dict):
            entity = Agent(**entity)
        entity.id = str(self.next_id)
        self.next_id += 1
        self.rows[entity.id] = entity
        return entity

    async def get_async(self, entity_id):
        return self.rows.get(entity_id)

    async def get_all_async(self):
        return list(self.rows.values())

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
    return PersonaService(repository=StubPersonaRepository(), config=StubRuntimeConfig())


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
    result = persona_service.validate_update(
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
    result = persona_service.validate_update(
        PersonaUpdate(
            name="  Aria Prime  ",
            gender=" female ",
            bio="  Warm. Curious. Loyal.  ",
            background_story="  Quiet lab origins.  ",
            active_node_limit=50,
        )
    )
    assert result.valid
    values = result.normalized.to_repository_values()
    assert values["name"] == "Aria Prime"
    assert values["gender"] == "female"
    assert values["bio"] == "Warm. Curious. Loyal."
    assert values["background_story"] == "Quiet lab origins."
    assert values["active_node_limit"] == 50


def test_persona_service_enforces_configured_node_limit():
    """The configured maximum must cap the creation default and stay UI-readable."""
    service = PersonaService(
        repository=StubPersonaRepository(),
        config=StubRuntimeConfig({"persona": {"max_active_node_limit": 60}}),
    )

    async def create():
        return await service.create_persona(
            PersonaUpdate(name="Cap Test", bio="Cap test persona.")
        )

    created = run(create())
    assert created.active_node_limit == 60
    assert service._config.get("persona.max_active_node_limit") == 60


def test_persona_service_update_persona_applies_changes(persona_service):
    """update_persona must persist normalized changes through the injected repository."""

    async def scenario():
        persona = await persona_service._repository.insert_async(_sample_persona())
        updated = await persona_service.update_persona(
            persona.id,
            PersonaUpdate(name="Aria Prime", active_node_limit=75),
        )
        assert updated.name == "Aria Prime"
        assert updated.active_node_limit == 75
        assert updated.bio == "A warm companion."

        with pytest.raises(ValueError):
            await persona_service.update_persona(persona.id, PersonaUpdate(name="   "))

    run(scenario())


def test_persona_state_serialization_and_prompt_compilation(persona_service):
    """compile_prompt_segments must produce ordered persona prompt blocks."""
    persona = _sample_persona()
    segments = persona_service.compile_prompt_segments(persona)

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
    async def scenario():
        repository = AgentRepository(db_url)
        config = JsonConfigRepository(config_path)
        service = PersonaService(repository=repository, config=config)
        try:
            await repository.create_schema()
            async with repository:
                persona = await repository.insert_async(_sample_persona())
                await service.update_persona(
                    persona.id,
                    PersonaUpdate(bio="Rewritten with care."),
                )
                current = await service.get_persona(persona.id)
                assert current.bio == "Rewritten with care."

                segments = await service.compile_base_prompt()
                assert segments.identity.startswith("Aria")
        finally:
            await repository.dispose()

    run(scenario())


# ---------------------------------------------------------------------------
# Guard: Layer 2 framework independence (runtime-proof)
# ---------------------------------------------------------------------------


def test_layer2_imports_load_no_framework_modules():
    """Importing business logic must not load SQLAlchemy, aiosqlite, or any web framework."""
    snippet = (
        "import sys; sys.path.insert(0, r'{src}'); "
        "from business.persona.persona_service import PersonaService; "
        "from business.memory.event_log_manager import EventLogManager; "
        "banned = [m for m in sys.modules if m.split('.')[0] in "
        "('sqlalchemy', 'aiosqlite', 'flask', 'fastapi', 'tinydb', 'unqlite')]; "
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
