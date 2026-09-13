# Agent 4 Notes

## Observations

- Add configuration, startup, and tool-entry-point findings here.

## Proposed Composition

- Canonical environment variable:
- Default SQLite path:
- Repository factory location:
- Startup failure behavior:

## Gotchas And Dependencies

- Record requirements from Agent 2's constructor and lifecycle.
- Record requirements from Agent 3's batch route.

## Evidence

- Server restart proof:
- Invalid-path failure proof:
- Import command proof:
- Export atomicity proof:
- Full-suite result:

## Recommended Trace Update

- Forward connection:
- Backward connection:
- Supported node-color change:

## Handoff

Complete `agents/shared/HANDOFF_TEMPLATE.md` in the agent conversation when this assignment is ready for Agent 1 review.

## Update 2026-09-12: Dependency And Composition Readiness

### Agent And Scope

- Agent: Agent 4, Runtime Composition and Portability.
- Assigned connection: configured data path -> repository composition -> running
  server, followed later by batch-import CLI migration and portable atomic export.
- Files eventually owned: `fieldnotes/config.py`, a new composition/factory module,
  composition-only sections of `fieldnotes/server.py`, `tools/import_sample.py`
  after the batch gate, export implementation and focused Agent 4 tests.
- Subagents used: three read-only reviews covering Agent 2 storage readiness,
  Agent 3 import readiness, and Agent 1/Agent 5/shared-note integration state.
- Changes made in this update: notes only; no production or test code changed.

### Observed Runtime Before Agent 4 Connection

- Entry point: `python3 -m fieldnotes.server`.
- Current call path: server -> module-global `NoteRepository()` -> `NoteService` ->
  API handler.
- Current state owner: the in-memory repository created while importing
  `fieldnotes.server`.
- Current lifetime: one server process; Agent 5 verified that a genuinely new
  server process returns an empty note list.
- Current failure boundary: `FIELDNOTES_DATA` is parsed but never used to construct
  runtime storage. The isolated SQLite adapter is not selected by the server.
- Current full-suite evidence: `./scripts/check.sh` passes 45 tests after Agent 2's
  11 isolated SQLite/conformance tests were added.

### Storage Gate Status: Closed Pending Agent 1 Acceptance

Agent 2 delivered `SQLiteNoteRepository(database_path: str | Path)` with the
structural operations `list`, `add`, `delete`, and `clear`, plus `close()` and
context-manager support.

The isolated evidence covers:

- missing-parent creation and schema initialization;
- committed create and delete surviving close and reopen;
- exact ID, field, tag, and timestamp preservation;
- `BEGIN IMMEDIATE` mutations and rollback after a forced failure;
- continued repository use after rollback;
- concurrent additions with unique sequential IDs;
- invalid SQLite content failing visibly; and
- unknown nonzero schema versions failing visibly.

Agent 1 nevertheless placed acceptance hold S1 on existing version-zero schema
handling. `PRAGMA user_version = 0` can describe either a new database or an
existing unversioned database. The current constructor runs `CREATE TABLE IF NOT
EXISTS`, stamps version 1, and can therefore bless an incompatible existing
`notes` table before later operations discover missing columns.

Required proof before runtime selection:

```text
create existing SQLite file with an incompatible notes table
construct SQLiteNoteRepository
construction fails visibly
user_version remains 0
existing table and data remain unchanged
```

Agent 1 owns acceptance, so Agent 4 will not connect the server merely because the
current adapter tests pass. Doing so would promote a known isolated compatibility
defect into the default application startup path.

### Proposed Composition After Storage Acceptance

- Canonical environment variable: `FIELDNOTES_DATA`.
- Legacy compatibility fallback: `FIELD_NOTES_DATA`.
- Recommended default SQLite path: `./data/fieldnotes.sqlite3`.
- Repository factory location: a small new composition module; final name should
  be selected when the accepted adapter is integrated.
