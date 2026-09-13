import json
from pathlib import Path

from .helpers.text import normalize_tag
from .repository import NoteRepository


def import_notes(path: str, repository: NoteRepository) -> int:
    payload = json.loads(Path(path).read_text())
    count = 0
    for item in payload.get("notes", []):
        tags = [normalize_tag(t) for t in item.get("tags", [])]
        repository.add(item["title"], item.get("body", ""), tags)
        count += 1
    return count
