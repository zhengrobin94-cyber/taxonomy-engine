"""
Simple SQLite storage for taxonomy.
"""

from __future__ import annotations

from sqlite3 import Row
from typing import Any, TYPE_CHECKING

from app.store.base import DB, DBTable
from app.utils import get_settings_starting_with

if TYPE_CHECKING:
    from app.taxonomy.taxonomy import Taxonomy


class TaxonomyDB(DBTable["Taxonomy"]):
    """A lightweight SQLite3 Table handler for taxonomies."""

    def __init__(self):
        schema = """
            id TEXT PRIMARY KEY,
            tree TEXT NOT NULL,
            chroma_collection TEXT NOT NULL,
            created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        """
        db = DB(**get_settings_starting_with("sqlite_", remove_prefix=True))
        super().__init__(db, "TAXONOMY", schema)

    def row_factory(self, taxonomy: Taxonomy) -> dict[str, Any]:
        """Convert a taxonomy to a Table's row.

        Args:
            taxonomy (Taxonomy): Taxonomy to convert to a row.

        Returns:
            dict[str, Any]: Created row.
        """
        return taxonomy.serialize()

    def obj_factory(self, row: Row) -> dict[str, Any]:
        """Convert a Table's row to a taxonomy dictionary.

        Args:
            row (Row): Table's row.

        Returns:
            dict[str, Any]: Taxonomy dictionary.
        """
        # To avoid cyclic import, we don't return a Taxonomy instance here.
        return self.row_to_dict(row)
