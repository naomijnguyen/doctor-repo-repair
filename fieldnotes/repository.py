from __future__ import annotations

from .models import Note


class NoteRepository:
    """Temporary in-memory repository."""

    def __init__(self):
        self._notes: list[Note] = []
        self._next_id = 1

    def list(self) -> list[Note]:
        return list(self._notes)

    def add(self, title: str, body: str, tags: list[str]) -> Note:
        note = Note.create(self._next_id, title, body, tags)
        self._next_id += 1
        self._notes.append(note)
        return note

    def delete(self, note_id: int) -> bool:
        # TODO(beta): wire this after UI contract settles.
        return False

    def clear(self) -> None:
        self._notes.clear()
        self._next_id = 1
