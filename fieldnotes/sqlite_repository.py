from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

from .models import Note, NoteDraft


SCHEMA_VERSION = 1


class SQLiteNoteRepository:
    """SQLite-backed implementation of the note repository operations."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._connection = sqlite3.connect(
            self.database_path,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row

        try:
            self._initialize_schema()
        except Exception:
            self._connection.close()
            raise

    def list(self) -> list[Note]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, title, body, tags, created_at FROM notes ORDER BY id"
            ).fetchall()
            return [self._note_from_row(row) for row in rows]

    def add(self, title: str, body: str, tags: list[str]) -> Note:
        tags_json = json.dumps(list(tags), ensure_ascii=False)
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                cursor = self._connection.execute(
                    "INSERT INTO notes (title, body, tags, created_at) "
                    "VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'))",
                    (title, body, tags_json),
                )
                row = self._connection.execute(
                    "SELECT id, title, body, tags, created_at FROM notes WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
                self._connection.execute("COMMIT")
            except Exception:
                self._rollback()
                raise

            if row is None:  # Defensive: the insert and select are one transaction.
                raise sqlite3.DatabaseError("inserted note could not be read back")
            return self._note_from_row(row)

    def add_many(self, notes: list[NoteDraft]) -> list[Note]:
        with self._lock:
            created = []
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for draft in notes:
                    cursor = self._connection.execute(
                        "INSERT INTO notes (title, body, tags, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            draft.title,
                            draft.body,
                            json.dumps(list(draft.tags), ensure_ascii=False),
                            draft.created_at,
                        ),
                    )
                    row = self._connection.execute(
                        "SELECT id, title, body, tags, created_at "
                        "FROM notes WHERE id = ?",
                        (cursor.lastrowid,),
                    ).fetchone()
                    if row is None:
                        raise sqlite3.DatabaseError(
                            "inserted batch note could not be read back"
                        )
                    created.append(self._note_from_row(row))
                self._connection.execute("COMMIT")
            except Exception:
                self._rollback()
                raise
            return created

    def delete(self, note_id: int) -> bool:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                cursor = self._connection.execute(
                    "DELETE FROM notes WHERE id = ?", (note_id,)
                )
                self._connection.execute("COMMIT")
            except Exception:
                self._rollback()
                raise
            return cursor.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute("DELETE FROM notes")
                self._connection.execute(
                    "DELETE FROM sqlite_sequence WHERE name = 'notes'"
                )
                self._connection.execute("COMMIT")
            except Exception:
                self._rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteNoteRepository:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _initialize_schema(self) -> None:
        with self._lock:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise sqlite3.DatabaseError(
                    f"unsupported database schema version: {version}"
                )

            user_tables = {
                row["name"]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }

            if version == 0 and user_tables:
                if user_tables != {"notes"}:
                    raise sqlite3.DatabaseError("unrecognized unversioned database")
                self._validate_existing_notes()
            elif version == SCHEMA_VERSION:
                if "notes" not in user_tables:
                    raise sqlite3.DatabaseError("version 1 database is missing notes table")
                self._validate_existing_notes()

            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        body TEXT NOT NULL,
                        tags TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self._connection.execute("COMMIT")
            except Exception:
                self._rollback()
                raise

    def _validate_existing_notes(self) -> None:
        if not self._notes_schema_is_compatible():
            raise sqlite3.DatabaseError("incompatible notes table")

        rows = self._connection.execute(
            "SELECT id, title, body, tags, created_at FROM notes ORDER BY id"
        ).fetchall()
        try:
            for row in rows:
                self._note_from_row(row)
        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
            sqlite3.DatabaseError,
        ) as error:
            raise sqlite3.DatabaseError("unreadable notes data") from error

    def _notes_schema_is_compatible(self) -> bool:
        columns = self._connection.execute("PRAGMA table_info(notes)").fetchall()
        actual = [
            (row["name"], row["type"].upper(), row["notnull"], row["pk"])
            for row in columns
        ]
        expected = [
            ("id", "INTEGER", 0, 1),
            ("title", "TEXT", 1, 0),
            ("body", "TEXT", 1, 0),
            ("tags", "TEXT", 1, 0),
            ("created_at", "TEXT", 1, 0),
        ]
        schema_row = self._connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = 'notes'"
        ).fetchone()
        schema_sql = schema_row["sql"].upper() if schema_row and schema_row["sql"] else ""
        return actual == expected and "AUTOINCREMENT" in schema_sql

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            self._connection.execute("ROLLBACK")

    @staticmethod
    def _note_from_row(row: sqlite3.Row) -> Note:
        tags = json.loads(row["tags"])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise sqlite3.DatabaseError("stored note tags are not a list of strings")
        if not isinstance(row["id"], int):
            raise sqlite3.DatabaseError("stored note ID is not an integer")
        if not isinstance(row["title"], str) or not isinstance(row["body"], str):
            raise sqlite3.DatabaseError("stored note text is not readable")
        if not isinstance(row["created_at"], str):
            raise sqlite3.DatabaseError("stored note timestamp is not text")
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.utcoffset() != timedelta(0):
            raise sqlite3.DatabaseError("stored note timestamp is not UTC")
        return Note(
            id=row["id"],
            title=row["title"],
            body=row["body"],
            tags=tags,
            created_at=row["created_at"],
        )
