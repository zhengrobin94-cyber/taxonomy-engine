"""
Simple SQLite storage for concepts.
"""

from sqlite3 import Row
from typing import Any
from uuid import UUID

from app.concept.models import Concept
from app.store.base import DB, DBDocumentRelatedTable
from app.utils import get_settings_starting_with


class ConceptDB(DBDocumentRelatedTable[Concept]):
    """A lightweight SQLite3 Table handler for concepts."""

    def __init__(self):
        schema = """
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            definition TEXT,
            chunk_id TEXT NOT NULL,
            page_number INT,
            filename TEXT NOT NULL,
            created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        """
        self.tag_separator = "|"
        db = DB(**get_settings_starting_with("sqlite_", remove_prefix=True))
        super().__init__(db, "CONCEPTS", schema)

    def row_factory(self, concept: Concept) -> dict[str, Any]:
        """Convert a concept to a Table's row.

        Args:
            concept (Concept): Concept to convert to a row.

        Returns:
            dict[str, Any]: Created row.
        """
        return concept.serialize()

    def obj_factory(self, row: Row) -> Concept:
        """Convert a Table's row to a `Concept`.

        Args:
            row (Row): Table's row.

        Returns:
            Concept: Concept created from the row.
        """
        return Concept(**self.row_to_dict(row))

    def get_by_chunk(self, chunk_id: UUID) -> list[Concept]:
        """Get `Concept`s associated with a specific chunk.

        Args:
            chunk_id (UUID): UUID of the chunk.

        Returns:
            list[Concept]: Concepts associated with that chunk, if any.
        """
        sql_statement = f"SELECT * FROM {self.table_name} WHERE chunk_id = ?"
        with self.db.connect() as conn:
            rows = conn.execute(sql_statement, (str(chunk_id),)).fetchall()
        return [self.obj_factory(row) for row in rows]
