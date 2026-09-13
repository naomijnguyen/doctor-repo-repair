# Shared Notes And Integration Ledger

Agent 1 maintains the consolidated sections in this file. Other agents should write full details in their own `NOTES.md`; urgent cross-agent notices may be added to the appropriate inbox subsection without editing another agent's entry.

## Current Verified State

- Branch observed: `codex/field-notes-triage`.
- Baseline commit: `1884f4d785f2c3042792d45854e06c0837599408`.
- The working tree contains intentional uncommitted changes from prior agents.
- Three earlier agents completed broad repository exploration; the new assignments should investigate their specific connection rather than repeat the inventory.
- `./scripts/check.sh` most recently passed 89 tests after the atomic import,
  one-request command, hold regressions, and Agent 5's public import-connection
  tests arrived. Python compilation, frontend syntax checks, and
  `git diff --check` also pass.
- The import command now sends one complete payload to `POST /api/import`; it no
  longer posts each note separately.
- Imported notes are visible through `GET /api/notes` and Agent 1 has verified
  that a successful direct batch survives a complete server restart.
- Agent 5 independently verifies the real CLI -> batch API -> SQLite -> restart
  path, plus empty no-op, invalid-later-record rejection, and forced mid-batch
  rollback followed by a clean retry.
- The running server now uses configured SQLite storage. Agent 1 verified that
  an HTTP-created note survived a complete server restart with its ID, tags,
  and timestamp unchanged; an HTTP deletion also survived a second restart.

## Accepted Decisions

1. Fix missing storage and data-path connections before amber UI or HTTP cleanup.
2. Use SQLite as the intended durable local store.
3. Keep the in-memory repository available as a test adapter.
4. Prove each connection with one success case and one failure case.
5. Stop and redraw both traces after every accepted connection.
6. Agent 1 owns shared-contract acceptance and integration order.
7. Atomic import uses a frozen, storage-neutral `NoteDraft` in
   `fieldnotes.models` with `title`, `body`, immutable `tags`, and canonical UTC
   `created_at` values.
8. Both repositories expose
   `add_many(notes: list[NoteDraft]) -> list[Note]`; output order matches input,
   IDs are assigned locally, and any exception publishes none of the batch.
9. `POST /api/import` returns `201` only after a non-empty batch commits. An
   empty batch is an accepted no-op and returns `200` with zero imported notes.
10. Keep the repository interface structural and prove parity through shared
    conformance tests. Do not add an abstract base class or protocol during this
    repair unless a concrete type-checking need appears.
11. Keep import on the verified HTTP authority boundary. The command sends
    one complete batch request rather than opening SQLite as a second writer.

## Open Contract Questions

- Export conflict behavior when the destination already exists.
- Whether a future import retry contract should add idempotency keys.

## Cross-Agent Inbox

### Agent 2: Durable Storage

- Isolated `SQLiteNoteRepository` implementation received and independently
  rerun: all 16 storage and conformance tests pass.
- Verified: create/delete persistence across reopen, defensive copies, ID behavior,
  rollback after an aborting trigger, concurrent adds, invalid SQLite bytes, and
  unknown nonzero schema versions.
- Acceptance hold: an existing SQLite database with `user_version = 0` and an
  incompatible `notes` table is now rejected without mutation. The original
  schema-compatibility hold is resolved.
- Historical reproductions for the now-resolved holds found by Agent 1:
  - An unrelated version-zero SQLite database with another user table but no
    `notes` table was modified by adding `notes` and setting `user_version = 1`.
  - A database already marked version 1 but missing `notes` was silently given an
    empty `notes` table, masking an incomplete or damaged versioned schema.
  - A structurally compatible version-zero table containing unreadable tag JSON
    was stamped version 1 during construction, then failed on the first `list()`.
- The accepted `add_many` transaction contract is now implemented in both
  adapters.
- Holds S2, S3, and S4 are now resolved by focused tests in the current tree.
  The SQLite adapter is accepted for its single-write and batch contracts.
- Verified batch behavior: ordered local IDs, preserved canonical timestamps,
  empty no-op behavior, second-row SQLite failure rollback, unchanged prior
  state, clean retry without consumed IDs, and no use of public `add()` inside
  the batch.
- The permanent conformance regression races a 40-note batch against a single
  write in both adapters. The single write completes wholly before or after the
  batch, and each batch retains one contiguous ID range.

