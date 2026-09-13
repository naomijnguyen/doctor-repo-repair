from fieldnotes.importer import import_notes
from fieldnotes.repository import NoteRepository

repo = NoteRepository()
count = import_notes("data/sample.json", repo)
print(f"Imported {count} notes")
for note in repo.list():
    print(note.to_dict())
