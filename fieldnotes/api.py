import json
import re
from urllib.parse import parse_qs, urlparse

from .importer import ImportValidationError
from .service import NoteService


def _json(status: int, payload: dict):
    return status, {"Content-Type": "application/json"}, json.dumps(payload).encode()


def _error(status: int, code: str, message: str):
    return _json(status, {"error": {"code": code, "message": message}})


def _note_dict(note) -> dict:
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "tags": note.tags,
        "createdAt": note.created_at,
    }


def _create_payload(body: bytes) -> dict:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("request body must be valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    title = payload.get("title", "")
    note_body = payload.get("body", "")
    tags = payload.get("tags", [])
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    if not isinstance(note_body, str):
        raise ValueError("body must be a string")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("tags must be an array of strings")
    return {"title": title, "body": note_body, "tags": tags}


def _json_object(body: bytes) -> dict:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def handle_request(method: str, path: str, body: bytes, service: NoteService):
    parsed = urlparse(path)

    if method == "GET" and parsed.path == "/api/notes":
        return _json(200, {"notes": [_note_dict(n) for n in service.list_notes()]})

    if method == "GET" and parsed.path == "/api/search":
        query = parse_qs(parsed.query).get("q", [""])[0]
        return _json(200, {"notes": [_note_dict(n) for n in service.search(query)]})

    if method == "POST" and parsed.path == "/api/notes":
        try:
            payload = _create_payload(body)
            note = service.create_note(
                payload["title"],
                payload["body"],
                payload["tags"],
            )
            return _json(201, _note_dict(note))
        except ValueError as exc:
            return _error(400, "invalid_request", str(exc))

    if method == "POST" and parsed.path == "/api/import":
        try:
            payload = _json_object(body)
        except ValueError as exc:
            return _error(400, "invalid_request", str(exc))
        try:
            notes = service.import_notes(payload)
        except ImportValidationError as exc:
            return _error(400, "invalid_request", str(exc))
        status = 201 if notes else 200
        return _json(
            status,
            {"imported": len(notes), "notes": [_note_dict(note) for note in notes]},
        )

    delete_match = re.fullmatch(r"/api/notes/([^/]+)", parsed.path)
    if method == "DELETE" and delete_match:
        raw_note_id = delete_match.group(1)
        if not raw_note_id.isascii() or not raw_note_id.isdigit() or int(raw_note_id) < 1:
            return _error(400, "invalid_note_id", "note id must be a positive integer")
        note_id = int(raw_note_id)
        if service.delete_note(note_id):
            return 204, {}, b""
        return _error(404, "note_not_found", "note not found")

    known_path = parsed.path in {"/api/notes", "/api/search", "/api/import"} or delete_match
    if known_path:
        return _error(405, "method_not_allowed", "method not allowed")

    return _error(404, "not_found", "not found")
