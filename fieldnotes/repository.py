from __future__ import annotations

from threading import Lock

from .models import Note, NoteDraft


class NoteRepository:
    """Temporary in-memory repository."""

    def __init__(self) -> None:
        self._notes: list[Note] = []
        self._next_id = 1
        self._lock = Lock()

    def list(self) -> list[Note]:
        with self._lock:
            return [self._copy(note) for note in self._notes]

    def add(self, title: str, body: str, tags: list[str]) -> Note:
        with self._lock:
            note = Note.create(self._next_id, title, body, tags)
            self._next_id += 1
            self._notes.append(note)
            return self._copy(note)

    def add_many(self, notes: list[NoteDraft]) -> list[Note]:
        with self._lock:
            staged = [
                Note(
                    id=self._next_id + index,
                    title=draft.title,
                    body=draft.body,
                    tags=list(draft.tags),
                    created_at=draft.created_at,
                )
                for index, draft in enumerate(notes)
            ]
            self._notes.extend(staged)
            self._next_id += len(staged)
            return [self._copy(note) for note in staged]

    def delete(self, note_id: int) -> bool:
        with self._lock:
            for index, note in enumerate(self._notes):
                if note.id == note_id:
                    del self._notes[index]
                    return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._notes.clear()
            self._next_id = 1

    @staticmethod
    def _copy(note: Note) -> Note:
        return Note(
            id=note.id,
            title=note.title,
            body=note.body,
            tags=list(note.tags),
            created_at=note.created_at,
        )
