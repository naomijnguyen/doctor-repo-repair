import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fieldnotes.composition import create_repository, create_service
from fieldnotes.config import DEFAULT_DATA_FILE
from fieldnotes.server import build_server
from fieldnotes.sqlite_repository import SQLiteNoteRepository


class CompositionTests(unittest.TestCase):
    def test_default_data_path_names_a_sqlite_database(self):
        self.assertEqual(DEFAULT_DATA_FILE, "./data/fieldnotes.sqlite3")

    def test_repository_uses_canonical_configured_data_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "nested" / "notes.sqlite3"
            with patch.dict(
                os.environ, {"FIELDNOTES_DATA": str(database_path)}, clear=True
            ):
                repository = create_repository()
                try:
                    self.assertEqual(repository.database_path, database_path)
                    self.assertTrue(database_path.exists())
                finally:
                    repository.close()

    def test_service_and_repository_share_the_same_state_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "notes.sqlite3"
            service, repository = create_service(database_path)
            try:
                created = service.create_note("Composed", "body", ["Field Work"])
                self.assertEqual(repository.list(), [created])
                self.assertIs(service.repository, repository)
            finally:
                repository.close()

    def test_invalid_database_fails_without_memory_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "notes.sqlite3"
            database_path.write_text("not sqlite", encoding="utf-8")

            with self.assertRaises(sqlite3.DatabaseError):
                create_service(database_path)

            self.assertEqual(database_path.read_text(encoding="utf-8"), "not sqlite")

    def test_server_uses_sqlite_and_supports_ephemeral_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "notes.sqlite3"
            server, repository = build_server(port=0, data_path=database_path)
            try:
                self.assertIsInstance(repository, SQLiteNoteRepository)
                self.assertEqual(server.RequestHandlerClass.service.repository, repository)
                self.assertNotEqual(server.server_address[1], 0)
            finally:
                server.server_close()
                repository.close()

    def test_server_closes_repository_when_binding_fails(self):
        service = MagicMock()
        repository = MagicMock()
        with patch(
            "fieldnotes.server.create_service",
            return_value=(service, repository),
        ), patch(
            "fieldnotes.server.ThreadingHTTPServer",
            side_effect=OSError("port is unavailable"),
        ):
            with self.assertRaisesRegex(OSError, "port is unavailable"):
                build_server(port=8000, data_path="unused.sqlite3")

        repository.close.assert_called_once_with()

    def test_invalid_port_fails_before_creating_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "notes.sqlite3"
            with patch.dict(
                os.environ,
                {"FIELDNOTES_PORT": "not-a-port"},
                clear=True,
            ):
                with self.assertRaises(ValueError):
                    build_server(data_path=database_path)

            self.assertFalse(database_path.exists())


if __name__ == "__main__":
    unittest.main()
