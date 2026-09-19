import json
import unittest
from unittest.mock import Mock

from fieldnotes.api import handle_request
from fieldnotes.repository import NoteRepository
from fieldnotes.server import is_allowed_origin
from fieldnotes.service import NoteService


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.repo = NoteRepository()
        self.service = NoteService(self.repo)

    def request(self, method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        return handle_request(method, path, body, self.service)

    def test_create_and_list(self):
        status, _, body = self.request("POST", "/api/notes", {"title": "One", "body": "x", "tags": []})
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertIn("createdAt", created)
        self.assertNotIn("created_at", created)

        status, _, body = self.request("GET", "/api/notes")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["notes"]), 1)

    def test_delete_existing_note(self):
        note = self.service.create_note("One", "x", [])
        status, _, _ = self.request("DELETE", f"/api/notes/{note.id}")
        self.assertEqual(status, 204)

    def test_error_shape(self):
        status, _, body = self.request("POST", "/api/notes", {"title": "", "body": "", "tags": []})
        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertEqual(payload["error"]["code"], "invalid_request")
        self.assertEqual(payload["error"]["message"], "title is required")

    def test_create_rejects_malformed_json(self):
        status, _, body = handle_request("POST", "/api/notes", b"{", self.service)
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_request")

    def test_create_rejects_non_object_json(self):
        status, _, body = handle_request("POST", "/api/notes", b"[]", self.service)
        self.assertEqual(status, 400)
        self.assertIn("JSON object", json.loads(body)["error"]["message"])

    def test_create_rejects_invalid_field_types(self):
        invalid_payloads = (
            {"title": 1, "body": "", "tags": []},
            {"title": "One", "body": None, "tags": []},
            {"title": "One", "body": "", "tags": "research"},
            {"title": "One", "body": "", "tags": ["research", 2]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                status, _, body = self.request("POST", "/api/notes", payload)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body)["error"]["code"], "invalid_request")

    def test_search_uses_camel_case_timestamp(self):
        self.service.create_note("One", "research", [])
        status, _, body = self.request("GET", "/api/search?q=research")
        self.assertEqual(status, 200)
        note = json.loads(body)["notes"][0]
        self.assertIn("createdAt", note)
        self.assertNotIn("created_at", note)

    def test_export_returns_portable_public_note_document(self):
        created = self.service.create_note("One", "research", ["Field Work"])

        status, _, body = self.request("GET", "/api/export")

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"notes": [created.to_dict()]})

    def test_delete_rejects_invalid_ids_and_extra_segments(self):
        for path in (
            "/api/notes/nope",
            "/api/notes/0",
            "/api/notes/-1",
            f"/api/notes/{'9' * 10_000}",
        ):
            with self.subTest(path=path):
                status, _, body = self.request("DELETE", path)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body)["error"]["code"], "invalid_note_id")

        status, _, body = self.request("DELETE", "/api/notes/1/extra")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"]["code"], "not_found")

    def test_create_deduplicates_equivalent_normalized_tags(self):
        status, _, body = self.request(
            "POST",
            "/api/notes",
            {
                "title": "One",
                "body": "",
                "tags": ["Deep Learning", "deep-learning", "AI", " ai "],
            },
        )

        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["tags"], ["deep-learning", "ai"])

    def test_known_route_with_wrong_method_returns_405(self):
        status, _, body = self.request("POST", "/api/search")
        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

        status, _, body = self.request("GET", "/api/import")
        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

        status, _, body = self.request("POST", "/api/export")
        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_import_creates_one_ordered_batch_with_local_ids(self):
        status, _, body = self.request(
            "POST",
            "/api/import",
            {
                "notes": [
                    {
                        "id": 800,
                        "title": "First",
                        "createdAt": "2026-09-12T13:30:00-07:00",
                    },
                    {
                        "id": 900,
                        "title": "Second",
                        "createdAt": "2026-09-12T21:00:00Z",
                    },
                ]
            },
        )

        self.assertEqual(status, 201)
        payload = json.loads(body)
        self.assertEqual(payload["imported"], 2)
        self.assertEqual([note["title"] for note in payload["notes"]], ["First", "Second"])
        self.assertEqual([note["id"] for note in payload["notes"]], [1, 2])
        self.assertEqual(payload["notes"][0]["createdAt"], "2026-09-12T20:30:00+00:00")

    def test_import_invalid_timestamp_causes_zero_mutation(self):
        status, _, body = self.request(
            "POST",
            "/api/import",
            {
                "notes": [
                    {"title": "First"},
                    {"title": "Second", "createdAt": "2026-09-12T20:00:00"},
                ]
            },
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_request")
        self.assertEqual(self.repo.list(), [])

    def test_empty_import_returns_200_without_mutation(self):
        status, _, body = self.request("POST", "/api/import", {"notes": []})

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"imported": 0, "notes": []})
        self.assertEqual(self.repo.list(), [])

    def test_import_storage_value_error_escapes_as_server_failure(self):
        repository = Mock()
        repository.add_many.side_effect = ValueError("storage rejected batch")
        service = NoteService(repository)

        with self.assertRaisesRegex(ValueError, "storage rejected batch"):
            handle_request(
                "POST",
                "/api/import",
                json.dumps({"notes": [{"title": "Valid"}]}).encode(),
                service,
            )

        repository.add_many.assert_called_once()

    def test_cors_origin_is_limited_to_local_ui(self):
        self.assertTrue(is_allowed_origin("null"))
        self.assertTrue(is_allowed_origin("http://localhost:3000"))
        self.assertTrue(is_allowed_origin("http://127.0.0.1:8000"))
        self.assertFalse(is_allowed_origin("https://example.com"))
        self.assertFalse(is_allowed_origin("http://localhost.example.com:8000"))
        self.assertFalse(is_allowed_origin("http://localhost"))


if __name__ == "__main__":
    unittest.main()
