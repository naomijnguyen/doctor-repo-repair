from __future__ import annotations

from typing import Any

from .importer import validate_import_payload
from .repository import NoteRepository
from .utils import normalize_query, normalize_tag


class NoteService:
    def __init__(self, repository: NoteRepository):
        self.repository = repository

    def create_note(self, title: str, body: str, tags: list[str]):
        if not isinstance(title, str):
            raise ValueError("title must be a string")
        if not title.strip():
            raise ValueError("title is required")
        if not isinstance(body, str):
            raise ValueError("body must be a string")
        if not isinstance(tags, list):
            raise ValueError("tags must be a list")

        cleaned = []
        for tag in tags:
            if not isinstance(tag, str):
                raise ValueError("tags must contain strings")
            normalized = normalize_tag("-".join(tag.split()))
            if normalized:
                cleaned.append(normalized)
        return self.repository.add(title.strip(), body.strip(), cleaned)

    def list_notes(self):
        return self.repository.list()

    def import_notes(self, payload: Any):
        drafts = validate_import_payload(payload)
        if not drafts:
            return []
        return self.repository.add_many(drafts)

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
