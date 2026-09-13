import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from tests.test_http_persistence import PROJECT_ROOT, ServerProcess


class ImportConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "notes.sqlite3"
        self.servers = []

    def tearDown(self):
        for server in reversed(self.servers):
            server.stop()

    def start_server(self) -> ServerProcess:
        server = ServerProcess(self.database_path)
        self.servers.append(server)
        server.start()
        return server

    def write_payload(self, name: str, payload: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    @staticmethod
    def run_import(path: Path, server: ServerProcess) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                "tools/import_sample.py",
                str(path),
                "--api-url",
                server.base_url,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    def test_cli_batch_is_visible_and_survives_process_restart(self):
        payload_path = self.write_payload(
            "durable-import.json",
            {
                "notes": [
                    {
                        "id": 9001,
                        "title": "  Historical observation  ",
                        "body": "  Preserved through restart.  ",
                        "tags": ["Field Work"],
                        "createdAt": "2026-09-12T13:30:00-07:00",
                    },
                    {
                        "id": 9002,
                        "title": "Current observation",
                        "tags": ["Runtime"],
                    },
                ]
            },
        )
        first_server = self.start_server()

        result = self.run_import(payload_path, first_server)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Imported 2 notes", result.stdout)
        imported = first_server.request("GET", "/api/notes")["notes"]
        self.assertEqual([note["id"] for note in imported], [1, 2])
        self.assertEqual(
            [note["title"] for note in imported],
            ["Historical observation", "Current observation"],
        )
        self.assertEqual(imported[0]["body"], "Preserved through restart.")
        self.assertEqual(imported[0]["tags"], ["field-work"])
        self.assertEqual(imported[0]["createdAt"], "2026-09-12T20:30:00+00:00")
        assigned = datetime.fromisoformat(imported[1]["createdAt"])
        self.assertEqual(assigned.utcoffset(), timedelta(0))
        first_server.stop()

        second_server = self.start_server()
        self.assertEqual(second_server.request("GET", "/api/notes")["notes"], imported)

    def test_mid_batch_storage_failure_rolls_back_and_retry_is_clean(self):
        first_server = self.start_server()
        existing = first_server.request(
            "POST",
            "/api/notes",
            {"title": "Existing", "body": "Keep me", "tags": ["baseline"]},
        )
        first_server.stop()

        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "CREATE TRIGGER reject_second_batch_note BEFORE INSERT ON notes "
            "WHEN NEW.title = 'Reject me' "
            "BEGIN SELECT RAISE(ABORT, 'controlled batch failure'); END"
        )
        connection.close()

        payload_path = self.write_payload(
            "retry-import.json",
            {
                "notes": [
                    {
                        "title": "Would otherwise remain",
                        "createdAt": "2026-09-12T20:31:00Z",
                    },
                    {
                        "title": "Reject me",
                        "createdAt": "2026-09-12T20:32:00Z",
                    },
                ]
            },
        )
        failing_server = self.start_server()

        failed = self.run_import(payload_path, failing_server)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("internal server error", failed.stderr)
        self.assertEqual(
            failing_server.request("GET", "/api/notes")["notes"], [existing]
        )
        failing_server.stop()

        connection = sqlite3.connect(self.database_path)
        connection.execute("DROP TRIGGER reject_second_batch_note")
        connection.close()

        retry_server = self.start_server()
        retried = self.run_import(payload_path, retry_server)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        notes_after_retry = retry_server.request("GET", "/api/notes")["notes"]
        self.assertEqual([note["id"] for note in notes_after_retry], [1, 2, 3])
        self.assertEqual(
            [note["title"] for note in notes_after_retry],
            ["Existing", "Would otherwise remain", "Reject me"],
        )
        retry_server.stop()

        restarted = self.start_server()
        self.assertEqual(
            restarted.request("GET", "/api/notes")["notes"], notes_after_retry
        )

    def test_empty_import_is_no_op_and_does_not_consume_id(self):
        server = self.start_server()
        empty_path = self.write_payload("empty.json", {"notes": []})

        result = self.run_import(empty_path, server)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Imported 0 notes", result.stdout)
        self.assertEqual(server.request("GET", "/api/notes"), {"notes": []})

        created = server.request(
            "POST", "/api/notes", {"title": "First", "body": "", "tags": []}
        )
        self.assertEqual(created["id"], 1)

    def test_later_invalid_timestamp_rejects_complete_import(self):
        server = self.start_server()
        existing = server.request(
            "POST",
            "/api/notes",
            {"title": "Existing", "body": "", "tags": []},
        )
        invalid_path = self.write_payload(
            "invalid-timestamp.json",
            {
                "notes": [
                    {
                        "title": "Valid first record",
                        "createdAt": "2026-09-12T20:30:00Z",
                    },
                    {
                        "title": "Invalid second record",
                        "createdAt": "2026-09-12T13:30:00",
                    },
                ]
            },
        )

        result = self.run_import(invalid_path, server)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("note at index 1", result.stderr)
        self.assertEqual(server.request("GET", "/api/notes")["notes"], [existing])


if __name__ == "__main__":
    unittest.main()
