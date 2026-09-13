from __future__ import annotations

from .repository import NoteRepository
from .utils import normalize_query, normalize_tag


class NoteService:
    def __init__(self, repository: NoteRepository):
        self.repository = repository

    def create_note(self, title: str, body: str, tags: list[str]):
        if not title.strip():
            raise ValueError("title is required")
        cleaned = [normalize_tag(tag) for tag in tags if normalize_tag(tag)]
        return self.repository.add(title.strip(), body.strip(), cleaned)

    def list_notes(self):
        return self.repository.list()

    def search(self, query: str):
        q = normalize_query(query)
        if not q:
            return self.list_notes()
        results = []
        for note in self.repository.list():
            haystack = normalize_query(" ".join([note.title, note.body, " ".join(note.tags)]))
            if q in haystack:
                results.append(note)
        return results

    def delete_note(self, note_id: int) -> bool:
        return self.repository.delete(note_id)