### Agent 3: Atomic Import

- Typed `NoteDraft`, shared complete-payload validation, service batching,
  `POST /api/import`, and focused success/failure tests are implemented.
- Verified: source IDs are ignored; valid imported instants become canonical
  UTC; missing timestamps are application-assigned; invalid record 2 makes zero
  storage calls; empty import returns `200`; non-empty success returns `201`.
- Agent 1 public-route proof: a trigger rejected row 2, `/api/import` returned
  `500`, and `GET /api/notes` returned zero rows. After removing the trigger,
  retry returned ordered local IDs 1 and 2; both rows survived server restart.
- Hold I1 is resolved in the live tree. Import validation now raises the dedicated
  `ImportValidationError`; the route maps only request decoding and that exception
  to `400`. A repository `ValueError` escapes `handle_request()` so the server can
  return its existing generic `500 internal_error` response. The focused test
  proves storage was called once and the exception was not mislabeled.
- Hold I2 is resolved in the live tree. The shared repository conformance suite
  races a 40-note batch against one single add for both memory and SQLite. Batch
  IDs remain contiguous, proving a single write cannot interleave inside them.
- Hold I3 is resolved by Agent 4. The command sends one complete `/api/import`
  request, preserves original timestamp/source fields for shared server-side
  validation, prints only a validated complete success response, and retains
  useful API and connection errors.
- The Python file-import helper now also calls `add_many()` exactly once; no
  per-note storage fallback remains in Agent 3's importer boundary.
- Agent 5 completed the public handoff: the real command -> batch API -> committed
  SQLite -> full process restart -> normal API path preserves imported records.
  Its connection suite also covers empty no-op/ID behavior, later invalid
  timestamp rejection, and mid-batch storage rollback followed by a clean retry.
- Agent 3 status: implementation and focused acceptance holds I1/I2 are complete;
  the complete public connection now has independent Agent 5 evidence. Detailed
  implementation evidence remains in `agents/agent-3-atomic-import/NOTES.md`.

### Agent 4: Runtime Composition And Portability

- Durable runtime composition received and reviewed. `fieldnotes.composition`
  resolves the configured path, creates `SQLiteNoteRepository`, injects that
  exact state owner into `NoteService`, and gives the server lifecycle ownership.
- Agent 1 success proof: create over HTTP, terminate the server, start a new
  process against the same file, and retrieve the exact note; then delete,
  restart again, and observe an empty list.
- Agent 1 failure proof: startup against invalid SQLite bytes exited nonzero and
  left the file unchanged. No memory fallback occurred.
- Runtime hygiene is verified for `.sqlite3`, journal, WAL, and SHM files under
  `data/`; no SQLite artifact is tracked.
- Initial hold R1 found that `build_server()` created the repository before
  parsing `FIELDNOTES_PORT`. The update below resolves it by parsing the port
  first and proving malformed configuration creates no database.
- The durable runtime connection and startup ordering are accepted green.

#### Agent 4 update: runtime startup order and batch command

- Runtime hold R1 is resolved in `fieldnotes.server.build_server`: configured port
  parsing now occurs before repository construction.
- Focused proof: with `FIELDNOTES_PORT=not-a-port`, `build_server()` raises before
  creating the configured database. The existing socket-bind failure test still
  proves an already-open repository is closed when HTTP binding fails.
- Import hold I3 is implemented: `tools/import_sample.py` now sends exactly one
  `POST /api/import` containing the complete original parsed JSON document.
- The command performs local JSON parsing for readable file errors but leaves tag,
  timestamp, source-ID, and other semantic policy to the running API.
- The command accepts the approved 200 empty and 201 non-empty response shapes,
  preserves structured API failure detail, performs no automatic retry, and
  refuses to print success for a malformed success response.
- Seven focused command tests cover one-request payload equality, route/method,
  empty success, API rejection, connection failure, invalid success shape, and
  preservation of source fields.
- Agent 4's handoff-time rerun, before the final hold regressions landed, passed
  86 tests, including four real import-connection
  cases for durable CLI visibility/restart, empty no-op, invalid timestamp
  rejection, and mid-batch storage rollback/retry.
- `git diff --check` passes.
- Accepted trace change: malformed-port startup ordering and command-to-batch
  route are green in the current maps and permanent test suite.
