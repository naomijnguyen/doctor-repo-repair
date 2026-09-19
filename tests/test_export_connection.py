import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_http_persistence import PROJECT_ROOT, ServerProcess


class ExportConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.servers = []

    def tearDown(self):
        for server in reversed(self.servers):
            server.stop()

    def start_server(self, database_path: Path) -> ServerProcess:
        server = ServerProcess(database_path)
        self.servers.append(server)
        server.start()
        return server

    @staticmethod
    def meaningful_fields(notes):
        return [
            {
                "title": note["title"],
                "body": note["body"],
                "tags": note["tags"],
                "createdAt": note["createdAt"],
            }
            for note in notes
        ]

    @staticmethod
    def run_command(*arguments):
        return subprocess.run(
            [sys.executable, *arguments],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    def test_real_export_recovers_notes_into_a_separate_database_and_restart(self):
        source_database = self.root / "source.sqlite3"
        destination_database = self.root / "destination.sqlite3"
        export_path = self.root / "portable-notes.json"

        source = self.start_server(source_database)
        source.request(
            "POST",
            "/api/import",
            {
                "notes": [
                    {
                        "id": 9001,
                        "title": "Historical observation",
                        "body": "Preserve this exact text.",
                        "tags": ["Field Work"],
                        "createdAt": "2026-09-12T13:30:00-07:00",
                    },
                    {
                        "id": 9002,
                        "title": "Second observation",
                        "body": "A second durable record.",
                        "tags": ["Runtime"],
                        "createdAt": "2026-09-12T21:00:00Z",
                    },
                ]
            },
        )
        source_notes = source.request("GET", "/api/notes")["notes"]

        exported = self.run_command(
            "tools/export_notes.py",
            str(export_path),
            "--api-url",
            source.base_url,
        )
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertIn("Exported 2 notes", exported.stdout)
        self.assertEqual(json.loads(export_path.read_text())["notes"], source_notes)
        source.stop()

        destination = self.start_server(destination_database)
        imported = self.run_command(
            "tools/import_sample.py",
            str(export_path),
            "--api-url",
            destination.base_url,
        )
        self.assertEqual(imported.returncode, 0, imported.stderr)
        recovered = destination.request("GET", "/api/notes")["notes"]
        self.assertEqual(
            self.meaningful_fields(recovered),
            self.meaningful_fields(source_notes),
        )
        destination.stop()

        restarted = self.start_server(destination_database)
        self.assertEqual(restarted.request("GET", "/api/notes")["notes"], recovered)

    def test_existing_export_is_unchanged_without_explicit_replace(self):
        database = self.root / "source.sqlite3"
        export_path = self.root / "existing.json"
        original = b'{"notes":[{"title":"previous backup"}]}\n'
        export_path.write_bytes(original)
        server = self.start_server(database)
        server.request(
            "POST",
            "/api/notes",
            {"title": "New state", "body": "", "tags": []},
        )

        result = self.run_command(
            "tools/export_notes.py",
            str(export_path),
            "--api-url",
            server.base_url,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(export_path.read_bytes(), original)
        self.assertEqual(list(self.root.glob(f".{export_path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
