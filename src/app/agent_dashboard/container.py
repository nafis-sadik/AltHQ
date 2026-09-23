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
from core.repositories import JsonConfigRepository
from core.repositories.agent_repository import AgentRepository
from core.repositories.character_sheet_repository import CharacterSheetRepository
from core.repositories.event_log_repository import EventLogRepository
from core.repositories.file_storage_repository import FileStorageRepository
from core.repositories.message_repository import MessageRepository


class Container:
    """Lazily builds and caches the shared config, repository, and service instances."""

    def __init__(self) -> None:
        """Prepare lazy singletons for config, repositories, and services."""
        self._config = None
        self._repository = None
        self._sheet_repository = None
        self._storage = None
        self._service = None
        self._sheet_service = None
        self._event_repository = None
        self._message_repository = None
        self._event_log_manager = None
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

        # Touch the entity module so every table is registered on the shared metadata.
        from core.dtos.db_entities import (  # noqa: F401
            Agent,
            CharacterSheet,
            EventLogNode,
            Message,
        )

        self._repository = AgentRepository(f"sqlite+aiosqlite:///{db_path}")
        self._event_repository = EventLogRepository(f"sqlite+aiosqlite:///{db_path}")
        self._message_repository = MessageRepository(f"sqlite+aiosqlite:///{db_path}")

        # Bootstrap the schema so a fresh deployment can serve requests immediately.
        import asyncio

        bootstrap_loop = asyncio.new_event_loop()
        try:
            bootstrap_loop.run_until_complete(self._repository.create_schema_async())
        finally:
            bootstrap_loop.close()

        self._service = PersonaService(repository=self._repository, config=self._config)

        self._event_log_manager = EventLogManager(
            event_repository=self._event_repository,
            message_repository=self._message_repository,
            agent_repository=self._repository,
        )

        sheets_dir = str(config_dir / "sheets")
        self._storage = FileStorageRepository(sheets_dir)
        self._sheet_repository = CharacterSheetRepository(f"sqlite+aiosqlite:///{db_path}")
        self._sheet_service = CharacterSheetService(
            sheet_repository=self._sheet_repository,
            storage=self._storage,
            image_provider=NullImageProvider(),
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

    def storage(self) -> FileStorageRepository:
        """Return the shared file storage repository."""
        self._ensure_initialized()
        return self._storage

    def reset(self) -> None:
        """Dispose engines and drop cached singletons (used between tests)."""
        # Dispose on the shared loop where the pools were created, otherwise
        # pooled aiosqlite connections stay open and lock the database file.
        from dashboard.async_utils import run_async

        for repository in (
            self._repository,
            self._sheet_repository,
            self._event_repository,
            self._message_repository,
        ):
            if repository is not None:
                if repository._session is not None:
                    run_async(repository._session.close())
                run_async(repository._engine.dispose())

        self._config = None
        self._repository = None
        self._sheet_repository = None
        self._storage = None
        self._service = None
        self._sheet_service = None
        self._event_repository = None
        self._message_repository = None
        self._event_log_manager = None
        self._initialized = False


container = Container()
