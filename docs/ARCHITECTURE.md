# Architecture

Field Notes has three layers:

1. `fieldnotes/api.py` — HTTP request translation only.
2. `fieldnotes/service.py` — business rules.
3. `fieldnotes/repository.py` — SQLite persistence.

The browser calls the API through `web/api.js`. UI modules must not call `fetch` directly.

## API conventions

All JSON fields use camelCase. Timestamps are ISO-8601 strings in the `createdAt` field.
Tags are normalized in the service layer only.

## Runtime

The server binds to localhost on port 8080 unless overridden by `FIELDNOTES_PORT`.
CORS is restricted to the local development origin.

## Reliability

Writes are persisted before success is returned. Repository operations are serialized.
All HTTP errors use `{ "error": { "code": "...", "message": "..." } }`.
