# Field Notes: As-Built Architecture

Review draft, inspected 2026-09-12 Pacific / 2026-09-13 UTC.

This document describes the working implementation, not a proposed replacement. The repository is being edited concurrently. During inspection its branch changed from `main` to `codex/field-notes-triage`; that change was not made by this review. The baseline inspected during the field scan was `1884f4d785f2c3042792d45854e06c0837599408`, but uncommitted code is part of this description. A commit hash alone does not reproduce this state.

## The Short Version

Field Notes is a small research-note application. A browser interface talks to a local Python HTTP server. The server translates requests into service calls, and the service stores notes in a shared, lock-protected Python repository.

The repository currently holds notes in memory. Successful API writes mean the note exists in that server process, not that it has been saved to disk. The importer can load a JSON file into a repository, but its command-line entry point creates a separate repository from the running server.

There are no model calls, agents, background jobs, cloud services, or database connections in the inspected application path.

## Runtime Pieces

| Piece | Current responsibility | Source |
| --- | --- | --- |
| Browser document and styles | Form, note collection, accessible labels/status regions, presentation | [index.html](../web/index.html), [styles.css](../web/styles.css) |
| Browser interaction code | Form submission, rendering, search, delete, status messages | [app.js](../web/app.js) |
| Browser API client | Central fetch wrapper, JSON parsing, HTTP failure messages | [api.js](../web/api.js) |
| HTTP host | Threaded localhost server, body-size boundary, CORS responses, request dispatch | [server.py](../fieldnotes/server.py) |
| API adapter | Routes, payload shape validation, status codes, public serialization | [api.py](../fieldnotes/api.py) |
| Service | Note validation, trimming, tag normalization, substring search, repository delegation | [service.py](../fieldnotes/service.py) |
| Repository | In-memory records, sequential IDs, per-operation locking, defensive copies | [repository.py](../fieldnotes/repository.py) |
| Note model | Data fields, UTC creation time, serialization helper | [models.py](../fieldnotes/models.py) |
| Text helpers | Canonical tag/query normalization | [utils.py](../fieldnotes/utils.py) |
| File importer | Validate a complete JSON payload, normalize fields, add each note | [importer.py](../fieldnotes/importer.py) |
| Sample import tool | Create a separate repository, import a file, print the results | [import_sample.py](../tools/import_sample.py) |

The main dependency path is browser interactions -> browser API client -> HTTP handler -> API adapter -> service -> repository -> note model. Service and importer both use the text helpers. The importer calls the repository directly rather than passing through the service.

## Startup and Process Boundaries

The documented workflow uses two commands:

```sh
python3 -m fieldnotes.server
python3 -m http.server 8080 --directory web
```

The first starts the API on `127.0.0.1:8000` by default. Importing the server module constructs one repository and one service, shared by its HTTP handler threads. It does not read existing note data at startup and does not serve the browser assets.

The second is a separate static-file server. The browser loads JavaScript from it, then makes requests to the API on port 8000. These are different origins. The documented static-server command does not explicitly bind to loopback; the API command does. Treat those exposure boundaries separately.

`FIELDNOTES_PORT` changes the API listener. The browser client currently has a fixed API base of `http://127.0.0.1:8000`, so changing the listener alone does not reconfigure the browser.

`FIELDNOTES_DATA` is the canonical data-path setting, with `FIELD_NOTES_DATA` as a legacy fallback and `./data/fieldnotes.json` as the default. The server does not currently call this setting to open storage.

## Where State Lives

| State | Owner | Lifetime and guarantees |
| --- | --- | --- |
| Form values, status, search counter, rendered notes | Browser DOM / JavaScript | Current page; not an authoritative database |
| Notes and next ID | One NoteRepository instance | Current process; empty after a new process starts |
| Repository lock | One NoteRepository instance | Serializes individual operations in that instance; not cross-process coordination |
| Import input | JSON file chosen by the caller | Readable input; not automatically connected to server storage |
| Imported sample results | Tool's separate repository | Lost when the tool exits, apart from printed output |

The repository copies records and tag lists when returning results, preventing callers from mutating stored data through those returned objects. `list`, `add`, `delete`, and `clear` acquire the same lock. This protects individual operations, not an entire sequence of multiple operations or an import transaction.

## A Note's Shape

Public notes contain `id`, `title`, `body`, `tags`, and `createdAt`. Python stores the timestamp as `created_at`; it is assigned using the current UTC time when a Note is created.

- IDs are integers assigned sequentially within one repository. A new repository starts at 1; `clear` also resets the counter.
- Creation requires a nonblank string title. The service trims title and body at both ends.
- Tags must be strings. Normalization lowercases, trims, converts whitespace to hyphens, and removes characters outside ASCII letters, digits, underscore, and hyphen. Empty normalized tags are dropped.
- Duplicate normalized tags are currently retained, not deduplicated.
- The repository returns insertion order: currently oldest-created-in-this-instance first, not the newest-first order described as intended.
- API serialization is implemented in `_note_dict`; the model also has `to_dict`. These are currently equivalent representations, but separate maintenance points.

## Request Workflows

### Create

