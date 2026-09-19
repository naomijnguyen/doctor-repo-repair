import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fieldnotes.exporter import write_export


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.destination = self.directory / "notes.json"
        self.payload = {
            "notes": [
                {
                    "id": 1,
                    "title": "Field observation",
                    "body": "Portable text",
                    "tags": ["field-work"],
                    "createdAt": "2026-09-12T20:30:00+00:00",
                }
            ]
        }

    def temporary_siblings(self):
        return list(self.directory.glob(f".{self.destination.name}.*.tmp"))

    def test_writes_readable_utf8_json_without_replacing_existing_files(self):
        write_export(self.destination, self.payload)

        self.assertEqual(
            json.loads(self.destination.read_text(encoding="utf-8")), self.payload
        )
        self.assertEqual(self.temporary_siblings(), [])

        original = self.destination.read_bytes()
        with self.assertRaises(FileExistsError):
            write_export(self.destination, {"notes": []})
        self.assertEqual(self.destination.read_bytes(), original)

    def test_empty_export_is_a_valid_document(self):
        write_export(self.destination, {"notes": []})

        self.assertEqual(
            json.loads(self.destination.read_text(encoding="utf-8")),
            {"notes": []},
        )

    def test_failed_replace_preserves_previous_bytes_and_cleans_temporary_file(self):
        original = b'{"notes":[{"title":"previous"}]}\n'
        self.destination.write_bytes(original)

        with patch("fieldnotes.exporter.os.replace", side_effect=OSError("blocked")):
            with self.assertRaisesRegex(OSError, "blocked"):
                write_export(self.destination, self.payload, replace=True)

        self.assertEqual(self.destination.read_bytes(), original)
        self.assertEqual(self.temporary_siblings(), [])

    @unittest.skipUnless(hasattr(os, "link"), "requires atomic hard-link publication")
    def test_default_publication_wins_no_overwrite_race(self):
        def competing_publication(_source, destination):
            Path(destination).write_text("competitor", encoding="utf-8")
            raise FileExistsError(destination)

        with patch("fieldnotes.exporter.os.link", side_effect=competing_publication):
            with self.assertRaises(FileExistsError):
                write_export(self.destination, self.payload)

        self.assertEqual(self.destination.read_text(encoding="utf-8"), "competitor")
        self.assertEqual(self.temporary_siblings(), [])


if __name__ == "__main__":
    unittest.main()
