import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tools.import_sample import ApiImportClient, read_import_payload


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class ImportToolTests(unittest.TestCase):
    @patch("tools.import_sample.urlopen")
    def test_client_posts_one_complete_payload_to_batch_route(self, urlopen):
        payload = {
            "notes": [
                {
                    "id": 9001,
                    "title": "Observation",
                    "createdAt": "2026-09-12T13:30:00-07:00",
                },
                {"title": "Follow-up", "extra": "preserved for the server"},
            ]
        }
        response = {"imported": 2, "notes": [{"id": 1}, {"id": 2}]}
        urlopen.return_value = FakeResponse(response)
        client = ApiImportClient("http://127.0.0.1:8000/")

        result = client.import_payload(payload)

        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8000/api/import")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(json.loads(request.data), payload)
        self.assertEqual(result, response)

    @patch("tools.import_sample.urlopen")
    def test_empty_batch_response_is_accepted(self, urlopen):
        urlopen.return_value = FakeResponse({"imported": 0, "notes": []})

        result = ApiImportClient("http://127.0.0.1:8000").import_payload(
            {"notes": []}
        )

        self.assertEqual(result, {"imported": 0, "notes": []})
        urlopen.assert_called_once()

    @patch("tools.import_sample.urlopen")
    def test_api_error_preserves_useful_message_without_retry(self, urlopen):
        error_body = BytesIO(
            json.dumps(
                {
                    "error": {
                        "code": "invalid_request",
                        "message": "note at index 1 requires a non-empty title",
                    }
                }
            ).encode()
        )
        urlopen.side_effect = HTTPError(
            "http://127.0.0.1:8000/api/import",
            400,
            "Bad Request",
            {},
            error_body,
        )

        with self.assertRaisesRegex(RuntimeError, "note at index 1"):
            ApiImportClient("http://127.0.0.1:8000").import_payload(
                {"notes": [{"title": ""}]}
            )

        urlopen.assert_called_once()

    @patch("tools.import_sample.urlopen")
    def test_connection_error_names_the_api_origin(self, urlopen):
        urlopen.side_effect = URLError("connection refused")

        with self.assertRaisesRegex(RuntimeError, "http://127.0.0.1:8123"):
            ApiImportClient("http://127.0.0.1:8123").import_payload({"notes": []})

        urlopen.assert_called_once()

    @patch("tools.import_sample.urlopen")
    def test_invalid_success_response_is_not_reported_as_success(self, urlopen):
        urlopen.return_value = FakeResponse({"notes": []})

        with self.assertRaisesRegex(RuntimeError, "invalid import response"):
            ApiImportClient("http://127.0.0.1:8000").import_payload({"notes": []})

    def test_read_import_payload_preserves_original_fields(self):
        payload = {
            "notes": [
                {
                    "id": 42,
                    "title": "Historical note",
                    "createdAt": "2026-09-12T13:30:00-07:00",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            self.assertEqual(read_import_payload(path), payload)

    def test_malformed_import_file_has_a_useful_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text("not JSON", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "Could not read import file"):
                read_import_payload(path)


if __name__ == "__main__":
    unittest.main()
