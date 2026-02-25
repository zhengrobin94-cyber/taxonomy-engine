"""
Simple SQLite storage for chunks.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Optional, Generic, TypeVar
from uuid import UUID


T = TypeVar("T", bound="DBTable[Any]")


class DB:
    """A lightweight SQLite3 database handler."""

    def __init__(self, database: str, **kwargs):
        """A lightweight SQLite3 database handler.

        Args:
            database (str): Name/location of the database. If it doesn't exist, will be created.
        """
        self.database = database
        self.kwargs = kwargs
        self.conn: Optional[sqlite3.Connection] = None

        # Create parent directories if they do not exist
        Path(self.database.removeprefix("file:")).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        """Context for creating a connection that handles commits and rollbacks."""
        # Commit and Rollback are guaranteed thanks to the context manager
        try:
            with sqlite3.connect(self.database, **self.kwargs) as conn:
                self.conn = conn
                yield conn
        finally:
            if self.conn:
                self.conn.close()


class DBTable(Generic[T], ABC):
    """Abstract class representing a Table in a SQLite3 database."""

    def __init__(self, db: DB, table_name: str, schema: str):
        """Abstract class representing a table in a SQLite3 database.

        Args:
            db (DB): SQLite3 database from which the table should originate from.
            table_name (str): Table's name.
            schema (str): Table's schema.
        """
        self.db = db
        self.table_name = table_name
        self.create_table(schema)

    @abstractmethod
    def row_factory(self, x: T) -> dict[str, Any]:
        """Convert the object associated to the Table to a Table's row."""
        pass

    @abstractmethod
    def obj_factory(self, row: sqlite3.Row) -> T:
        """Convert a table's row to the object associated with the Table."""
        pass

    def create_table(self, schema: str) -> None:
        """Create a table with the give schema in the SQLite3 database.

        Args:
            schema (str): Table's schema.
        """
        sql_statement = f"CREATE TABLE IF NOT EXISTS {self.table_name} ({schema})"
        with self.db.connect() as conn:
            conn.execute(sql_statement)

    def _insert_statement(self, **kwargs) -> str:
        """Generate an INSERT statement."""
        columns = ", ".join(kwargs.keys())
        variables = ", ".join(["?"] * len(kwargs))
        return f"INSERT OR REPLACE INTO {self.table_name} ({columns}) VALUES ({variables})"

    def insert(self, x: T) -> None:
        """Insert an object into the Table.

        Replace if object already exists into the Table.

        Args:
            x (T): Object to insert.
        """
        row = self.row_factory(x)
        sql_statement = self._insert_statement(**row)
        with self.db.connect() as conn:
            conn.execute(sql_statement, list(row.values()))

    def insert_many(self, x: Iterable[T]) -> None:
        """Insert multiple objects into the Table.


        Args:
            x (Iterable[T]): Objects to insert.
        """
        rows = [self.row_factory(_x) for _x in x]
        sql_statement = self._insert_statement(**rows[0])
        with self.db.connect() as conn:
            conn.executemany(sql_statement, [list(row.values()) for row in rows])

    def get_by_id(self, id: UUID) -> Optional[T]:
        """Retrieve an object from the Table by its id.

        Args:
            id (UUID): Object's id.

        Returns:
            Optional[T]: Object, if found.
        """
        sql_statement = f"SELECT * FROM {self.table_name} WHERE id = ?"
        with self.db.connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor().execute(sql_statement, (str(id),))
            row = cursor.fetchone()
        if not row:
            return None
        return self.obj_factory(row)

    def delete(self, id: UUID) -> None:
        """Remove an object from the Table, given its id.

        Args:
            id (UUID): Object's id.
        """
        sql_statement = f"DELETE FROM {self.table_name} WHERE id = ?"
        with self.db.connect() as conn:
            conn.execute(sql_statement, (str(id),))

    def delete_old_records(self, older_than_x_days: int) -> None:
        """Remove from the Table, objects that have been inserted more than x days ago.

        Args:
            older_than_x_days (int): Number of days from which to consider a object old.
        """
        sql_statement = f"DELETE FROM {self.table_name} WHERE created < DATETIME('now', ?)"
        parameter = f"-{older_than_x_days} days"
        with self.db.connect() as conn:
            conn.execute(sql_statement, (parameter,))

    def truncate(self) -> None:
        """Drop the table but keep the schema."""
        sql_statement = f"DELETE FROM {self.table_name}"
        with self.db.connect() as conn:
            conn.execute(sql_statement)

    @staticmethod
    def row_to_dict(row: sqlite3.Row, fields_to_exclude: tuple[str] = ("created",)) -> dict[str, Any]:
        """Cast a row to a dictionary.

        Args:
            row (sqlite3.Row): Row to be casted to a dictionary.
            fields_to_exclude (tuple[str], optional): Fields to exclude from the dictionary. Defaults to ("created",).

        Returns:
            dict[str, Any]: Dictionary representing the row.
        """
        return {key: value for key, value in zip(row.keys(), row) if key not in fields_to_exclude}


class DBDocumentRelatedTable(DBTable[T]):
    """Class representing a Table containing objects that are associated to documents."""

    def delete_by_document(self, filename: str) -> None:
        """Remove all records associated to a document.

        Args:
            filename (str): Document's filename.
        """
        sql_statement = f"DELETE FROM {self.table_name} WHERE filename = ?"
        with self.db.connect() as conn:
            conn.execute(sql_statement, (filename,))

    def get_by_document(self, filename: str, limit: int = -1, offset: int = 0) -> list[T]:
        """Get objects associated to a document.

        Args:
            filename (str): Document's filename.
            limit (int, optional): Number of objects to extract. Defaults to -1.
            offset (int, optional): Offset the results by that value. Defaults to 0.

        Returns:
            list[T]: Objects extracted.
        """
        sql_statement = f"SELECT * FROM {self.table_name} WHERE filename = ?"
        parameters = [filename]
        if limit != -1:
            sql_statement += " LIMIT ? OFFSET ?"
            parameters.extend([limit, offset])
        with self.db.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql_statement, tuple(parameters)).fetchall()
        return [self.obj_factory(row) for row in rows]
