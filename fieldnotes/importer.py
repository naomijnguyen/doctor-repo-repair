from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import NoteDraft
from .repository import NoteRepository
from .utils import normalize_tag


class ImportValidationError(ValueError):
    """The import payload is invalid before repository mutation begins."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_created_at(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ImportValidationError(
            f"{label} createdAt must be a timezone-aware ISO 8601 string"
        )

    candidate = value.strip()
    if candidate.endswith(("Z", "z")):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ImportValidationError(
            f"{label} createdAt must be a timezone-aware ISO 8601 string"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ImportValidationError(f"{label} createdAt must include a timezone offset")
    return parsed.astimezone(timezone.utc).isoformat()


def validate_import_payload(payload: Any) -> list[NoteDraft]:
    if not isinstance(payload, dict):
        raise ImportValidationError("import file must contain a JSON object")

    notes = payload.get("notes")
    if not isinstance(notes, list):
        raise ImportValidationError("import file must contain a 'notes' list")

    validated = []
    for index, item in enumerate(notes):
        label = f"note at index {index}"
        if not isinstance(item, dict):
            raise ImportValidationError(f"{label} must be an object")

        title = item.get("title")
        body = item.get("body", "")
        tags = item.get("tags", [])
        if not isinstance(title, str) or not title.strip():
            raise ImportValidationError(f"{label} requires a non-empty title")
        if not isinstance(body, str):
            raise ImportValidationError(f"{label} body must be a string")
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ImportValidationError(f"{label} tags must be a list of strings")

        cleaned_tags = []
        seen_tags = set()
        for tag in tags:
            cleaned = normalize_tag(tag)
            if cleaned and cleaned not in seen_tags:
                cleaned_tags.append(cleaned)
                seen_tags.add(cleaned)
        if "createdAt" in item:
            created_at = _canonical_created_at(item["createdAt"], label)
        else:
            created_at = _utc_now().isoformat()
        validated.append(
            NoteDraft(
                title=title.strip(),
                body=body.strip(),
                tags=tuple(cleaned_tags),
                created_at=created_at,
            )
        )

    return validated


def _validated_notes(payload: Any) -> list[NoteDraft]:
    """Compatibility name for callers that used the former private helper."""
    return validate_import_payload(payload)


def import_notes(path: str | Path, repository: NoteRepository) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    notes = validate_import_payload(payload)
    if not notes:
        return 0
    return len(repository.add_many(notes))
