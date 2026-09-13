import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from fieldnotes.config import DEFAULT_DATA_FILE, get_data_file
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

    def test_add_copies_tags(self):
        repo = NoteRepository()
        tags = ["field-work"]
        note = repo.add("a", "", tags)

        tags.append("changed-by-caller")
        note.tags.append("also-changed-by-caller")

        self.assertEqual(repo.list()[0].tags, ["field-work"])

    def test_list_copies_note_tags(self):
        repo = NoteRepository()
        repo.add("a", "", ["field-work"])

        repo.list()[0].tags.append("changed-by-caller")

        self.assertEqual(repo.list()[0].tags, ["field-work"])

    def test_delete_existing_note(self):
        repo = NoteRepository()
        first = repo.add("a", "", [])
        second = repo.add("b", "", [])

        self.assertTrue(repo.delete(first.id))
        self.assertEqual([note.id for note in repo.list()], [second.id])
        self.assertFalse(repo.delete(first.id))

    def test_concurrent_adds_assign_unique_sequential_ids(self):
        repo = NoteRepository()
        worker_count = 8
        notes_per_worker = 100
        start = Barrier(worker_count)

        def add_notes(worker: int) -> None:
            start.wait()
            for number in range(notes_per_worker):
                repo.add(f"worker-{worker}-{number}", "", [])

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            list(executor.map(add_notes, range(worker_count)))

        ids = sorted(note.id for note in repo.list())
        self.assertEqual(ids, list(range(1, worker_count * notes_per_worker + 1)))

    def test_note_serializes_with_api_timestamp_name(self):
        note = NoteRepository().add("a", "", ["field-work"])

        self.assertEqual(
            note.to_dict(),
            {
                "id": 1,
                "title": "a",
                "body": "",
                "tags": ["field-work"],
                "createdAt": note.created_at,
            },
        )

    def test_data_file_prefers_canonical_environment_name(self):
        with patch.dict(
            os.environ,
            {"FIELDNOTES_DATA": "/new.json", "FIELD_NOTES_DATA": "/old.json"},
            clear=True,
        ):
            self.assertEqual(get_data_file(), "/new.json")

    def test_data_file_keeps_legacy_environment_name_compatible(self):
        with patch.dict(os.environ, {"FIELD_NOTES_DATA": "/old.json"}, clear=True):
            self.assertEqual(get_data_file(), "/old.json")

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_data_file(), DEFAULT_DATA_FILE)


if __name__ == "__main__":
    unittest.main()
