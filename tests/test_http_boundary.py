import http.client
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

from fieldnotes.server import MAX_BODY_BYTES
from tests.test_http_persistence import ServerProcess


class HttpBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database = Path(self.temporary_directory.name) / "notes.sqlite3"
        self.server = ServerProcess(database)
        self.server.start()
        self.addCleanup(self.server.stop)

    def raw_request(self, method, path, *, body=None, headers=None):
        parsed = urlparse(self.server.base_url)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            payload = response.read()
            return response.status, dict(response.getheaders()), payload
        finally:
            connection.close()

    def json_body(self, payload):
        return json.dumps(payload).encode()

    def assert_empty_state(self):
        self.assertEqual(self.server.request("GET", "/api/notes"), {"notes": []})

    def test_same_origin_json_mutation_succeeds(self):
        status, headers, body = self.raw_request(
            "POST",
            "/api/notes",
            body=self.json_body({"title": "Allowed", "body": "", "tags": []}),
            headers={
                "Origin": self.server.base_url,
                "Content-Type": "application/json; charset=utf-8",
            },
        )

        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["title"], "Allowed")
        self.assertEqual(headers["Access-Control-Allow-Origin"], self.server.base_url)

    def test_foreign_and_opaque_origins_cannot_mutate_state(self):
        for origin in ("https://example.com", "null", "http://127.0.0.1:1"):
            with self.subTest(origin=origin):
                status, headers, body = self.raw_request(
                    "POST",
                    "/api/notes",
                    body=self.json_body(
                        {"title": "Blocked", "body": "", "tags": []}
                    ),
                    headers={"Origin": origin, "Content-Type": "application/json"},
                )
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(body)["error"]["code"], "origin_not_allowed")
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                self.assert_empty_state()

    def test_wrong_or_missing_json_media_type_cannot_mutate_state(self):
        for content_type in (None, "text/plain", "application/x-www-form-urlencoded"):
            with self.subTest(content_type=content_type):
                headers = {}
                if content_type is not None:
                    headers["Content-Type"] = content_type
                status, _headers, body = self.raw_request(
                    "POST",
                    "/api/notes",
                    body=self.json_body(
                        {"title": "Blocked", "body": "", "tags": []}
                    ),
                    headers=headers,
                )
                self.assertEqual(status, 415)
                self.assertEqual(
                    json.loads(body)["error"]["code"], "unsupported_media_type"
                )
                self.assert_empty_state()

    def test_disallowed_origin_cannot_delete(self):
        created = self.server.request(
            "POST", "/api/notes", {"title": "Keep", "body": "", "tags": []}
        )

        status, _headers, body = self.raw_request(
            "DELETE",
            f"/api/notes/{created['id']}",
            headers={"Origin": "https://example.com"},
        )

        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"]["code"], "origin_not_allowed")
        self.assertEqual(
            self.server.request("GET", "/api/notes")["notes"], [created]
        )

    def test_preflight_and_unsupported_methods_use_json_contract(self):
        status, headers, body = self.raw_request(
            "OPTIONS",
            "/api/notes",
            headers={"Origin": self.server.base_url},
        )
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertIn("POST", headers["Access-Control-Allow-Methods"])

        status, headers, body = self.raw_request("PATCH", "/api/notes")
        self.assertEqual(status, 405)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_oversized_json_body_is_rejected_before_mutation(self):
        status, _headers, body = self.raw_request(
            "POST",
            "/api/notes",
            body=b"",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(MAX_BODY_BYTES + 1),
            },
        )

        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)["error"]["code"], "request_too_large")
        self.assert_empty_state()


if __name__ == "__main__":
    unittest.main()