- Path rule: resolve the configured path once at composition time. Relative-path
  behavior must remain explicit because different working directories can
  otherwise select different database files.
- Startup failure behavior: fail visibly for an unusable, corrupt, or unsupported
  database. Never silently fall back to memory.
- Lifecycle: construct one repository for the server runtime and close it through
  the accepted `close()` or context-manager contract on clean shutdown and failed
  startup.
- Server edit policy: preserve the concurrent request-size, error-containment,
  CORS, and response-header work already present in `fieldnotes/server.py`; change
  only construction, injection, and shutdown ownership.
- Test boundary: Agent 4 adds focused composition/startup tests. Agent 5 retains
  ownership of black-box subprocess restart evidence.

### Import Gate Status: Closed

Agent 3's direction is accepted, but the batch implementation and remaining
contract details are not yet frozen.

Accepted direction:

```text
import command
    -> one POST /api/import
    -> complete route validation
    -> one service batch operation
    -> repository add_many
    -> one transaction
    -> all rows committed or none published
```

The importer should remain HTTP-based. Agent 5 already proved that the repaired
command reaches the running API and the same live state returned by
`GET /api/notes`. Opening SQLite directly from the import command would discard
that verified authority boundary and introduce a second writer.

The current per-note HTTP adapter must remain until the batch gate opens. It is
connected to the correct state owner but uses the wrong unit of work: a later POST
failure can leave earlier notes committed.

Still required before Agent 4 migrates the CLI:

- Agent 1 freezes the structural `add_many` input and output shapes.
- Agent 2 implements `add_many` in both repositories without looping through the
  public `add()` method.
- Agent 3 implements the route, service operation, timestamp policy, and tests.
- A deterministic failure after at least one insertion attempt proves rollback to
  the exact pre-import state.
- Successful imported records remain visible after server restart.

The proposed request is `POST /api/import` with `{ "notes": [...] }`. Valid
supplied `createdAt` values preserve their instant and are canonicalized to UTC;
missing timestamps are assigned by the application; source IDs remain ignored.

One contract detail remains unresolved: empty batch behavior. Agent 3 proposed
`201` with zero imported notes, while Agent 1 correctly noted that 201 claims
creation. Agent 4 recommends accepting the no-op with:

```text
200 OK
{ "imported": 0, "notes": [] }
```

Rejecting an empty batch is also coherent if Agent 1 prefers a stricter API.

### Export Gate Status: Closed Behind Persistence And Import

After durable runtime and atomic import are accepted, Agent 4 will add export that:

- reads from the same configured authoritative repository;
- serializes portable public fields, including `createdAt`;
- writes UTF-8 JSON to a temporary sibling file;
- flushes and closes the complete temporary output;
- atomically replaces the destination only after successful completion;
- removes temporary output after pre-replacement failure; and
- never includes configuration, logs, filesystem details, or SQLite sidecars.

Recommended destination-conflict policy: refuse to replace an existing export
unless the user supplies an explicit `--force`. Even with `--force`, replacement
must remain atomic so a failed export preserves the previous valid file.

### Runtime Data Hygiene

Before runtime composition creates real databases, `.gitignore` needs narrow
coverage for the accepted database extension and SQLite companions:

```text
data/*.sqlite3
data/*.sqlite3-journal
data/*.sqlite3-wal
data/*.sqlite3-shm
```

The pattern choice should follow the frozen default filename and must not untrack
or obscure the committed sample JSON fixture.

### Agent 5 Verification Handoff Requirements

After the server connection is implemented, provide Agent 5 exact commands for:

1. Start a real server with explicit `FIELDNOTES_PORT` and `FIELDNOTES_DATA` in a
   temporary directory.
2. Create a note over HTTP.
3. Stop the exact child process and wait for complete exit.
4. Start a genuinely new process using the same database.
5. Retrieve the same note, ID, tags, and timestamp through the normal API.
6. Start against an unusable or incompatible database and prove visible startup
   failure without memory fallback or file replacement.
