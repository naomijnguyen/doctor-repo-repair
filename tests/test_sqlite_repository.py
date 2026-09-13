import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

from fieldnotes.models import NoteDraft
from fieldnotes.repository import NoteRepository
from fieldnotes.sqlite_repository import SCHEMA_VERSION, SQLiteNoteRepository


class RepositoryConformanceMixin:
    def make_repository(self):
        raise NotImplementedError

    def test_add_list_delete_and_clear(self):
        repository = self.make_repository()
        first = repository.add("first", "body", ["field-work"])
        second = repository.add("second", "", [])

        self.assertEqual([note.id for note in repository.list()], [1, 2])
        self.assertTrue(repository.delete(first.id))
        self.assertFalse(repository.delete(first.id))
        self.assertEqual([note.id for note in repository.list()], [second.id])

        repository.clear()
        self.assertEqual(repository.list(), [])
        self.assertEqual(repository.add("after clear", "", []).id, 1)

    def test_returned_notes_do_not_mutate_storage(self):
        repository = self.make_repository()
        source_tags = ["field-work"]
        added = repository.add("note", "body", source_tags)
        source_tags.append("source-mutated")
        added.tags.append("result-mutated")
        listed = repository.list()
        listed[0].tags.append("list-mutated")
        listed.clear()

        stored = repository.list()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].tags, ["field-work"])

    def test_add_many_preserves_order_assigns_local_ids_and_timestamps(self):
        repository = self.make_repository()
        drafts = [
            NoteDraft("first", "one", ("field-work",), "2026-09-12T20:00:00+00:00"),
            NoteDraft("second", "two", (), "2026-09-12T21:00:00+00:00"),
        ]

        created = repository.add_many(drafts)

        self.assertEqual([note.id for note in created], [1, 2])
        self.assertEqual([note.title for note in created], ["first", "second"])
        self.assertEqual(
            [note.created_at for note in created],
            ["2026-09-12T20:00:00+00:00", "2026-09-12T21:00:00+00:00"],
        )
        self.assertEqual(repository.list(), created)

    def test_empty_add_many_does_not_consume_an_id(self):
        repository = self.make_repository()
        self.assertEqual(repository.add_many([]), [])
        self.assertEqual(repository.add("after empty", "", []).id, 1)

    def test_single_add_cannot_interleave_inside_batch_ids(self):
        repository = self.make_repository()
        start = Barrier(2)
        drafts = [
            NoteDraft(
                f"batch-{number}",
                "",
                (),
                f"2026-09-12T20:{number:02d}:00+00:00",
            )
            for number in range(40)
        ]

        def add_batch():
            start.wait()
            return repository.add_many(drafts)

        def add_single():
            start.wait()
            return repository.add("single", "", [])

        with ThreadPoolExecutor(max_workers=2) as executor:
            batch_future = executor.submit(add_batch)
            single_future = executor.submit(add_single)
            batch = batch_future.result()
            single = single_future.result()

        batch_ids = [note.id for note in batch]
        self.assertEqual(
            batch_ids,
            list(range(batch_ids[0], batch_ids[0] + len(batch_ids))),
        )
        self.assertNotIn(single.id, batch_ids)


class MemoryRepositoryConformanceTests(RepositoryConformanceMixin, unittest.TestCase):
    def make_repository(self):
        return NoteRepository()