- Next Agent 4 gate: portable atomic export may now begin because the durable
  public import connection is accepted. Ambiguous retry after a lost post-commit
  response remains explicitly out of scope without an idempotency-key contract.

### Agent 5: Connection Verification

- Independent durable-runtime evidence received and accepted in
  `tests/test_http_persistence.py`.
- Verified through public HTTP across three server processes: create survives
  restart with exact public fields, and delete survives a second restart.
- Verified startup failures: corrupt SQLite bytes and an incompatible existing
  schema stop the server before listening and preserve the configured files.
- Verified current hygiene scope: documented `data/*.sqlite3` databases and
  their journal, WAL, and SHM files are ignored; none are tracked.
- Durable-runtime subprocess suite: 3 tests passed. The independent import
  connection suite adds 4 real-process cases covering durable CLI visibility,
  empty no-op, invalid timestamp rejection, and mid-batch rollback/retry.
- The earlier malformed-port finding is resolved by Agent 4: port parsing now
  occurs before repository construction, and the focused regression proves an
  invalid port creates no database.

#### Agent 5 update: public atomic import connection

- `tests/test_import_connection.py` now exercises the real command and server
  against temporary configured SQLite databases.
- A multi-note CLI import is visible through the normal API and survives a full
  server-process restart with fields and timestamps preserved.
- An empty import is a no-op and does not consume the next local ID.
- An invalid timestamp later in a batch rejects the complete import with zero
  mutation.
- A deterministic mid-batch SQLite failure returns an error, leaves no partial
  batch, preserves prior state, and allows a clean retry without residue.
- These four public import-connection tests pass in the current 89-test canonical
  suite. The atomic import connection is ready for Agent 1 acceptance/redraw.
- Agent 5 independently reran `scripts/check.sh` on 2026-09-12 while reconciling
  this ledger: all 89 tests passed, followed by Python compilation, frontend
  syntax checks, and `git diff --check`.
- Next Agent 5 boundary: verify portable atomic export through a real populated
  server/database, then import that file into a separate empty database and
  compare the recovered public records under the local-ID policy. A controlled
  export failure must preserve the prior destination byte-for-byte.
- Agent 5 prepared the complete second-wave acceptance matrix in its own
  `NOTES.md`. It is test planning only: no second-wave production implementation
  is claimed at this checkpoint.

## Integration Log

### Update 0: Import command connection

- Before: `tools/import_sample.py` created a private `NoteRepository`, printed records, and exited.
- After: the tool posts validated notes through the running API.
- Success proof: importing two sample notes followed by `GET /api/notes` returned both records.
- Failure boundary: restarting the server returned `{ "notes": [] }`.
- Trace change: import command moved from red to green; durable storage remains red.

### Update 2: Atomic API batch connection

- Before: every imported note used its own create request and transaction.
- After: direct `POST /api/import` validates the complete payload, calls one
  service operation, and commits through one repository `add_many` transaction.
- Success proof: two notes returned in order with local IDs and survived a full
  server restart.
- Failure proof: an SQLite trigger rejected row 2; the API returned `500` and no
  batch row remained.
- Trace change at initial review: validator, service batch operation, and
  repository transaction moved green. The later I1 and command holds are now
  resolved by their permanent regressions and public connection evidence.

### Update 3: Atomic import connection completed

- Before: the direct route worked, but validation/storage `ValueError` boundaries,
  permanent batch concurrency coverage, and the command-to-batch arrow remained
  on hold.
- After: `ImportValidationError` separates client input from storage failures;
  memory and SQLite conformance tests preserve contiguous batch IDs; the command
  sends one complete request; and Agent 5 verifies the entire public path across
  restart and rollback/retry scenarios.
- Success proof: real CLI multi-note import remains visible with preserved fields
  after a new server process opens the same SQLite database.
- Failure proof: later invalid input performs zero mutation, and a second-row
  storage failure rolls back the full transaction before a clean retry.
- Trace change accepted: file -> command -> batch route -> service -> one
  repository transaction -> SQLite -> restarted API visibility is green.

## Trace History

