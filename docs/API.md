# API

Base URL: `http://127.0.0.1:8000`

## GET /api/notes
Returns `{ "notes": [...] }`.

## POST /api/notes
Body:
```json
{"title":"...","body":"...","tags":["a","b"]}
```

## DELETE /api/notes/:id
Returns 204 when deletion succeeds.

## GET /api/search?q=term
Returns matching notes.

Errors use `{ "message": "..." }`.
