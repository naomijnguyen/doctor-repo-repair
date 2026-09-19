# Technical Notes

This document is the implementation readthrough for the current Field Notes
milestone. It explains what the code does, where each rule lives, and which
failure guarantees have direct test evidence.

## Runtime and dependencies

Field Notes targets Python 3.11 or newer and uses only the standard library at
runtime:

- `http.server` for the local HTTP process;
- `sqlite3` for durable storage;
- `urllib` for the import command's HTTP client;
- `dataclasses` for domain values; and
- `threading.Lock` for repository-level process concurrency.

Node.js is optional and is used by `scripts/check.sh` to syntax-check frontend
JavaScript and run two deterministic request-state tests. The separate Chrome
acceptance runner uses Node's built-in DevTools-protocol support.

Package and source versions are both `0.4.0`.

## Domain values

### `Note`

`fieldnotes.models.Note` represents a stored note:

```text
id          local positive integer
title       required text
body        optional text stored as a string
tags        mutable list returned as a defensive copy
created_at  timezone-aware UTC ISO 8601 string
```

`Note.create()` assigns the current UTC timestamp for ordinary creation.
`Note.to_dict()` translates the internal `created_at` name to public
`createdAt` and copies the tag list.

### `NoteDraft`

`NoteDraft` is immutable and has no ID. It represents a fully validated imported
record waiting for the selected repository to assign a local identity. Its tags
are a tuple so callers cannot mutate the validated batch while storage is
publishing it.

Keeping drafts storage-neutral avoids assigning IDs or relying on SQLite inside
the validation layer.

## Normalization and service rules

`fieldnotes.utils.normalize_tag()` is the canonical tag function used by normal
creation and import. The service trims title and body text, turns internal tag
whitespace into hyphenated input, discards empty normalized tags, deduplicates
equivalent normalized values in first-seen order, and delegates the clean values
to its repository. Import applies the same deduplication rule.

Search normalizes both the query and a combined title/body/tag haystack. A blank
query returns the full repository list.

`NoteService` receives its repository in the constructor. It does not construct
storage or read configuration, which keeps business rules reusable across the
SQLite runtime and in-memory tests.

## Repository contract

The application currently uses a structural contract rather than an abstract
base class or protocol:

```python
list() -> list[Note]
add(title, body, tags) -> Note
add_many(notes: list[NoteDraft]) -> list[Note]
delete(note_id) -> bool
clear() -> None
```

Both adapters:

- assign local sequential IDs;
- preserve input order for `add_many()`;
- copy tags at the repository boundary;
- return an empty result for an empty batch without consuming an ID;
- keep one lock around a complete operation; and
- reset IDs to 1 after `clear()`.

Shared conformance tests protect these behaviors without forcing the service to
depend on one concrete adapter type.

## In-memory adapter

`fieldnotes.repository.NoteRepository` stores notes in a list and tracks the
next ID as an integer. It is useful for focused tests because it is fast and has
no filesystem lifecycle.

It is not selected by runtime composition and is not a fallback when SQLite
fails. That distinction is deliberate: a durable write must not appear to
succeed only because the application quietly switched to temporary memory.

## SQLite adapter

`SQLiteNoteRepository` opens one connection with:

```python
sqlite3.connect(
    database_path,
    isolation_level=None,
    check_same_thread=False,
)
```

Autocommit mode is enabled so each mutation can control its transaction
explicitly. `check_same_thread=False` permits the threaded HTTP server to share
the repository connection; the repository's `Lock` serializes access.

### Mutation pattern

Create, batch create, delete, and clear follow the same shape:

```text
acquire repository lock
  -> BEGIN IMMEDIATE
  -> perform mutation
  -> read back or inspect the result
  -> COMMIT

on any exception
  -> ROLLBACK when a transaction is active
  -> re-raise the original failure
```

`add_many()` does not loop through public `add()`. It owns one transaction for
the whole batch and reads each new row back before commit. A missing readback is
treated as a database failure rather than returning a partial-looking success.

`clear()` deletes both note rows and the table's `sqlite_sequence` entry in the
same transaction, preserving parity with the memory adapter's ID reset.

### Schema initialization

`SCHEMA_VERSION` is 1. Initialization reads `PRAGMA user_version` and the set of
non-SQLite user tables before opening its schema transaction.

For existing stores, `_validate_existing_notes()` checks:

- exact required columns and types;
- the primary-key shape;
- `AUTOINCREMENT` in the table SQL;
- readable IDs and text fields;
- a JSON list of string tags; and
- a timezone-aware UTC timestamp.

Only a compatible version-zero `notes` database is adopted. Other unversioned,
damaged, unreadable, or unsupported stores fail without being rewritten.

## Import contract

The import path has two separate safety stages.

### Complete validation

`validate_import_payload()` requires a JSON object containing a `notes` list. It
checks every item and returns `NoteDraft` values in source order. Validation:

- requires a nonblank string title;
- accepts an optional string body;
- accepts an optional list of string tags;
- normalizes tags;
- ignores source IDs;
- preserves valid timezone-aware `createdAt` instants in canonical UTC; and
- assigns current UTC when `createdAt` is absent.

Import validation raises `ImportValidationError`, a dedicated `ValueError`
subclass. The API maps that known client failure to `400 invalid_request`.
Repository `ValueError` exceptions are intentionally not caught there, so an
unexpected storage failure reaches the server's generic `500` boundary.

Create and import record objects currently ignore unknown fields. Source `id` is
one intentional example: it may travel through a portable document, but the
destination repository assigns local identity. Unknown fields are not persisted.

### Atomic publication

`NoteService.import_notes()` validates first and calls `repository.add_many()`
once. SQLite then publishes all drafts in one transaction. Validation atomicity
and transaction atomicity solve different failure classes:

