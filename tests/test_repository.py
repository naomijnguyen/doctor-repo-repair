import unittest

from fieldnotes.repository import NoteRepository


class RepositoryTests(unittest.TestCase):
    def test_ids_increment(self):
        repo = NoteRepository()
        a = repo.add("a", "", [])
        b = repo.add("b", "", [])
        self.assertEqual((a.id, b.id), (1, 2))

    def test_list_returns_copy(self):
        repo = NoteRepository()
        repo.add("a", "", [])
        notes = repo.list()
        notes.clear()
        self.assertEqual(len(repo.list()), 1)


if __name__ == "__main__":
    unittest.main()
