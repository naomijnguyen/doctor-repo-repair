import unittest

from fieldnotes.repository import NoteRepository
from fieldnotes.service import NoteService


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = NoteRepository()
        self.service = NoteService(self.repo)

    def test_create_normalizes_tags(self):
        note = self.service.create_note("A", "B", [" Deep Learning ", "AI/ML"])
        self.assertEqual(note.tags, ["deep-learning", "aiml"])

    def test_search_matches_body(self):
        self.service.create_note("A", "Transformers are useful", [])
        self.assertEqual(len(self.service.search("transformers")), 1)

    def test_blank_title_fails(self):
        with self.assertRaises(ValueError):
            self.service.create_note("   ", "B", [])


if __name__ == "__main__":
    unittest.main()
