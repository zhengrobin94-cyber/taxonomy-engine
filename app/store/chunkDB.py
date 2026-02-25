"""
SQLite storage for chunks.
"""

from typing import Any
from sqlite3 import Row

from app.chunk.models import SemanticChunk
from app.store.base import DB, DBDocumentRelatedTable
from app.utils import get_settings_starting_with


class ChunkDB(DBDocumentRelatedTable[SemanticChunk]):
    """A lightweight SQLite3 Table handler for chunks."""

    def __init__(self):
        schema = """
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            page_number INT NOT NULL,
            page_tags TEXT,
            filename TEXT NOT NULL,
            created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        """
        self.tag_separator = "|"
        db = DB(**get_settings_starting_with("sqlite_", remove_prefix=True))
        super().__init__(db, "CHUNKS", schema)

    def row_factory(self, chunk: SemanticChunk) -> dict[str, Any]:
        """Convert a chunk to a Table's row.

        Args:
            chunk (SemanticChunk): Chunk to convert to a row.

        Returns:
            dict[str, Any]: Created row.
        """
        return chunk.serialize(list_separator=self.tag_separator)

    def obj_factory(self, row: Row) -> SemanticChunk:
        """Convert a Table's row to a `SemanticChunk`.

        Args:
            row (Row): Table's row.

        Returns:
            SemanticChunk: Chunk created from the row.
        """
        x = self.row_to_dict(row)
        x["page_tags"] = x.get("page_tags").split(self.tag_separator)
        return SemanticChunk(**x)