7. Verify the database, journal, WAL, and SHM paths remain untracked.

Later handoffs add batch visibility, mid-transaction rollback, post-import
restart, export/import recovery, and failed-export preservation.

### Current Collision And Ownership Notes

- `fieldnotes/config.py`, `fieldnotes/server.py`, `tools/import_sample.py`,
  `.gitignore`, and related tests already contain legitimate uncommitted work.
- Agent 4 changes must be surgical and preserve those edits.
- `fieldnotes/sqlite_repository.py` and its query/schema internals remain Agent 2
  territory.
- Import validation, timestamp policy, service batching, and transaction semantics
  remain Agent 3 and shared-contract territory.
- General HTTP hardening and browser behavior remain outside Agent 4.
- Agent 1 owns shared-contract acceptance and integration order.

### Recommended Trace Update

- Isolated SQLite adapter -> database remains implemented but acceptance-held
  until S1 is resolved.
- Server -> in-memory repository remains the active runtime arrow.
- Import command -> running API -> current live repository remains verified green
  for one process.
- Server process restart -> durable state remains red until Agent 4 composition and
  Agent 5 black-box evidence are complete.
- Batch import and export arrows remain inactive.

### Agent 4 Next Action

Wait for Agent 2 to resolve S1 and for Agent 1 to explicitly accept the storage
gate. Then implement only configured server composition and lifecycle, run focused
and full checks, and hand the resulting process boundary to Agent 5 before
starting any batch-import or export work.

## Update 2026-09-12: Durable Runtime Connection Implemented

### Accepted Incoming Storage Contract

Agent 2 resolved acceptance hold S1. The storage suite now proves both sides of
version-zero handling: a compatible unversioned `notes` table is adopted without
data loss, while an incompatible one is rejected during construction without
changing its schema, rows, or `user_version`.

The incoming full suite passed 47 tests before Agent 4 composition changes.

### Work Completed

- Added `fieldnotes/composition.py` as the explicit runtime composition point.
- `create_repository(database_path=None)` resolves configuration once and creates
  the accepted `SQLiteNoteRepository`.
- `create_service(database_path=None)` connects one `NoteService` to that exact
  repository and returns both the service and repository lifecycle owner.
- Changed the default data path from `./data/fieldnotes.json` to
  `./data/fieldnotes.sqlite3`.
- Preserved `FIELDNOTES_DATA` as canonical and `FIELD_NOTES_DATA` as the legacy
  fallback.
- Updated `.env.example` with the canonical SQLite data-path setting.
- Removed module-import-time in-memory repository and service construction from
  `fieldnotes/server.py`.
- Added `handler_for(service)` so each server receives its explicitly composed
  service rather than consulting mutable global state.
- Added `build_server(port=None, data_path=None)` to compose storage and service,
  bind the HTTP server, and close the repository if binding fails.
- Updated `main()` to close both the HTTP server and repository in `finally`.
- Preserved the existing request-size, error-containment, CORS, method, and
  response behavior in `Handler`.
- Added SQLite database, journal, WAL, and SHM patterns under `data/` to
  `.gitignore`.
- Added focused composition tests without modifying Agent 2's adapter tests or
  Agent 3's import code.

### Connection Change

Before:

```text
server import
    -> new in-memory NoteRepository
    -> NoteService
    -> process-lifetime state
```

After:

```text
FIELDNOTES_DATA or accepted default
    -> composition.create_repository
    -> SQLiteNoteRepository
    -> composition.create_service
    -> injected HTTP handler
    -> durable configured database
```

No memory fallback exists in this path. Database construction errors propagate
before the HTTP server starts.

### Files Changed By Agent 4

