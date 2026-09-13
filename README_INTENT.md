# Field Notes

Field Notes is a small, local-first workspace for capturing, organizing, and retrieving research notes.

It is designed for the moment when an observation is worth keeping but does not yet belong in a polished document: a result from an experiment, a comparison to revisit, a question raised while reading, or a short connection between ideas. The application should make those notes quick to record, easy to find, and safe to keep on the user's own machine.

Field Notes deliberately favors a small, dependable workflow over a large knowledge-management feature set.

## What Field Notes is for

A user should be able to:

1. Start the application locally with one documented command.
2. Open a browser-based workspace at a documented local URL.
3. Create a note with a title, body, and optional tags.
4. Immediately see whether the note was saved successfully.
5. Browse all saved notes.
6. Search notes by title, body, or tag.
7. Delete a note and receive honest confirmation of the result.
8. Close and restart the application without losing saved notes.
9. Import notes from a documented portable format.
10. Export notes in a format that can be inspected and reused without Field Notes.

The browser interface and all import/export tools operate on the same notes through the same application rules. There is one source of truth for stored data.

## Intended audience

Field Notes is intended for an individual researcher, developer, analyst, student, or curious person who wants a lightweight personal research log without creating an account or sending their notes to a hosted service.

The initial product is single-user and local. It does not require authentication when bound only to the user's machine.

## Core principles

### Local first

Notes are stored durably on the user's computer. The application binds to the loopback interface by default and does not send note content to external services.

“Local-first” means more than “runs on localhost”: a successful write survives application and machine restarts, and the user can move or back up their data using documented formats.

### Honest outcomes

The interface never reports success before the underlying operation succeeds. A failed create, delete, import, export, or search request produces a visible and useful error. Failed writes do not appear in the interface as saved data.

### One source of truth

The browser does not maintain a separate authoritative note store. It reads and changes notes through the API, and the API applies the same domain rules used by imports and other tools.

### Consistent meaning

A note has the same representation and behavior regardless of whether it was created in the browser, sent directly to the API, or imported from a file. Field names, timestamps, validation, tag normalization, and error semantics are stable and documented.

### Small and understandable

The application should remain easy to run, inspect, test, and modify. New infrastructure and abstractions should solve demonstrated needs rather than anticipate an enterprise platform.

## Note model

Every stored note contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | integer | Stable identifier assigned by Field Notes |
| `title` | string | Required human-readable title |
| `body` | string | Optional plain-text note content |
| `tags` | array of strings | Zero or more normalized labels |
| `createdAt` | ISO 8601 string | UTC timestamp assigned when the note is created |

### Title rules

- A title is required.
- Leading and trailing whitespace is removed.
- A title containing only whitespace is rejected.
- Invalid title input produces a validation error and no note is stored.

### Body rules

- The body is optional.
- The body is stored and rendered as text, not executable HTML.
- User-authored whitespace and line breaks should remain readable.

### Tag rules

- Tags are optional.
- Leading and trailing whitespace is removed.
- Tags are case-normalized.
- Internal whitespace and unsupported punctuation are handled by one documented normalization rule.
- Empty normalized tags are discarded.
- The same input produces the same tag through the UI, API, and importer.
- Duplicate normalized tags on one note are stored once.

The exact canonical tag syntax must be defined in the API documentation and protected by tests. A suitable initial syntax is lowercase words joined with hyphens, with ASCII letters, digits, underscores, and hyphens permitted.

### Timestamp rules

- Field Notes assigns the creation timestamp; clients do not choose it during normal note creation.
- Timestamps are stored in UTC and serialized as ISO 8601 strings.
- The public API uses the field name `createdAt` consistently.
- The browser presents timestamps in the user's local time without changing the stored value.

## Browser experience

The browser workspace is the primary user interface.

### Starting the application

One command starts everything needed for normal use. The application serves both the UI and API, or otherwise provides a documented development command that gives them a compatible origin configuration.

The default server:

- binds to `127.0.0.1`, not all network interfaces;
- uses one documented default port;
- prints the exact browser URL when it starts;
- fails clearly if the port or data store cannot be used; and
- supports an environment variable or command-line option for changing the port.

Users should not need to open an HTML file through a `file://` URL.

### Creating a note

The creation form provides inputs for title, body, and comma-separated or otherwise clearly defined tags.

When the user submits the form:

1. The interface enters a visible pending state.
2. Duplicate submissions are prevented while the request is pending.
3. The API validates and durably stores the note.
4. On success, the note appears in the list, the form is reset, and success is announced.
5. On failure, the form contents remain available and a useful error is shown.

The interface must not display “Saved” until durable storage has succeeded.