- complete validation prevents known bad input from starting storage; and
- rollback removes attempted rows when storage fails after insertion begins.

The current contract does not include an idempotency key. If SQLite commits but
the HTTP response is lost, a blind retry may duplicate the batch. That is an
ambiguous-retry problem, not a failure of transaction rollback.

## API adapter

`fieldnotes.api.handle_request()` is transport translation without a live socket.
It parses paths, methods, query parameters, and request JSON; calls the injected
service; and returns a `(status, headers, body)` tuple.

Implemented routes:

```text
GET    /api/notes
POST   /api/notes
DELETE /api/notes/:id
GET    /api/search?q=...
POST   /api/import
GET    /api/export
```

Public errors use a nested shape:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "human-readable detail"
  }
}
```

Known routes with wrong methods return `405`. The server dispatches `PUT` and
`PATCH` through the adapter so unsupported API methods use JSON rather than the
base handler's HTML `501` page.

## HTTP server and lifecycle

`fieldnotes.server.Handler`:

- serves browser assets for non-API GET requests from the repository's `web/`
  directory;
- parses and bounds `Content-Length` before reading request bodies;
- limits bodies to 1,000,000 bytes;
- delegates supported methods to `handle_request()`;
- rejects mismatched or opaque browser origins before mutation;
- requires `application/json` for JSON POST routes;
- converts unexpected exceptions to a generic JSON `500`;
- emits `Content-Length`; and
- supplies local CORS headers only for the actual same origin.

`handler_for(service)` creates a handler subclass bound to the composed service.
This avoids a module-global repository and makes the selected state owner
explicit.

The normal launch command serves the UI and API from one loopback origin.
`web/api.js` therefore uses relative API paths and follows a configured server
port automatically.

`build_server()` parses the selected port before constructing storage. If socket
binding fails after repository creation, it closes the repository. `main()` owns
normal server and repository shutdown.

The trust boundary is deliberately local. Requests without `Origin` remain valid
for CLI clients. Browser requests carrying `Origin` must match the current
loopback server's host and port; foreign origins and `Origin: null` are rejected
before state changes.

## Import command

`tools/import_sample.py` uses `ApiImportClient` rather than opening SQLite. It:

- reads and parses one JSON file;
- sends exactly one request to `/api/import`;
- preserves the original parsed fields for server-side policy;
- reports structured API detail when available;
- names the selected API origin on connection failure;
- performs no automatic retry; and
- validates the success-response shape before printing imported notes.

The command defaults to the configured API port and supports an explicit
`--api-url` for tests or another local server.

## Export command and atomic publication

`tools/export_notes.py` reads `GET /api/export` from the running application.
`fieldnotes.exporter.write_export()` serializes readable UTF-8 JSON into a
temporary sibling, flushes and fsyncs it, then publishes once:

- default mode uses an atomic hard link and refuses an existing destination;
- `--replace` uses `os.replace()` only after the new file is complete; and
- any exception removes the temporary sibling while preserving prior bytes.

The black-box recovery test uses a populated source database, the real export
command, a distinct empty destination database, the real import command, and a
new destination server process. It compares ordered public fields and timestamps;
IDs are assigned locally and are not portable identity.

## Browser implementation

`web/app.js` builds note elements with DOM methods and assigns user content with
`textContent`; note data is not interpolated into active HTML. It renders empty,
loading, saving, deleting, searching, success, and error states.

`web/api.js` centralizes same-origin requests and converts non-success responses
into JavaScript errors.

`web/request-state.js` supplies the generation and submitted-draft primitives.
Every collection read receives a generation, and only the newest may render or
report an error. A completed save clears only fields that still equal their
submitted values, preserving newer edits. Mutation success is reported before a
follow-up refresh, so refresh failure cannot mislabel a committed write.

## Verification map

| Boundary | Representative proof |
| --- | --- |
| Domain and API | model, service, importer, and route unit tests |
| Repository parity | shared conformance suite against memory and SQLite |
| Durable adapter | close/reopen create and delete tests |
| Schema safety | compatible adoption and non-mutating rejection cases |
| Atomic storage | deterministic second-row trigger failure and rollback |
| Runtime composition | configured path, shared state owner, bind cleanup |
| Public persistence | real HTTP create/delete across server processes |
| Public import | real CLI, API retrieval, restart, rollback, and retry |
| Public export/recovery | real export and import commands, two databases, restart |
| Atomic filesystem publication | overwrite race and forced publish failure preserve prior bytes |
| HTTP trust boundary | real socket origin, media-type, method, and body-limit checks |
| Browser ordering | generation/draft unit tests plus delayed real-Chrome workflows |
| Concurrency | ordinary add raced against a contiguous 40-note batch |

Run all current checks with:

```bash
./scripts/check.sh
```

The current gate passes 110 Python tests and 2 JavaScript state tests. Run the
separate real-browser flow with `node scripts/browser_acceptance.mjs`.

## Current design decisions

- SQLite is the runtime state owner; memory is a test adapter.
- The service receives its repository through composition.
- Import reaches the application over HTTP rather than opening a second writer.
- Export also reaches the application over HTTP and publishes locally only after
  receiving a complete valid response.
- Source IDs are ignored during import; the destination assigns local IDs.
- Valid source timestamps preserve their instant; missing timestamps are assigned.
- An empty import is a successful no-op and does not consume an ID.
- Transactions provide rollback, not ambiguous-retry idempotency.
- Unknown or incompatible schemas fail visibly instead of being guessed at.

The remaining implementation assignments and acceptance gates are in
[`../agents/NEXT_WAVE.md`](../agents/NEXT_WAVE.md).
