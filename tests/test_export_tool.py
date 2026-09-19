import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.export_notes import ApiExportClient, export_notes


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class ExportToolTests(unittest.TestCase):
    def test_client_fetches_one_complete_export_document(self):
        payload = {"notes": [{"id": 1, "title": "One"}]}

        with patch(
            "tools.export_notes.urlopen", return_value=FakeResponse(payload)
        ) as urlopen:
            result = ApiExportClient("http://127.0.0.1:8123/").export_payload()

        self.assertEqual(result, payload)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8123/api/export")
        self.assertEqual(request.method, "GET")

    def test_client_rejects_malformed_success_response(self):
        with patch(
            "tools.export_notes.urlopen", return_value=FakeResponse({"notes": {}})
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid export response"):
                ApiExportClient("http://127.0.0.1:8123").export_payload()

    def test_export_notes_publishes_only_after_valid_response(self):
        payload = {"notes": []}
        client = Mock()
        client.export_payload.return_value = payload

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "notes.json"
            count = export_notes(client, destination)

            self.assertEqual(count, 0)
            self.assertEqual(json.loads(destination.read_text()), payload)


if __name__ == "__main__":
    unittest.main()
