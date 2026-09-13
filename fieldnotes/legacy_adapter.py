"""Old response adapter retained during the UI migration."""

from collections.abc import Mapping
from typing import Any


def note_to_frontend(note: Mapping[str, Any]) -> dict[str, Any]:
    """Translate a legacy snake_case note mapping to the frontend contract."""
    return {
        "id": note["id"],
        "title": note["title"],
        "body": note["body"],
        "tags": note["tags"],
        "createdAt": note.get("createdAt", note.get("created_at")),
    }