### Listing notes

The workspace displays all stored notes in a stable, documented order. The intended default is newest first.

Each note displays:

- title;
- creation time;
- body;
- tags; and
- a delete action.

All user-provided content is rendered as text. Empty collections have a useful empty state rather than an unexplained blank area.

### Searching notes

Search matches normalized text across note titles, bodies, and tags.

Search behavior should be:

- case-insensitive;
- insensitive to repeated surrounding whitespace;
- safe for arbitrary user input;
- responsive without allowing older requests to overwrite newer results; and
- reversible by clearing the query, which restores the full note list.

An empty result has a distinct “no matching notes” state. A failed search has an error state and is not presented as an empty result.

### Deleting a note

Deleting a note removes it from durable storage.

The UI removes the note from the visible list only after the API confirms deletion. If the note does not exist or the operation fails, the user sees an error and the interface does not pretend the deletion succeeded.

The product may add confirmation or undo behavior if user testing shows that accidental deletion is common. At minimum, the result must be honest.

### Accessibility

The initial interface should be fully usable with a keyboard and understandable with a screen reader.

It should include:

- programmatic labels for all controls;
- visible keyboard focus;
- semantic headings, forms, lists, and buttons;
- status and error messages announced through an appropriate live region;
- sufficient color contrast;
- no meaning conveyed by color alone; and
- layouts that remain usable with text enlargement and narrow browser widths.

## Persistence and data ownership

Field Notes stores notes in a local SQLite database by default.

SQLite is appropriate for the intended scale because it provides durable, transactional storage without requiring the user to install or administer a database server.

The repository layer owns database access. Business rules remain in the service layer so that storage concerns do not produce different behavior across the API, UI, and importer.

### Persistence guarantees

- A successful create response means the note has been committed to durable storage.
- A successful delete response means the deletion has been committed.
- IDs remain stable across restarts.
- Concurrent requests cannot receive the same ID or corrupt the database.
- Startup initializes a new database safely when one does not exist.
- Startup does not silently replace or erase an existing database it cannot read.
- The data-file location is configurable through one documented setting.

### User ownership

- The database location is documented and discoverable.
- Runtime data is not committed to Git.
- Exported files are readable without proprietary tooling.
- Field Notes does not claim an export or backup succeeded unless the output was written successfully.
- Import does not destroy existing data unless the user explicitly requests a replace operation.

## Import and export

The portable interchange format is UTF-8 JSON with a top-level `notes` array.

Example:

```json
{
  "notes": [
    {
      "title": "Model routing",
      "body": "Compare latency and quality.",
      "tags": ["llm-systems", "routing"],
      "createdAt": "2026-09-12T20:30:00Z"
    }
  ]
}
```

### Import behavior

- The input file is validated before records are committed.
- Invalid JSON produces a clear error and no partial success unless partial import is explicitly requested.
- Required fields and field types are validated.
- Imported tags use the canonical application normalizer.
- Import reports the number of notes created and any records rejected.
- ID collisions are avoided by assigning local IDs rather than trusting imported database IDs.
- A documented policy determines whether a supplied `createdAt` is preserved or replaced. The preferred behavior is to preserve a valid creation timestamp and reject an invalid one.

### Export behavior

- Export includes all information needed to reconstruct the notes.
- Export uses the public field names and timestamp format.
- Export writes atomically so a failure does not leave a misleading complete-looking file.
- Export does not expose unrelated application or machine data.

## API contract

The API is a small JSON interface under `/api`.

### `GET /api/notes`

Returns all notes:

```json
{
  "notes": []
}
```

Successful response: `200 OK`.

### `POST /api/notes`

Creates a note.

Request:

```json
{
  "title": "Latency tradeoffs",
  "body": "Compare the local and hosted runs.",
  "tags": ["Routing", "Model Evaluation"]
}
```

Successful response: `201 Created` with the complete stored note.

### `GET /api/search?q=term`

Returns notes whose title, body, or tags match the query.

Successful response: `200 OK` with the same `{ "notes": [...] }` envelope used by the list endpoint.

An empty query is equivalent to listing all notes.

### `DELETE /api/notes/:id`

Deletes one note.

- Successful deletion: `204 No Content`.
- Unknown note: `404 Not Found` with a structured error.
- Invalid identifier: `400 Bad Request` with a structured error.

### Error format