1. The browser captures the current form and disables Submit.
2. The API client sends JSON to `POST /api/notes`.
3. The HTTP handler checks declared body length and rejects bodies over 1,000,000 bytes.
4. The API adapter decodes a JSON object and checks field types. Unknown fields are ignored.
5. The service validates the title, trims fields, and normalizes tags.
6. The repository locks, assigns an ID/timestamp, appends the record, and returns a copy.
7. The API sends 201 with the note. The browser resets the form, refreshes the collection, and then announces success.

The write is acknowledged before any durable storage because none exists. The form remains editable during the request, so a successful response can reset edits made after submission. A failed refresh after a successful create is currently handled together with create failure. See FN-S3-01 and FN-S3-03 in [TRIAGE.md](../TRIAGE.md).

### List and Search

`GET /api/notes` returns `{ "notes": [...] }`. `GET /api/search?q=...` returns the same envelope.

Search lowercases and collapses whitespace in the query and in a joined title/body/tag string, then performs substring matching over a repository snapshot. Empty queries return all notes. This is an in-memory text scan, not indexed, fuzzy, or semantic search; query normalization does not apply the tag punctuation/hyphen conversion.

Input-triggered searches use a version counter to reject older search responses. Initial loading and post-mutation refreshes do not participate in that same ordering mechanism, so they can still overwrite newer results (FN-S3-02).

### Delete

`DELETE /api/notes/:id` validates a positive ASCII integer ID, delegates through the service, and deletes under the repository lock. Success returns 204; a missing note returns 404; an invalid ID returns 400.

The browser disables the selected Delete button, waits for deletion, and reloads the collection. If that reload fails, the confirmed deletion is not separately reconciled in the UI (FN-S3-03). Direct Python service calls do not currently enforce the HTTP layer's ID validation (FN-S1-03).

### Import

The importer reads UTF-8 JSON with a top-level `notes` array. It validates every record before adding any and uses the same tag normalizer as the service. It nevertheless duplicates some service validation and calls `repository.add` directly.

Each added row receives a new local ID and a fresh creation timestamp. Supplied IDs and timestamps are not preserved by this path. Validation failures avoid partial mutation, but failures during the add loop have no rollback or retry deduplication (FN-S2-02).

The sample tool's output is a demonstration of importing and printing, not an export feature or an import into the running API. There is no import/export HTTP route in the current implementation.

## HTTP and Safety Boundary

The API listener binds to loopback. There is no authentication layer. CORS allows local HTTP origins with an explicit port, plus `null`; allowed-origin responses receive CORS headers. OPTIONS rejects origins outside that policy.

That is not a complete mutation authorization boundary: ordinary request handling does not enforce the origin policy or JSON media type before creating a note. Null also does not uniquely identify a trusted local file. See FN-S4-01 and FN-S4-02 for scoped evidence; no live browser exploit was demonstrated.

The browser renders note values as text rather than interpolating them into HTML. Expected API errors use a nested `error` object. Unexpected handler exceptions are logged and returned as generic JSON 500 responses. Deep JSON nesting can currently reach that unexpected-error path.

The API adapter implements JSON 405 responses, but the HTTP host dispatches only GET/POST/DELETE to it. Other verbs such as PUT can receive the standard handler's 501 HTML response instead. This is a real adapter/transport distinction, not a second public API contract.

## Compatibility and Support Code

`helpers/text.py` reexports the canonical tag normalizer for older imports. `legacy_adapter.py` translates mappings with either timestamp key into the frontend shape. Neither is the primary server serialization path.

The application path uses Python's standard library. Frontend JavaScript uses native modules and fetch, with no frontend build step. `pyproject.toml` declares Python >=3.11; CI selects Python 3.11 and runs `scripts/check.sh`.

That check compiles Python, checks frontend syntax if Node is available, and runs unittest discovery. The closing field scan passed 33 tests locally on Python 3.9.6, including repository concurrency coverage. This is not verification on the declared runtime, remote CI, or browser interactions. See the triage log for the dated evidence rather than treating that count as permanent.

## Current Implementation vs Product Intent

[README_INTENT.md](../README_INTENT.md) is a product-direction document, not proof of implemented behavior.

| Concern | Implemented now | Intent / decision still to implement |
| --- | --- | --- |
| Storage | Lock-protected process memory | Durable, transactional SQLite |
| Startup | Separate API and static-server commands | One documented startup path |
| Ordering | Repository insertion order | Newest first |
| Tags | Shared normalizer, duplicates retained | Unique normalized tags |
| Import | Separate tool repository, fresh timestamps | Same durable store and explicit timestamp policy |
| Export | No dedicated export implementation | Portable, atomic JSON export |
| Browser ordering | Search-only sequence guard | Consistent ordering across searches and refreshes |
| Quality gates | Python unit tests and syntax checks | Supported-runtime, HTTP, browser, persistence, and round-trip coverage |

## Review Discussion

The existing separation between API, service, and repository is useful: it gives persistence work a clear home without requiring a new frontend framework or cloud infrastructure. Keep that structure unless implementation reveals a concrete reason to change it.

Questions to settle before parallel implementation:

1. Does the SQLite direction in README_INTENT become the approved storage contract, including failure and timestamp behavior?
2. Should the Python server serve the UI on the same origin, eliminating the fixed cross-origin client address for normal use?
3. How should API and import share validation while preserving transactional batch behavior?
4. Who owns the shared API/model contract while other agents implement UI and repository changes?

These are review questions, not decisions made by this document. No application code, configuration, or existing documentation was changed to make this architecture description true.
