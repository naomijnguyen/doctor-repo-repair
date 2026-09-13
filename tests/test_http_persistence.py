import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ServerProcess:
    """Run the public server entry point in a genuinely separate process."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.port = self._reserve_port()
        self.process = None

    @staticmethod
    def _reserve_port() -> int:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return listener.getsockname()[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "FIELDNOTES_PORT": str(self.port),
                "FIELDNOTES_DATA": str(self.database_path),
                "PYTHONPYCACHEPREFIX": str(
                    self.database_path.parent / "python-cache"
                ),
            }
        )
        self.process = subprocess.Popen(
            [sys.executable, "-m", "fieldnotes.server"],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                self.process = None
                self.fail_startup(stdout, stderr)
            try:
                self.request("GET", "/api/notes")
                return
            except URLError:
                time.sleep(0.02)
        self.stop()
        raise AssertionError("server did not become ready within five seconds")

    @staticmethod
    def fail_startup(stdout: str, stderr: str) -> None:
        raise AssertionError(
            "server exited before becoming ready\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.communicate()
        self.process = None

    def request(self, method: str, path: str, payload=None):
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        with urlopen(request, timeout=1) as response:
            if response.status == 204:
                return None
            return json.loads(response.read())


class HttpPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "notes.sqlite3"
        self.servers = []

    def start_server(self) -> ServerProcess:
        server = ServerProcess(self.database_path)
        self.servers.append(server)
        server.start()
        return server

    def tearDown(self):
        for server in reversed(self.servers):
            server.stop()

    def test_create_and_delete_survive_real_process_restarts(self):
        first_server = self.start_server()
        created = first_server.request(
            "POST",
            "/api/notes",
            {
                "title": "Durable field observation",
                "body": "Created through the public HTTP boundary.",
                "tags": ["Field Work"],
            },
        )
        first_server.stop()

        second_server = self.start_server()
        self.assertEqual(second_server.request("GET", "/api/notes")["notes"], [created])
        self.assertEqual(created["id"], 1)
        self.assertTrue(created["createdAt"].endswith("+00:00"))
        second_server.request("DELETE", f"/api/notes/{created['id']}")
        second_server.stop()

        third_server = self.start_server()
        self.assertEqual(third_server.request("GET", "/api/notes"), {"notes": []})

    def test_corrupt_configured_database_prevents_server_startup(self):
        original = b"not a sqlite database"
        self.database_path.write_bytes(original)

        process = self._start_expected_failure()
        stdout, stderr = process.communicate(timeout=5)

        self.assertNotEqual(process.returncode, 0)
        self.assertIn("DatabaseError", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self.database_path.read_bytes(), original)

    def test_incompatible_configured_database_prevents_server_startup(self):
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
        connection.close()

        process = self._start_expected_failure()
        _stdout, stderr = process.communicate(timeout=5)

        self.assertNotEqual(process.returncode, 0)
        self.assertIn("incompatible notes table", stderr)
        unchanged = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(unchanged.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(
                unchanged.execute(
                    "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = 'notes'"
                ).fetchone()[0],
                original_schema,
            )
            self.assertEqual(
                unchanged.execute("SELECT * FROM notes").fetchall(), original_rows
            )
        finally:
            unchanged.close()

    def _start_expected_failure(self) -> subprocess.Popen:
        port = ServerProcess._reserve_port()
        environment = os.environ.copy()
        environment.update(
            {
                "FIELDNOTES_PORT": str(port),
                "FIELDNOTES_DATA": str(self.database_path),
                "PYTHONPYCACHEPREFIX": str(
                    self.database_path.parent / "python-cache"
                ),
            }
        )
        return subprocess.Popen(
            [sys.executable, "-m", "fieldnotes.server"],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
