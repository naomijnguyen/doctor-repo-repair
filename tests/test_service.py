import unittest
from unittest.mock import Mock, patch

from fieldnotes.repository import NoteRepository
from fieldnotes.service import NoteService


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = NoteRepository()
        self.service = NoteService(self.repo)

    def test_create_normalizes_tags(self):
        note = self.service.create_note("A", "B", [" Deep Learning ", "AI/ML"])
        self.assertEqual(note.tags, ["deep-learning", "aiml"])

    def test_create_trims_fields_and_omits_empty_tags(self):
        note = self.service.create_note("  A title  ", "  A body  ", [" ", "Useful Tag"])
        self.assertEqual((note.title, note.body), ("A title", "A body"))
        self.assertEqual(note.tags, ["useful-tag"])

    def test_create_normalizes_each_tag_once(self):
        with patch("fieldnotes.service.normalize_tag", wraps=lambda tag: tag.lower()) as normalize:
            note = self.service.create_note("A", "B", ["One", "Two"])

        self.assertEqual(note.tags, ["one", "two"])
        self.assertEqual(normalize.call_count, 2)

    def test_create_rejects_malformed_fields(self):
        cases = [
            (None, "body", [], "title must be a string"),
            ("title", None, [], "body must be a string"),
            ("title", "body", "tag", "tags must be a list"),
            ("title", "body", [None], "tags must contain strings"),
        ]
        for title, body, tags, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.service.create_note(title, body, tags)

    def test_search_matches_body(self):
        self.service.create_note("A", "Transformers are useful", [])
        self.assertEqual(len(self.service.search("transformers")), 1)

    def test_search_matches_normalized_title_and_tag(self):
        title_match = self.service.create_note("Field   Notes", "", [])
        tag_match = self.service.create_note("Other", "", ["Deep Learning"])

        self.assertEqual(self.service.search("field notes"), [title_match])
        self.assertEqual(self.service.search("deep-learning"), [tag_match])

    def test_blank_search_returns_all_notes(self):
        notes = [
            self.service.create_note("One", "", []),
            self.service.create_note("Two", "", []),
        ]
        self.assertEqual(self.service.search(" \n "), notes)

    def test_delete_delegates_to_repository(self):
        repository = Mock()
        repository.delete.return_value = True
        service = NoteService(repository)

        self.assertTrue(service.delete_note(7))
        repository.delete.assert_called_once_with(7)

    def test_import_validates_then_delegates_once_to_batch_operation(self):
        repository = Mock()
        repository.add_many.return_value = ["first", "second"]
        service = NoteService(repository)
        payload = {
            "notes": [
                {"title": "First", "createdAt": "2026-09-12T20:00:00Z"},
                {"title": "Second", "createdAt": "2026-09-12T21:00:00Z"},
            ]
        }

        self.assertEqual(service.import_notes(payload), ["first", "second"])
        repository.add_many.assert_called_once()
        drafts = repository.add_many.call_args.args[0]
        self.assertEqual([draft.title for draft in drafts], ["First", "Second"])

    def test_invalid_import_never_calls_storage(self):
        repository = Mock()
        service = NoteService(repository)

        with self.assertRaisesRegex(ValueError, "index 1.*createdAt"):
            service.import_notes(
                {
                    "notes": [
                        {"title": "First"},
                        {"title": "Second", "createdAt": "timezone missing"},
                    ]
                }
            )

        repository.add_many.assert_not_called()

    def test_empty_import_does_not_call_storage(self):
        repository = Mock()
        service = NoteService(repository)

        self.assertEqual(service.import_notes({"notes": []}), [])
        repository.add_many.assert_not_called()

    def test_blank_title_fails(self):
        with self.assertRaises(ValueError):
            self.service.create_note("   ", "B", [])


if __name__ == "__main__":
    unittest.main()
