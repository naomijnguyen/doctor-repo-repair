from __future__ import annotations

from pathlib import Path

from .config import get_data_file
from .service import NoteService
from .sqlite_repository import SQLiteNoteRepository


def create_repository(
    database_path: str | Path | None = None,
) -> SQLiteNoteRepository:
    """Construct the configured durable repository for an application runtime."""
    selected_path = get_data_file() if database_path is None else database_path
    return SQLiteNoteRepository(selected_path)


def create_service(
    database_path: str | Path | None = None,
) -> tuple[NoteService, SQLiteNoteRepository]:
    """Compose the service and return its repository for lifecycle ownership."""
    repository = create_repository(database_path)
    return NoteService(repository), repository
