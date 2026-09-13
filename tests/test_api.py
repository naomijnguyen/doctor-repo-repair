import json
import unittest

from fieldnotes.api import handle_request
from fieldnotes.repository import NoteRepository
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
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
