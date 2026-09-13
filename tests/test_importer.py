import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fieldnotes.helpers.text import normalize_tag as legacy_normalize_tag
from fieldnotes.importer import import_notes, validate_import_payload
from fieldnotes.legacy_adapter import note_to_frontend
from fieldnotes.repository import NoteRepository
from fieldnotes.utils import normalize_tag


class ImportTests(unittest.TestCase):
    def test_imports_notes(self):
        repo = NoteRepository()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(
                json.dumps(
                    {
                        "notes": [
                            {
                                "title": "  A  ",
                                "body": "  Body  ",
                                "tags": ["Deep Learning", "AI/ML", "!"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(import_notes(path, repo), 1)
            note = repo.list()[0]
            self.assertEqual((note.title, note.body), ("A", "Body"))
            self.assertEqual(note.tags, ["deep-learning", "aiml"])

    def test_file_import_delegates_to_one_batch_operation(self):
        class BatchSpyRepository(NoteRepository):
            def __init__(self):
                super().__init__()
                self.batch_calls = 0

            def add_many(self, notes):
                self.batch_calls += 1
                return super().add_many(notes)

        repo = BatchSpyRepository()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(
                json.dumps({"notes": [{"title": "A"}, {"title": "B"}]}),
                encoding="utf-8",
            )

            self.assertEqual(import_notes(path, repo), 2)

        self.assertEqual(repo.batch_calls, 1)
        self.assertEqual([note.title for note in repo.list()], ["A", "B"])

    def test_invalid_note_does_not_partially_import(self):
        repo = NoteRepository()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(
                json.dumps({"notes": [{"title": "Valid"}, {"title": "  "}]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "index 1.*non-empty title"):
                import_notes(path, repo)

            self.assertEqual(repo.list(), [])

    def test_requires_notes_list(self):
        repo = NoteRepository()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(json.dumps({"notes": {}}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "'notes' list"):
                import_notes(path, repo)

    def test_validates_typed_drafts_in_input_order_and_ignores_source_ids(self):
        drafts = validate_import_payload(
            {
                "notes": [
                    {
                        "id": 9001,
                        "title": "  First  ",
                        "body": "  Body  ",
                        "tags": ["Field Work"],
                        "createdAt": "2026-09-12T13:30:00-07:00",
                    },
                    {
                        "title": "Second",
                        "createdAt": "2026-09-12T21:00:00Z",
                    },
                ]
            }
        )

        self.assertEqual([draft.title for draft in drafts], ["First", "Second"])
        self.assertEqual(drafts[0].body, "Body")
        self.assertEqual(drafts[0].tags, ("field-work",))
        self.assertEqual(drafts[0].created_at, "2026-09-12T20:30:00+00:00")
        self.assertEqual(drafts[1].created_at, "2026-09-12T21:00:00+00:00")
        self.assertFalse(hasattr(drafts[0], "id"))

    def test_missing_timestamp_is_assigned_in_utc(self):
        fixed = datetime(2026, 9, 12, 20, 30, tzinfo=timezone.utc)
        with patch("fieldnotes.importer._utc_now", return_value=fixed):
            drafts = validate_import_payload({"notes": [{"title": "A"}]})

        self.assertEqual(drafts[0].created_at, "2026-09-12T20:30:00+00:00")

    def test_invalid_timestamp_anywhere_rejects_entire_payload(self):
        invalid_values = (
            "2026-09-12T20:30:00",
            "2026-09-12",
            "not a timestamp",
            "",
            None,
            7,
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "index 1.*createdAt"):
                    validate_import_payload(
                        {
                            "notes": [
                                {"title": "Valid"},
                                {"title": "Invalid", "createdAt": value},
                            ]
                        }
                    )

    def test_empty_payload_validates_to_empty_draft_list(self):
        self.assertEqual(validate_import_payload({"notes": []}), [])

    def test_legacy_normalizer_uses_canonical_rules(self):
        self.assertEqual(legacy_normalize_tag(" Deep  Learning "), "deep-learning")
        self.assertEqual(legacy_normalize_tag("AI/ML"), normalize_tag("AI/ML"))

    def test_legacy_adapter_accepts_old_and_current_timestamp_keys(self):
        base = {"id": 1, "title": "A", "body": "B", "tags": []}
        old = note_to_frontend({**base, "created_at": "old"})
        current = note_to_frontend({**base, "createdAt": "current"})

        self.assertEqual(old["createdAt"], "old")
        self.assertEqual(current["createdAt"], "current")


if __name__ == "__main__":
    unittest.main()
