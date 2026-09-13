import json
import tempfile
import unittest
from pathlib import Path

from fieldnotes.importer import import_notes
from fieldnotes.repository import NoteRepository


class ImportTests(unittest.TestCase):
    def test_imports_notes(self):
        repo = NoteRepository()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(json.dumps({"notes": [{"title": "A", "tags": ["Deep Learning"]}]}))
            self.assertEqual(import_notes(str(path), repo), 1)
            self.assertEqual(repo.list()[0].tags, ["deep_learning"])


if __name__ == "__main__":
    unittest.main()
