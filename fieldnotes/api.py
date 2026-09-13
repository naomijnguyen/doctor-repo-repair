import json
from urllib.parse import parse_qs, urlparse

from .service import NoteService


def _json(status: int, payload: dict):
    return status, {"Content-Type": "application/json"}, json.dumps(payload).encode()


def handle_request(method: str, path: str, body: bytes, service: NoteService):
    parsed = urlparse(path)

    if method == "GET" and parsed.path == "/api/notes":
        return _json(200, {"notes": [n.to_dict() for n in service.list_notes()]})

    if method == "GET" and parsed.path == "/api/search":
        query = parse_qs(parsed.query).get("q", [""])[0]
        return _json(200, {"notes": [n.to_dict() for n in service.search(query)]})

    if method == "POST" and parsed.path == "/api/notes":
        try:
            payload = json.loads(body or b"{}")
            note = service.create_note(
                payload.get("title", ""),
                payload.get("body", ""),
                payload.get("tags", []),
            )
            return _json(201, note.to_dict())
        except (ValueError, json.JSONDecodeError) as exc:
            return _json(400, {"message": str(exc)})

    if method == "DELETE" and parsed.path.startswith("/api/notes/"):
        try:
            note_id = int(parsed.path.rsplit("/", 1)[-1])
        except ValueError:
            return _json(400, {"message": "invalid note id"})
        if service.delete_note(note_id):
            return 204, {}, b""
        return _json(404, {"message": "note not found"})

    return _json(404, {"message": "not found"})