| Update | Forward trace | Backward trace | Newly exposed boundary |
| --- | --- | --- | --- |
| 0 | Import tool reaches API and live repository | Printed note traces back through API to process memory | Server restart erases the shared repository |
| 1 review | Isolated SQLite adapter reaches a database file but is not selected by runtime | Reopened record traces to SQLite in isolation only | Incompatible `notes` schema fixed; unrelated, incomplete versioned, and unreadable adoption cases remain |
| 2 accepted | HTTP create and delete reach configured SQLite and survive separate server processes | Restarted API records trace to the original committed SQLite rows | Malformed port configuration opens storage before failing; atomic batch import is the next red connection |
| 3 review | Direct batch API reaches one SQLite transaction and rolls back a second-row failure | Restart-visible imported rows trace to one committed batch response | Import command still sends per-note requests; storage `ValueError` is mislabeled as a client error |
| 4 accepted | Real command reaches one batch transaction; validation/storage failures stay distinct | Restart-visible imported rows trace back through the command and one committed SQLite batch | Atomic import is fully evidenced; portable export is the next planned lower-path connection |

## Acceptance Holds

### Storage hold S1: Validate existing version-zero schema

Before the isolated SQLite node turns green, construction must verify that an
existing `notes` table has the required columns and compatible schema. A database
with an incompatible table must fail during construction without changing
`user_version` or existing data.

Reproduction:

```text
create SQLite file with: CREATE TABLE notes (id INTEGER PRIMARY KEY)
construct SQLiteNoteRepository
observed: construction succeeds and sets user_version to 1
call list()
observed: OperationalError: no such column: title
```

Required proof: constructor rejects that database, leaves `user_version` at 0,
and leaves its existing table/data unchanged.

Status: resolved by Agent 2 and independently rerun by Agent 1.

### Storage hold S2: Do not claim an unrelated database

A version-zero SQLite file containing user tables but no `notes` table currently
receives a new `notes` table and is stamped version 1. Refuse this case without
changing tables, rows, or `user_version`. A truly empty version-zero database may
be initialized normally.

Status: resolved by Agent 2; focused test passes in the 56-test suite.

### Storage hold S3: Do not silently reconstruct a damaged versioned schema

A database already marked schema version 1 but missing the required `notes` table
currently receives a new empty table. Treat a known version as a contract: all
required version-1 schema must already exist and be compatible, or construction
must fail without mutation.

Status: resolved by Agent 2; focused test passes in the 56-test suite.

### Storage hold S4: Validate adopted rows before stamping an unversioned store

A structurally compatible version-zero `notes` table can contain tag values that
the repository cannot deserialize. Before adopting and stamping an unversioned
table, verify that existing rows are readable under the version-1 contract. On
failure, preserve version, schema, and rows unchanged.

Status: resolved by Agent 2; focused test passes in the 56-test suite.

### Runtime hold R1: Parse the port before opening storage

Before the fix, `build_server()` constructed `SQLiteNoteRepository` before calling
`get_port()`. A malformed `FIELDNOTES_PORT` therefore creates a database and then
raises `ValueError` outside the existing repository-close guard.

Required proof: malformed port configuration exits visibly, creates no database,
and opens no repository. Keep the existing test that proves a socket-bind failure
closes a repository that was successfully constructed.

Status: resolved by Agent 4; port parsing now precedes repository construction and
the permanent malformed-port regression passes.

### Import hold I1: Separate validation errors from storage errors

Before the fix, `POST /api/import` caught all `ValueError` exceptions raised by the
service call. That correctly handles payload validation but also converts a
repository `ValueError` into `400 invalid_request`.

Required proof: malformed import data returns `400`, while a repository
`ValueError` escapes `handle_request()` and becomes the server's existing
`500 internal_error`. Both cases must leave state unchanged.

Status: resolved by Agent 3 with `ImportValidationError` and focused route tests.

### Import hold I2: Preserve the batch concurrency guarantee in tests

Both repositories currently hold one lock around the complete batch, and Agent 1
verified that a single concurrent write cannot interleave an ID inside a 40-note
batch. Add this case to the shared repository conformance suite so later edits do
not weaken that guarantee.

Status: resolved by Agent 3 in the shared memory/SQLite conformance mixin.

### Import hold I3: Connect the command to the batch route

Before the fix, `tools/import_sample.py` called `POST /api/notes` once per note through a
repository-shaped adapter. It also cannot preserve imported `createdAt` through
that per-note create contract.

Required proof: one input file causes exactly one `POST /api/import`; a successful
batch prints only after the complete response; imported timestamps survive; and a
failed batch prints no partial success.

Status: resolved by Agent 4's `ApiImportClient` and seven focused command tests.