- `fieldnotes/composition.py` — new explicit composition point.
- `fieldnotes/config.py` — SQLite-appropriate default path.
- `fieldnotes/server.py` — service injection, build function, and lifecycle close.
- `.env.example` — canonical database-path example.
- `.gitignore` — SQLite runtime artifacts under `data/`.
- `tests/test_composition.py` — six focused composition and failure tests.
- `agents/agent-4-runtime-composition/NOTES.md` — this append-only handoff.

### Focused Evidence

`python3 -m unittest tests.test_composition -v` passes six tests proving:

1. The default path names a SQLite database.
2. Canonical configuration selects the database and the adapter creates missing
   parent directories.
3. Service and repository share the same state owner.
4. Invalid SQLite content fails without memory fallback or file replacement.
5. The built server uses `SQLiteNoteRepository` and supports port zero for an
   isolated test harness.
6. A server-bind failure closes the already-created repository.

The first focused run exposed Python 3.9 evaluating `int | None` at import time.
Although the project declares Python 3.11 or newer, adding
`from __future__ import annotations` to `server.py` preserved compatibility at
negligible cost. The focused suite then passed.

### Full Evidence

- `./scripts/check.sh`: 53 tests passed, plus Python compilation and frontend
  syntax checks.
- `git diff --check`: passed.
- `git check-ignore` confirmed all four representative runtime paths are ignored:
  `data/example.sqlite3`, `data/example.sqlite3-journal`,
  `data/example.sqlite3-wal`, and `data/example.sqlite3-shm`.
- No default runtime database was created during testing; composition tests use
  temporary directories.

### Contract Assumptions

- `SQLiteNoteRepository(database_path)` and `close()` are accepted Agent 2
  interfaces.
- Missing parent directories are created by the adapter.
- Relative configured paths remain relative to the startup working directory;
  configuration is read once per constructed runtime.
- Invalid, incompatible, or unsupported databases are fatal startup errors.
- In-memory `NoteRepository` remains available for unit tests but is not a
  production fallback.
- Import remains on its verified HTTP path until Agent 3's batch contract is
  accepted and implemented.

### Findings For Other Agents

- Agent 5 can now run the real HTTP create -> stop -> restart -> HTTP list proof
  using explicit `FIELDNOTES_PORT` and `FIELDNOTES_DATA`.
- Agent 5 should also verify persisted delete, unchanged IDs/timestamps, invalid
  configured database startup failure, and Git hygiene at the process boundary.
- Agent 3 remains blocked from atomic storage until both repositories implement
  the accepted `add_many` contract. Agent 4 did not alter import behavior.
- The server can now accept `port=0` through `build_server`, which may help an
  in-process harness avoid fixed-port allocation races. A subprocess still needs
  a way to observe the selected port or should use a bounded readiness probe.
- Export remains gated behind successful durable-runtime and atomic-import
  verification.

### Recommended Trace Update

- Forward connection to test: configured path -> composition root -> accepted
  SQLite adapter -> injected service -> HTTP server.
- Backward connection to test: note returned after process restart -> committed
  SQLite row -> original HTTP create.
- Supported node-color change: composition and server-to-SQLite arrows may move
  from red to amber pending Agent 5's black-box restart and failure evidence.
- Import batch and export arrows remain inactive.

### Handoff

Agent 4's durable-runtime implementation is ready for Agent 1 review and Agent 5
independent process verification. No batch-import or export work should begin
from this update alone.

## Update 2026-09-12: Import Command Redirected To Atomic Batch Route

### Accepted Incoming Batch Contract

Agent 3 activated and tested the atomic path through `POST /api/import`,
`NoteService.import_notes`, and repository `add_many`. The accepted route returns
`201` after a non-empty committed batch and `200` for an accepted empty no-op.
Validation failures use the structured `400 invalid_request` envelope. Source IDs
remain database-local, valid supplied timestamps preserve their instant in
canonical UTC form, and missing timestamps are application-assigned.

The incoming full suite passed 74 tests. The remaining amber connection was the
user-facing command, which still translated one input file into repeated
`POST /api/notes` calls.

