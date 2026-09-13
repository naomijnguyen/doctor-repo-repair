# Architecture

Field Notes has an application boundary and two storage adapters:

1. `fieldnotes/api.py` — HTTP request translation only.
2. `fieldnotes/service.py` — business rules.
3. `fieldnotes/repository.py` — the in-memory test adapter and structural repository contract.
4. `fieldnotes/sqlite_repository.py` — transactional durable storage.
5. `fieldnotes/composition.py` — runtime construction and dependency injection.

The browser calls the API through `web/api.js`; `web/app.js` owns rendering and interaction state.

## API conventions

Public JSON uses camelCase timestamps in `createdAt`; the Python model keeps its internal `created_at` attribute.

API-created and imported tags share the normalization rules in `fieldnotes/utils.py`.

`POST /api/import` parses one complete payload, validates it into storage-neutral
`NoteDraft` values, and calls repository `add_many()` once. SQLite holds one lock
and one transaction across the complete batch.

## Runtime

The API server binds to localhost on port 8000 unless overridden by
`FIELDNOTES_PORT`. `FIELDNOTES_DATA` selects the SQLite database, defaulting to
`./data/fieldnotes.sqlite3`. `build_server()` parses the port before opening
storage, constructs one repository through the composition root, injects it into
`NoteService`, and closes it during shutdown.

The browser UI is static and can be served on a separate local port. It still
targets API port 8000 directly; same-origin serving is planned rather than
claimed.

CORS accepts direct-file access and local HTTP origins with an explicit port.
Other origins are rejected during preflight, but mutation enforcement remains a
known trust-boundary follow-up.

## Reliability

The running repository is SQLite. Committed create, delete, and batch import
operations survive process restart. The in-memory repository remains available
for fast conformance and service tests.

Schema version 1 is recorded with SQLite `user_version`. Startup distinguishes a
new database from compatible, incompatible, unrelated, damaged, and unreadable
existing stores. Unsafe states fail visibly without a memory fallback.

HTTP errors use a nested `error` object with a stable code and human-readable message. The browser client also tolerates the former flat `message` shape during the transition.
