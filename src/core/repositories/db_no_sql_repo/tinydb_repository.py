"""TinyDB-backed implementation of the INoSQLRepository interface."""

from dataclasses import asdict
import sys
from typing import Generic, List, Optional, Type, TypeVar

from core.repositories.db_no_sql_repo.no_sql_repository import INoSQLRepository
from tinydb import TinyDB, Query

T = TypeVar("T")

class TinyDbRepository(INoSQLRepository[T], Generic[T]):
    """Stores serialized entities in a TinyDB JSON file under a named table."""

    def __init__(self, db_path: str, entity_type: Type[T], table_name: str) -> None:
        """Open the TinyDB database and select the table used to store entities."""
        self._entity_type = entity_type
        self._db = TinyDB(db_path)
        self._table = self._db.table(table_name)

    def __enter__(self) -> "TinyDbRepository[T]":
        """Return self so the repository can be used as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the database, mirroring the UnQLite context-manager lifecycle.

        Returns False so any exception from the 'with' block propagates naturally.
        """
        if not self._db:
            return False

        try:
            if exc_type is not None:
                # 1. ROLLBACK ON ERROR
                # An exception occurred inside the 'with' block. TinyDB persists writes
                # incrementally and offers no rollback API, so pending in-memory state is
                # simply discarded before closing.
                print(f"Error detected: {exc_val}. Discarding uncommitted changes.")
            else:
                # 2. COMMIT ON SUCCESS
                # Code finished smoothly. Closing the DB flushes all writes to the file.
                print("Transaction successful. Saving changes to file...")

        except Exception as cleanup_err:
            print(f"Failed during pre-closing transaction checks: {cleanup_err}", file=sys.stderr)

        finally:
            # 3. DISPOSE & CLOSE RESOURCES
            # Always close the DB to release filesystem locks, regardless of whether a crash occurred.
            print("Disposing TinyDB engine and closing file handle.")
            self._db.close()
            self._db = None  # Free memory reference
            self._table = None

        # Return False to let any exceptions bubble up to the global scope naturally
        return False

    def add(self, entity_id: str, entity: T) -> None:
        """Insert the entity's fields as a new row in the table."""
        self._table.insert({"id": entity_id, **asdict(entity)})

    def get(self, entity_id: str) -> Optional[T]:
        """Return the entity whose id matches entity_id, or None if it does not exist."""
        result = self._table.get(Query().id == entity_id)

        if result is None:
            return None

        return self._entity_type(**result)

    def get_all(self) -> List[T]:
        """Return every row in the table reconstructed as entity objects."""
        return [
            self._entity_type(**row)
            for row in self._table.all()
        ]

    def update(self, entity_id: str, entity: T) -> None:
        """Overwrite the row matching entity_id with the new entity's fields."""
        self._table.update(
            asdict(entity),
            Query().id == entity_id,
        )

    def delete(self, entity_id: str) -> None:
        """Remove every row matching entity_id from the table."""
        self._table.remove(Query().id == entity_id)