### Work Completed

- Replaced the repository-shaped `ApiNoteRepository` per-note adapter with
  `ApiImportClient`.
- The client sends exactly one `POST` to `/api/import` containing the original
  complete JSON payload.
- The command parses JSON locally only to provide a readable file/JSON error.
- Semantic validation remains authoritative in the running API; the command does
  not normalize tags, discard source fields, or assign timestamps.
- Preserved the configurable `--api-url` and canonical configured-port default.
- Preserved useful structured API error messages for both 4xx validation and 5xx
  storage failures.
- Connection failures continue to name the selected API origin.
- Added defensive response-shape validation so a malformed server response is not
  printed as a successful import.
- Updated focused command tests for complete-payload preservation, one-request
  behavior, empty-batch success, API failure without retry, connection failure,
  malformed success responses, source-field preservation, and malformed files.

### Connection Change

Before:

```text
one import file
    -> validate locally
    -> adapter.add(note A) -> POST /api/notes -> commit A
    -> adapter.add(note B) -> POST /api/notes -> commit B
    -> adapter.add(note C) -> POST /api/notes -> possible failure
```

After:

```text
one import file
    -> parse JSON locally without semantic transformation
    -> one POST /api/import with the complete original payload
    -> server validation
    -> one service batch call
    -> one repository add_many transaction
    -> commit all or publish none
```

### Why The Command Does Not Reuse `import_notes`

The legacy `import_notes(path, repository)` helper validates and then loops over
`repository.add`. Reusing it would preserve the wrong per-note unit of work.

The command also should not call `validate_import_payload` and reconstruct the
request before sending it. Doing so would normalize source data and assign missing
timestamps in the CLI, followed by a second validation in the server. Sending the
original parsed document keeps one semantic authority and preserves fields such
as `createdAt` for the accepted server policy.

### Files Changed In This Update

- `tools/import_sample.py` — one-request `ApiImportClient`, readable file parsing,
  response-shape validation, and batch-result output.
- `tests/test_import_tool.py` — seven focused CLI/client tests.
- `agents/agent-4-runtime-composition/NOTES.md` — this append-only handoff.

### Evidence

- `python3 -m unittest tests.test_import_tool -v`: seven tests passed.
- `./scripts/check.sh`: 80 tests passed, plus Python compilation and frontend
  syntax checks.
- `git diff --check`: passed.
- The focused request test asserts one `urlopen` call, `/api/import`, method POST,
  JSON content type, and byte-decoded payload equality with the original document.
- The error test asserts the structured API detail remains visible and the client
  does not retry a rejected batch.

The first focused run exposed Python 3.9 eagerly evaluating the tool's
`str | Path` annotation. `from __future__ import annotations` was added to preserve
the project's existing local-test portability; no request ran before that import
failure was corrected.

### Remaining Boundaries

- Agent 5 must independently run the real command against the durable server,
  retrieve the complete batch through the public list API, fully stop the process,
  restart against the same database, and retrieve the same notes, IDs, and
  timestamps again.
- Agent 5 must pair success with a controlled public-path batch failure and prove
  the database after failure equals the pre-import snapshot.
- A response lost after a successful commit remains an ambiguous retry and can
  duplicate a batch. Idempotency keys are outside the accepted transaction
  contract and no retry-safety claim is made.
- Portable atomic export remains Agent 4's next gated feature after durable import
  verification is accepted.

### Recommended Trace Update

- Import command -> `/api/import` may move from amber to green based on focused
  one-request contract evidence.
- Complete public import -> durable database -> process restart -> public list
  remains amber pending Agent 5's independent black-box proof.
- Atomic rollback is green at the repository/component boundary and awaits its
  public connection proof.
- Export remains inactive.

### Handoff

The command rewrite is ready for Agent 1 review and Agent 5 independent
verification. Agent 4 made no changes to batch validation, service semantics,
repository transactions, API route behavior, or browser code.