class SQLiteRepositoryTests(RepositoryConformanceMixin, unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "nested" / "notes.db"
        self.repositories = []

    def tearDown(self):
        for repository in reversed(self.repositories):
            try:
                repository.close()
            except sqlite3.ProgrammingError:
                pass
        self.temporary_directory.cleanup()

    def make_repository(self):
        repository = SQLiteNoteRepository(self.database_path)
        self.repositories.append(repository)
        return repository

    def test_schema_version_is_recorded(self):
        repository = self.make_repository()
        version = repository._connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, SCHEMA_VERSION)

    def test_committed_note_survives_close_and_reopen(self):
        repository = self.make_repository()
        created = repository.add("durable", "body", ["field-work"])
        created_at = datetime.fromisoformat(created.created_at)
        self.assertEqual(created_at.utcoffset(), timezone.utc.utcoffset(created_at))
        repository.close()

        reopened = self.make_repository()
        self.assertEqual(reopened.list(), [created])

    def test_committed_delete_survives_close_and_reopen(self):
        repository = self.make_repository()
        first = repository.add("delete me", "", [])
        survivor = repository.add("keep me", "", [])
        self.assertTrue(repository.delete(first.id))
        repository.close()

        reopened = self.make_repository()
        self.assertEqual(reopened.list(), [survivor])

    def test_failed_write_rolls_back_and_connection_remains_usable(self):
        repository = self.make_repository()
        existing = repository.add("existing", "", [])
        repository._connection.execute(
            "CREATE TRIGGER reject_blocked_title BEFORE INSERT ON notes "
            "WHEN NEW.title = 'blocked' BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "blocked"):
            repository.add("blocked", "", [])

        self.assertEqual(repository.list(), [existing])
        self.assertEqual(repository.add("after failure", "", []).id, 2)

    def test_failed_batch_rolls_back_preserves_existing_and_retries_cleanly(self):
        repository = self.make_repository()
        existing = repository.add("existing", "body", ["saved"])
        drafts = [
            NoteDraft("first", "", (), "2026-09-12T20:00:00+00:00"),
            NoteDraft("blocked", "", (), "2026-09-12T21:00:00+00:00"),
            NoteDraft("third", "", (), "2026-09-12T22:00:00+00:00"),
        ]
        repository._connection.execute(
            "CREATE TRIGGER reject_blocked_batch BEFORE INSERT ON notes "
            "WHEN NEW.title = 'blocked' BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "blocked"):
            repository.add_many(drafts)

        self.assertEqual(repository.list(), [existing])
        repository._connection.execute("DROP TRIGGER reject_blocked_batch")
        retried = repository.add_many(drafts)
        self.assertEqual([note.id for note in retried], [2, 3, 4])
        self.assertEqual(
            [note.title for note in repository.list()],
            ["existing", "first", "blocked", "third"],
        )

    def test_concurrent_adds_assign_unique_sequential_ids(self):
        repository = self.make_repository()
        worker_count = 8
        notes_per_worker = 40
        start = Barrier(worker_count)

        def add_notes(worker):
            start.wait()
            for number in range(notes_per_worker):
                repository.add(f"worker-{worker}-{number}", "", [])

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            list(executor.map(add_notes, range(worker_count)))

        ids = sorted(note.id for note in repository.list())
        self.assertEqual(ids, list(range(1, worker_count * notes_per_worker + 1)))

    def test_invalid_database_fails_visibly(self):
        self.database_path.parent.mkdir(parents=True)
        self.database_path.write_text("this is not sqlite", encoding="utf-8")

        with self.assertRaises(sqlite3.DatabaseError):
            SQLiteNoteRepository(self.database_path)

        self.assertEqual(
            self.database_path.read_text(encoding="utf-8"), "this is not sqlite"
        )

    def test_unknown_schema_version_fails_visibly(self):
        self.database_path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA user_version = 99")
        connection.close()

        with self.assertRaisesRegex(sqlite3.DatabaseError, "schema version: 99"):
            SQLiteNoteRepository(self.database_path)

    def test_unversioned_incompatible_notes_table_is_not_modified(self):
        self.database_path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "CREATE TABLE notes (legacy_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO notes (legacy_id, payload) VALUES (?, ?)",
            ("legacy-1", "irreplaceable field note"),
        )
        connection.commit()
        original_schema = connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = 'notes'"
        ).fetchone()[0]
        original_rows = connection.execute("SELECT * FROM notes").fetchall()
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
        connection.close()

        with self.assertRaisesRegex(sqlite3.DatabaseError, "incompatible notes table"):
            SQLiteNoteRepository(self.database_path)

        unchanged = sqlite3.connect(self.database_path)
        self.assertEqual(unchanged.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(
            unchanged.execute(
                "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = 'notes'"
            ).fetchone()[0],
            original_schema,
        )
        self.assertEqual(unchanged.execute("SELECT * FROM notes").fetchall(), original_rows)
        unchanged.close()

    def test_unversioned_compatible_notes_table_is_adopted_without_data_loss(self):
        self.database_path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                tags TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO notes (title, body, tags, created_at) VALUES (?, ?, ?, ?)",
            (
                "existing compatible note",
                "preserve me",
                '["field-work"]',
                "2026-09-12T20:30:00+00:00",
            ),
        )
        connection.commit()
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
        connection.close()

        repository = self.make_repository()

        self.assertEqual(
            [note.to_dict() for note in repository.list()],
            [
                {
                    "id": 1,
                    "title": "existing compatible note",
                    "body": "preserve me",
                    "tags": ["field-work"],
                    "createdAt": "2026-09-12T20:30:00+00:00",
                }
            ],
        )
        self.assertEqual(
            repository._connection.execute("PRAGMA user_version").fetchone()[0],
            SCHEMA_VERSION,
        )
        self.assertEqual(repository.add("next note", "", []).id, 2)

    def test_unversioned_database_with_unrelated_table_is_not_modified(self):
        self.database_path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "CREATE TABLE observations (observation_id TEXT PRIMARY KEY, payload TEXT)"
        )
        connection.execute(
            "INSERT INTO observations VALUES (?, ?)",
            ("observation-1", "belongs to another application"),
        )
        connection.commit()
        original_schema = connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY name"
        ).fetchall()
        original_rows = connection.execute("SELECT * FROM observations").fetchall()
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
        connection.close()

        with self.assertRaisesRegex(
            sqlite3.DatabaseError, "unrecognized unversioned database"
        ):
            SQLiteNoteRepository(self.database_path)

        unchanged = sqlite3.connect(self.database_path)
        self.assertEqual(unchanged.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(
            unchanged.execute(
                "SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY name"
            ).fetchall(),
            original_schema,
        )
        self.assertEqual(
            unchanged.execute("SELECT * FROM observations").fetchall(), original_rows
        )
        unchanged.close()

    def test_version_one_database_missing_notes_table_is_not_modified(self):
        self.database_path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO metadata VALUES ('owner', 'field-notes')")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
        original_schema = connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY name"
        ).fetchall()
        original_rows = connection.execute("SELECT * FROM metadata").fetchall()
        connection.close()

        with self.assertRaisesRegex(sqlite3.DatabaseError, "missing notes table"):
            SQLiteNoteRepository(self.database_path)

        unchanged = sqlite3.connect(self.database_path)
        self.assertEqual(
            unchanged.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION
        )
        self.assertEqual(
            unchanged.execute(
                "SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY name"
            ).fetchall(),
            original_schema,
        )
        self.assertEqual(unchanged.execute("SELECT * FROM metadata").fetchall(), original_rows)
        unchanged.close()

    def test_unversioned_compatible_table_with_unreadable_rows_is_not_adopted(self):
        self.database_path.parent.mkdir(parents=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                tags TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO notes (title, body, tags, created_at) VALUES (?, ?, ?, ?)",
            (
                "unreadable note",
                "preserve this raw row",
                "not valid JSON",
                "2026-09-12T20:30:00+00:00",
            ),
        )
        connection.commit()
        original_schema = connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY name"
        ).fetchall()
        original_rows = connection.execute("SELECT * FROM notes").fetchall()
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
        connection.close()

        with self.assertRaisesRegex(sqlite3.DatabaseError, "unreadable notes data"):
            SQLiteNoteRepository(self.database_path)

        unchanged = sqlite3.connect(self.database_path)
        self.assertEqual(unchanged.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(
            unchanged.execute(
                "SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY name"
            ).fetchall(),
            original_schema,
        )
        self.assertEqual(unchanged.execute("SELECT * FROM notes").fetchall(), original_rows)
        unchanged.close()


if __name__ == "__main__":
    unittest.main()
