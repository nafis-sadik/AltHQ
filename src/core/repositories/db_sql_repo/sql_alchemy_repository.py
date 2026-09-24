"""SQLAlchemy async implementation of the ISQLRepository interface."""

from typing import Generic, List, Optional, Sequence, Type, TypeVar, Any
from sqlalchemy import Result, Select, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.orm import DeclarativeBase

# 1. Import your interface contract
from core.repositories.db_sql_repo.sql_repository import ISQLRepository

# 2. Bind TEntity to SQLAlchemy Declarative Base for metadata/attribute checking
class Base(DeclarativeBase):
    pass

TEntity = TypeVar("TEntity", bound=Base)

# 3. Maintain strict Interface Segregation (Inheriting from ISQLRepository)
class SQLAlchemyRepository(ISQLRepository[TEntity], Generic[TEntity]):
    """Async repository that maps a declarative entity type to a SQLAlchemy-backed table."""

    def __init__(self, entity_type: Type[TEntity], engine: AsyncEngine) -> None:
        """Initialize the repository with a specific entity type and a shared engine instance."""
        self._entity_type = entity_type
        self._engine = engine
        self._session: Optional[AsyncSession] = None

    async def __aenter__(self) -> "SQLAlchemyRepository[TEntity]":
        """Open a new session and return self for use with 'async with'."""
        self._session = AsyncSession(self._engine, expire_on_commit=False)
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """Handle transaction outcome, close the session safely, and bubble errors."""
        if self._session:
            try:
                if exc_type is not None:
                    await self._session.rollback()
                else:
                    await self._session.commit()
            finally:
                await self._session.close()
                self._session = None

    def __enter__(self) -> "SQLAlchemyRepository[TEntity]":
        raise NotImplementedError("SQLAlchemyRepository is async-only. Use 'async with' instead.")

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        raise NotImplementedError("SQLAlchemyRepository is async-only. Use 'async with' instead.")

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
        assert self._session is not None, "Session not initialized. Use 'async with'."
        self._session.add(entity)
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        await self._session.refresh(entity)
        return entity

    async def bulk_insert_async(self, entities: List[TEntity]) -> List[TEntity]:
        assert self._session is not None, "Session not initialized. Use 'async with'."
        self._session.add_all(entities)
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        for entity in entities:
            await self._session.refresh(entity)
        return entities

    async def get_async(self, entity_id: str) -> Optional[TEntity]:
        assert self._session is not None, "Session not initialized. Use 'async with'."
        return await self._session.get(self._entity_type, entity_id)

    async def get_all_async(self) -> List[TEntity]:
        assert self._session is not None, "Session not initialized. Use 'async with'."
        result = await self._session.execute(select(self._entity_type))
        return list(result.scalars().all())

    async def update_async(self, entity_id: str, values: dict) -> TEntity:
        assert self._session is not None, "Session not initialized. Use 'async with'."
        id_column = getattr(self._entity_type, "id")

        try:
            await self._session.execute(
                update(self._entity_type)
                .where(id_column == entity_id)
                .values(**values)
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        updated = await self.get_async(entity_id)
        if updated is None:
            raise ValueError(f"{self._entity_type.__name__} with id {entity_id} not found")
        return updated

    async def update_by_expression_async(self, criterion: Any, values: dict) -> List[TEntity]:
        assert self._session is not None, "Session not initialized. Use 'async with'."
        try:
            await self._session.execute(
                update(self._entity_type)
                .where(criterion)
                .values(**values)
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        result = await self._session.execute(
            select(self._entity_type).where(criterion)
        )
        return list(result.scalars().all())

    async def delete_async(self, entity_id: str) -> None:
        assert self._session is not None, "Session not initialized. Use 'async with'."
        id_column = getattr(self._entity_type, "id")

        try:
            await self._session.execute(
                delete(self._entity_type)
                .where(id_column == entity_id)
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    def base_query(self) -> Select[tuple[TEntity]]:
        """Starts a query statement that can be dynamically modified later."""        
        return select(self._entity_type)

    async def count_async(self, query: Select) -> int:
        """Count the number of rows that would be returned by the given query."""
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        assert self._session is not None, "Session not initialized. Use 'async with'."
        result = await self._session.execute(count_query)
        return result.scalar_one()

    async def execute_query_async(self, query: Select) -> Result[tuple[TEntity]]:
        """Execute a given SQLAlchemy Select query and return the result."""
        assert self._session is not None, "Session not initialized. Use 'async with'."
        return await self._session.execute(query)