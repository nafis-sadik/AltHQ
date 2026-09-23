"""UnQLite-backed implementation of the INoSQLRepository interface with transactional context-manager support."""

import json

from dataclasses import asdict
import sys
from typing import Generic, List, Optional, Type, TypeVar

from core.repositories.db_no_sql_repo import INoSQLRepository
from unqlite import UnQLite

T = TypeVar("T")


class UnQliteRepository(INoSQLRepository[T], Generic[T]):
    """Stores entities as JSON documents in a key-value UnQLite database file."""

    def __init__(self, db_path: str, entity_type: Type[T], collection_name: str) -> None:
        """Open the UnQLite database and configure the entity type and collection prefix."""
        self._db: UnQLite = UnQLite(db_path)
        self._entity_type: Type[T] = entity_type
        self._collection_name: str = collection_name

    def _key(self, entity_id: str) -> str:
        """Build the storage key for an entity id by prefixing it with the collection name."""
        return f"{self._collection_name}:{entity_id}"

    def __enter__(self) -> "UnQliteRepository[T]":
        """Return self so the repository can be used as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Commit on success, roll back on error, and always close the database.

        Returns False so any exception from the 'with' block propagates naturally.
        """
        if not self._db:
            return False

        try:
            if exc_type is not None:
                # 1. ROLLBACK ON ERROR
                # An exception occurred inside the 'with' block.
                # Explicitly disable autocommit to discard pending memory writes before closing.
                print(f"Error detected: {exc_val}. Discarding uncommitted changes.")
                self._db.disable_autocommit()
            else:
                # 2. COMMIT ON SUCCESS
                # Code finished smoothly. UnQLite will auto-commit changes upon .close().
                print("Transaction successful. Saving changes to file...")

        except Exception as cleanup_err:
            print(f"Failed during pre-closing transaction checks: {cleanup_err}", file=sys.stderr)

        finally:
            # 3. DISPOSE & CLOSE RESOURCES
            # Always close the DB to release filesystem locks, regardless of whether a crash occurred.
            print("Disposing UnQLite engine and closing file handle.")
            self._db.close()
            self._db = None  # Free memory reference

        # Return False to let any exceptions bubble up to the global scope naturally
        return False

    def add(self, entity_id: str, entity: T) -> None:
        """Store the entity as JSON under the given id."""
        self._db[self._key(entity_id)] = json.dumps(asdict(entity))

    def get(self, entity_id: str) -> Optional[T]:
        """Return the entity stored under entity_id, or None if it does not exist."""
        try:
            data = self._db[self._key(entity_id)]
            return self._entity_type(
                **json.loads(data)
            )
        except KeyError:
            return None

    def get_all(self) -> List[T]:
        """Return every entity whose key starts with the collection prefix."""
        entities = []
        prefix = f"{self._collection_name}:"
        for key, value in self._db:
            if key.startswith(prefix):
                entities.append(
                    self._entity_type(
                        **json.loads(value)
                        )
                    )

        return entities

    def update(self, entity_id: str, entity: T) -> None:
        """Overwrite the entity stored under entity_id with the new entity."""
        self._db[self._key(entity_id)] = json.dumps(
            asdict(entity)
        )

    def delete(self, entity_id: str) -> None:
        """Remove the entity stored under entity_id, ignoring the error if absent."""
        try:
            del self._db[self._key(entity_id)]
        except KeyError:
            pass