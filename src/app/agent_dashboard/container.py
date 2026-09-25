"""Composition root: builds the concrete object graph once per process.

Layer 1 imports Layer 2 and Layer 3 freely; Layer 2 stays framework-independent
because the wiring happens here and nowhere else.
"""

import os
from pathlib import Path

from agent_dashboard.settings import BASE_DIR
from business.memory import EventLogManager
from business.persona import (
    CharacterSheetService,
    NullImageProvider,
    PersonaService,
)
from core.db_engine import create_sqlite_engine
from core.dtos.db_entities import Agent, CharacterSheet, EventLogNode, Message
from core.repositories import (
    AgentRepository,
    FileStorageRepository,
    JsonConfigRepository,
)
from core.repositories.db_sql_repo.sql_alchemy_repository import SQLAlchemyRepository
from dashboard.async_utils import run_async
from dashboard.controllers import EventLogController, PersonaController


class Container:
    """Lazily builds and caches the shared config, engine, repository, and service instances."""

    def __init__(self) -> None:
        """Prepare lazy singletons for config, repositories, services, and controllers."""
        self._config = None
        self._engine = None
        self._repository = None
        self._sheet_repository = None
        self._storage = None
        self._service = None
        self._sheet_service = None
        self._event_repository = None
        self._message_repository = None
        self._event_log_manager = None
        self._persona_controller = None
        self._event_log_controller = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Build the object graph on first use, then cache the instances."""
        if self._initialized:
            return

        # Tests override the storage directory via AGENT_CONFIG_DIR.
        config_dir = Path(os.environ.get("AGENT_CONFIG_DIR", str(BASE_DIR)))
        config_dir.mkdir(parents=True, exist_ok=True)

        self._config = JsonConfigRepository(str(config_dir / "config.json"))

        db_path = self._config.get("database_path", "agent.db")
        if not os.path.isabs(db_path):
            db_path = str(config_dir / db_path)

        # One shared WAL-enabled engine; every repository reuses it.
        self._engine = create_sqlite_engine(f"sqlite+aiosqlite:///{db_path}")

        agent_store = SQLAlchemyRepository[Agent](Agent, self._engine)
        self._repository = AgentRepository(agent_store)
        self._event_repository = SQLAlchemyRepository[EventLogNode](EventLogNode, self._engine)
        self._message_repository = SQLAlchemyRepository[Message](Message, self._engine)

        # Bootstrap the schema so a fresh deployment can serve requests immediately.
        # All entities share one metadata, so a single create creates every table.
        run_async(agent_store.create_schema())

        self._service = PersonaService(
            persona_repository=self._repository,
            config=self._config,
        )

        self._event_log_manager = EventLogManager(
            event_repository=self._event_repository,
            message_repository=self._message_repository,
            agent_repository=self._repository,
        )

        sheets_dir = str(config_dir / "sheets")
        self._storage = FileStorageRepository(sheets_dir)
        self._sheet_repository = SQLAlchemyRepository[CharacterSheet](
            CharacterSheet,
            self._engine,
        )
        self._sheet_service = CharacterSheetService(
            sheet_repository=self._sheet_repository,
            storage=self._storage,
            image_provider=NullImageProvider(),
        )
        self._persona_controller = PersonaController(
            persona_service=self._service,
            sheet_service=self._sheet_service,
            config=self._config,
            storage=self._storage,
        )
        self._event_log_controller = EventLogController(
            persona_service=self._service,
            event_log_service=self._event_log_manager,
        )
        self._initialized = True

    def config(self) -> JsonConfigRepository:
        """Return the shared JSON config repository."""
        self._ensure_initialized()
        return self._config

    def persona_service(self) -> PersonaService:
        """Return the shared persona business service."""
        self._ensure_initialized()
        return self._service

    def sheet_service(self) -> CharacterSheetService:
        """Return the shared character sheet service."""
        self._ensure_initialized()
        return self._sheet_service

    def event_log_manager(self) -> EventLogManager:
        """Return the shared event log business service."""
        self._ensure_initialized()
        return self._event_log_manager

    def persona_controller(self) -> PersonaController:
        """Return the persona domain controller with its services injected."""
        self._ensure_initialized()
        return self._persona_controller

    def event_log_controller(self) -> EventLogController:
        """Return the Line of Truth controller with its services injected."""
        self._ensure_initialized()
        return self._event_log_controller

    def storage(self) -> FileStorageRepository:
        """Return the shared file storage repository."""
        self._ensure_initialized()
        return self._storage

    def reset(self) -> None:
        """Dispose engines and drop cached singletons (used between tests)."""
        # Dispose on the shared loop where the pool was created, otherwise
        # pooled aiosqlite connections stay open and lock the database file.
        if self._engine is not None:
            run_async(self._engine.dispose())

        self._config = None
        self._engine = None
        self._repository = None
        self._sheet_repository = None
        self._storage = None
        self._service = None
        self._sheet_service = None
        self._event_repository = None
        self._message_repository = None
        self._event_log_manager = None
        self._persona_controller = None
        self._event_log_controller = None
        self._initialized = False


container = Container()