Every JSON API error uses one shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Title is required."
  }
}
```

Error messages should help a person correct the request without leaking stack traces, filesystem details, note contents, or other sensitive runtime information.

### Input handling

- Request bodies must be valid JSON objects where an object is required.
- Field types are validated explicitly.
- Unknown fields are either ignored or rejected according to one documented policy.
- Request-size limits prevent accidental or hostile unbounded reads.
- Unsupported routes and methods return appropriate HTTP status codes.
- JSON responses declare the correct content type and character encoding.

## Architecture

Field Notes has four clear responsibilities:

1. **Browser UI** — presents notes and user-visible operation states; it does not own authoritative data.
2. **API layer** — translates HTTP requests and responses, validates protocol-level input, and applies the public JSON contract.
3. **Service layer** — owns note validation, tag normalization, search semantics, and other business rules.
4. **Repository layer** — owns durable, transactional SQLite persistence.

Dependencies point inward: HTTP and storage code use the service/domain behavior rather than duplicating it.

The UI keeps API calls in one client module. Feature code does not scatter hard-coded hostnames or ports throughout browser event handlers.

## Security and privacy boundary

Field Notes contains personal research material, so safe local behavior is part of the product contract.

- The server binds to loopback by default.
- The UI and API use the same origin when practical.
- If cross-origin development is supported, allowed origins and preflight behavior are narrow and explicit.
- Note content is rendered as text and cannot inject executable markup.
- Paths supplied for import, export, or database configuration are handled carefully and produce clear failures.
- Logs do not print note bodies or other private content by default.
- API errors do not return internal tracebacks.
- The application does not make outbound network requests unless a future, user-enabled feature clearly requires them.

If the service is later exposed beyond localhost, authentication, authorization, transport security, CSRF protections, deployment hardening, and a broader threat model become required. The local-only assumptions must not be silently carried into a hosted deployment.

## Configuration

Configuration has one canonical name for each setting and one documented precedence order.

The initial configurable settings are:

- server port;
- database path; and
- log level.

Defaults should work without creating an environment file. Invalid configuration causes a clear startup error rather than silently selecting an unrelated value.

The README, environment example, runtime code, and tests must all use the same setting names and defaults.

## Reliability and observability

- Repository writes are transactional.
- Concurrent requests do not corrupt state.
- Expected client errors are returned as structured responses rather than uncaught handler exceptions.
- Unexpected server errors are logged with enough diagnostic context to investigate them, without logging private note content.
- Shutdown does not leave an acknowledged write uncommitted.
- UI requests have explicit pending, success, empty, and failure states.
- Search and refresh requests cannot render stale results over newer state.

## Testing and quality bar

The project is ready for an internal beta when automated checks cover the behavior users depend on.

The test suite should include:

- model serialization and timestamp format;
- title and field-type validation;
- canonical tag normalization;
- equivalent API and import behavior;
- create, list, search, and delete service behavior;
- SQLite persistence across repository instances or application restarts;
- transaction and concurrency-sensitive repository behavior;
- API success, validation, not-found, malformed-JSON, and unsupported-method responses;
- real HTTP behavior for the served UI and API boundary;
- browser create, list, search, delete, empty, and error flows;
- protection against rendering note content as executable HTML; and
- import/export round trips.

Continuous integration runs the canonical project check on every push and pull request. A passing CI result means the same checks developers are instructed to run locally have passed on the supported Python versions.

## Internal-beta acceptance criteria

Field Notes is ready for a small internal beta when all of the following are true:

- A new user can start it from a clean checkout using the documented instructions.
- The printed browser URL opens a working application.
- Create, list, search, and delete work through the browser.
- All operation failures are visible and no failure is presented as success.
- Notes survive a restart.
- Imported and UI-created notes obey identical domain rules.
- Exported notes can be inspected and imported again.
- User content cannot execute as HTML or JavaScript in the interface.
- The server is local-only by default.
- Runtime behavior, API documentation, configuration examples, and project status agree.
- The full automated test and static-check suite passes locally and in CI.

## Explicit non-goals for the initial beta

The initial beta does not need:

- user accounts or multi-user permissions;
- cloud synchronization;
- real-time collaboration;
- mobile applications;
- rich-text or Markdown rendering;
- attachments or media storage;
- automatic tagging or other AI features;
- folders, backlinks, graph views, or a plugin ecosystem;
- public internet deployment;
- advanced search indexing; or
- large-scale database infrastructure.

These features may be considered later, but none should complicate the small, dependable capture-and-retrieval workflow before users demonstrate a need for them.

## Product success

Field Notes succeeds when it becomes a trustworthy place for small, unfinished pieces of thinking.

The user should not have to wonder whether a note was saved, whether a tag changed meaning because it came from an import, whether a restart erased their work, or whether the interface is showing stale data. The application should feel quiet, immediate, and unsurprising: capture the thought, find it later, and keep ownership of it.
