"""SQLAlchemy async implementation of the ISQLRepository interface."""

from typing import Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.repositories.db_sql_repo.sql_repository import ISQLRepository

TEntity = TypeVar("TEntity")

class SQLAlchemyRepository(ISQLRepository[TEntity], Generic[TEntity]):
    """Async repository that maps a declarative entity type to a SQLAlchemy-backed table."""

    def __init__(self, entity_type: Type[TEntity], db_url: str, echo: bool = False) -> None:
        """Create the async engine and session factory for the given database URL."""
        self._entity_type = entity_type
        self._engine = create_async_engine(db_url, echo=echo)
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )
        self._session: Optional[AsyncSession] = None

    async def __aenter__(self) -> "SQLAlchemyRepository[TEntity]":
        """Open a new session and return self for use with 'async with'."""
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Roll back on error, close the session, and clear the session reference."""
        if exc_type is not None:
            await self._session.rollback()
        await self._session.close()
        self._session = None

    def __enter__(self) -> "SQLAlchemyRepository[TEntity]":
        """Refuse sync context-manager usage since this repository is async-only."""
        raise NotImplementedError(
            "SQLAlchemyRepository is async-only. Use 'async with' instead."
        )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Refuse sync context-manager usage since this repository is async-only."""
        raise NotImplementedError(
            "SQLAlchemyRepository is async-only. Use 'async with' instead."
        )

    async def create_schema(self) -> None:
        """Create all tables defined on the entity's metadata."""
        async with self._engine.begin() as conn:
            await conn.run_sync(self._entity_type.metadata.create_all)

    async def drop_schema(self) -> None:
        """Drop all tables defined on the entity's metadata."""
        async with self._engine.begin() as conn:
            await conn.run_sync(self._entity_type.metadata.drop_all)

    async def dispose(self) -> None:
        """Release the underlying database engine connection pool."""
        await self._engine.dispose()

    async def insert_async(self, entity: TEntity) -> TEntity:
        """Add the entity, commit, refresh it from the database, and return it."""
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def bulk_insert_async(self, entities: List[TEntity]) -> List[TEntity]:
        """Add all entities in one transaction and return them refreshed."""
        self._session.add_all(entities)
        await self._session.commit()
        for entity in entities:
            await self._session.refresh(entity)
        return entities

    async def get_async(self, entity_id: str) -> Optional[TEntity]:
        """Return the entity with the given primary key, or None if absent."""
        return await self._session.get(
            self._entity_type,
            entity_id
        )

    async def get_by_expression_async(self, criterion) -> Sequence[TEntity]:
        """Return every entity matching the given SQLAlchemy criterion."""
        result = await self._session.execute(
            select(self._entity_type).where(criterion)
        )
        return result.scalars().all()

    async def get_all_async(self) -> List[TEntity]:
        """Return every entity in the table."""
        result = await self._session.execute(
            select(self._entity_type)
        )
        return list(result.scalars().all())

    async def update_async(self, entity_id: str, values: dict) -> TEntity:
        """Apply values to the entity with the given id and return the updated entity.

        Raises ValueError if no entity with that id exists.
        """
        await self._session.execute(
            update(self._entity_type)
            .where(self._entity_type.id == entity_id)
            .values(**values)
        )

        await self._session.commit()

        updated = await self.get_async(entity_id)

        if updated is None:
            raise ValueError(
                f"{self._entity_type.__name__} not found"
            )

        return updated

    async def update_by_expression_async(self, criterion, values: dict) -> List[TEntity]:
        """Apply values to every entity matching the criterion and return the updated rows."""
        await self._session.execute(
            update(self._entity_type)
            .where(criterion)
            .values(**values)
        )
        await self._session.commit()

        result = await self._session.execute(
            select(self._entity_type).where(criterion)
        )

        return list(result.scalars().all())

    async def delete_async(self, entity_id: str) -> None:
        """Delete the entity with the given id and commit the change."""
        await self._session.execute(
            delete(self._entity_type)
            .where(self._entity_type.id == entity_id)
        )

        await self._session.commit()