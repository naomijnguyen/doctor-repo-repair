# Agent 5 Notes

## Baseline Observations

- On 2026-09-12 Pacific, the canonical check passed on Python 3.12: Python
  compilation, frontend syntax, and 34 Python tests.
- The import command is connected to the running API. Its unit test mocks HTTP,
  so Agent 5 separately verified the real process boundary.
- A real import created two notes through HTTP and `GET /api/notes` returned
  both from the same server process.
- After that server was terminated and a new server process was started on the
  same port, `GET /api/notes` returned `{ "notes": [] }`.
- This proves the import-to-live-repository connection and the current
  process-memory lifetime. It does not prove durable persistence.

## Prepared Test Cases

- Repository reopen: create through the SQLite adapter in a temporary
  directory, close it completely, construct a new adapter for the same file,
  and compare IDs, fields, tags, and timestamps.
- HTTP restart persistence: launch a real server subprocess with explicit
  `FIELDNOTES_PORT` and `FIELDNOTES_DATA`; create through HTTP; terminate and
  wait; launch a new process against the same file; retrieve through HTTP.
- Import visibility: submit a valid multi-note file through the real import
  command or accepted batch entry point, then retrieve those records through
  the normal API and repeat after restart.
- Mid-batch rollback: inject a storage failure after at least one insertion
  attempt at the application boundary; confirm the batch reports failure and
  zero batch records remain through the normal API.
  - Prepared black-box case: start with a known database snapshot and import
    two otherwise valid notes where the second request exceeds the HTTP body
    limit. The current per-note POST design is expected to retain note one;
    the accepted batch design must leave the snapshot unchanged. This case has
    not yet been executed by Agent 5 and must not be reported as verified.
- Export recovery: export a populated database, import into a separate empty
  database, and compare meaningful fields under the accepted ID/timestamp
  policy. Force an export failure and confirm it does not replace an earlier
  valid file with a complete-looking partial file.
- Runtime-data hygiene: verify the database and SQLite `-wal`, `-shm`, and
  journal siblings remain untracked for both default and configured paths.

## Gotchas And Dependencies

- Repository reopen is blocked until Agent 2 supplies the SQLite adapter and
  an explicit close or context-manager lifecycle.
- Durable HTTP restart is blocked until the runtime composition work connects
  `FIELDNOTES_DATA` to server repository construction.
- Atomic rollback is blocked until Agent 3 supplies one batch-level operation
  using Agent 2's accepted transaction contract.
- Export recovery is blocked until an export implementation and overwrite
  policy exist.
- The server currently constructs a module-global repository and has no
  repository close hook. The restart harness must prove the child process has
  exited before reopening its database.
- Existing API tests call `handle_request()` directly and the import-tool test
  mocks `urlopen`; neither is substitute evidence for the required connection.
- `.gitignore` currently covers JSON under `data/`, but not SQLite databases or
  their `-wal`, `-shm`, and journal siblings. Hygiene is presently an expected
  failure, not a passing connection.
- Direct `git check-ignore` verification found `data/fieldnotes.db`,
  `data/fieldnotes.sqlite`, `data/fieldnotes.db-wal`,
  `data/fieldnotes.db-shm`, and `data/fieldnotes.db-journal` unignored. No
  SQLite artifact is currently tracked. `data/sample.json` is ignored.
- True mid-transaction rollback evidence requires a deterministic fault after
  at least one insertion attempt. Rejecting a batch before insertion proves
  validation atomicity, not transaction rollback. If there is no safe external
  failure trigger, the accepted composition contract needs a narrow test-only
  repository/fault seam.
- A fixed free-port probe has a small allocation race. Prefer a runtime that
  can bind port zero and report its address; otherwise use a bounded readiness
  poll and capture child logs.

## Evidence

- Success boundary: started `python3 -m fieldnotes.server` on port 8876, ran
  `python3 tools/import_sample.py data/sample.json --api-url
  http://127.0.0.1:8876`, and retrieved two imported notes with
  `GET /api/notes`.
- Failure boundary: terminated that child, started a genuinely new server
  process on port 8876, and retrieved `{ "notes": [] }`.
- Pre-storage full-suite result: 34 tests passed on Python 3.12; compilation
  and frontend syntax checks passed.
- Environment note: the sandbox printed `nice(5) failed: operation not
  permitted` when launching background processes, but the server started,
  served both probes, and was fully stopped. This warning did not alter the
  observed HTTP results.

## Recommended Trace Update

- Forward connection: import file -> import command -> HTTP API -> live shared
  repository is verified for one running server process.
- Backward connection: notes returned by `GET /api/notes` trace back to the
  imported payload through the running API.
- Supported node-color change: keep the import-command connection green.
- Newly exposed boundary: server process restart -> durable state remains red;
  the current state owner is process memory.

## Agent 2 Storage Handoff Check

- Agent 5 independently reran the canonical check after the isolated SQLite
  adapter arrived: 47 tests passed on Python 3.12, including compilation and
  frontend syntax; `git diff --check` passed.
- `SQLiteNoteRepository` has explicit `close()` and context-manager lifecycle,
  so Agent 5 can prove a genuine close/reopen boundary.
- The adapter constructs missing parent directories, records schema version 1,
  adopts a structurally compatible version-zero `notes` table, and rejects an
  incompatible version-zero table without modifying its schema, rows, or
  `user_version`.
- Isolated create and delete persistence, failed-write rollback, and exact
  ID/timestamp retention have component-level coverage. Agent 5 will not count
  those adapter tests as proof that the public runtime is durable.
- The concurrency evidence covers eight threads sharing one repository object.
  It does not establish comprehensive multi-process concurrency behavior.
- Public restart verification remains blocked: `fieldnotes/server.py` still
  constructs the in-memory `NoteRepository`, and no server path currently uses
  `SQLiteNoteRepository` or `get_data_file()`.
- Startup-failure verification remains blocked on the same composition step.
  Once connected, an invalid SQLite file and an incompatible configured schema
  must make server startup fail visibly rather than activate empty memory.
- SQLite database, WAL, SHM, and journal paths remain unignored at this gate.
  Agent 5 will recheck both ignored and tracked state after Agent 4's hygiene
  update.
- Next public acceptance proof: create through HTTP, capture the returned ID and
  `createdAt`, stop the process fully, restart with the same configured database,
  and verify the exact note through HTTP; then delete it, restart again, and
  verify it remains absent.

## Agent 4 Durable Runtime Acceptance

- Status: **Public durable connection verified.**
- Agent 5 added `tests/test_http_persistence.py` with three subprocess-level
  tests. These invoke `python -m fieldnotes.server` with an absolute temporary
  `FIELDNOTES_DATA` path and communicate only through the public HTTP API.
- Create/restart proof: HTTP POST returned a complete public note; the first
  server received `SIGINT` and exited; a genuinely new process using the same
  database returned the exact ID, title, body, normalized tags, and `createdAt`.
- Delete/restart proof: the second process deleted that note through HTTP and
  exited; a third process using the same database returned an empty note list.
- Corrupt-database proof: a configured file containing invalid SQLite bytes made
  the server exit nonzero before listening. The bytes remained unchanged and no
  memory fallback activated.
- Incompatible-schema proof: a configured version-zero database with an
  incompatible `notes` table and existing row made the server exit nonzero
  before listening. Its `user_version`, schema SQL, and rows remained unchanged.
- Additional public startup probes verified the remaining Agent 1 adoption
  holds after their concurrent repair:
  - an unrelated version-zero database was rejected without file mutation;
  - a version-one database missing `notes` was rejected without mutation; and
  - a compatible version-zero table with unreadable tag JSON was rejected
    without mutation.
- Final combined verification at this gate: 59 tests passed on Python 3.12;
  Python compilation, frontend syntax, and `git diff --check` passed.
- Hygiene proof: no SQLite database or sidecar is tracked or present as an
  untracked repository artifact. The documented/default `data/*.sqlite3`
  database, journal, WAL, and SHM family is ignored.
- Hygiene scope: configured `.db` names and configured SQLite paths outside
  `data/` are not covered by the current ignore patterns. The verified claim is
  limited to the documented `.sqlite3` path family under `data/`.
- Remaining composition hold for Agent 1: `build_server()` constructs the
  repository before evaluating `get_port()`, and port parsing is outside the
  cleanup `try`. An invalid `FIELDNOTES_PORT` can raise after opening the
  repository without calling `close()`.
- Concurrency scope remains unchanged: eight threads sharing one repository
  object and one SQLite connection; no comprehensive multi-process concurrency
  claim is made.

### Trace update after Agent 4

- Forward connection: configured path -> composition -> SQLite repository ->
  injected service -> HTTP server is verified green.
- Backward connection: note returned by a fresh server process -> committed
  SQLite row -> original HTTP create is verified green.
- Durable deletion: absence after the third process traces to the prior HTTP
  delete and committed SQLite transaction.
- Startup failure: invalid/incompatible configured state stops before the HTTP
  boundary and does not fall back to memory.
- Next red boundary: atomic batch import through one public request and one
  repository transaction.

## Agent 3 Atomic Import Acceptance

- Status: **Public atomic-import connection verified.**
- Agent 5 added `tests/test_import_connection.py` with four subprocess tests.
  They invoke the real import CLI, a real server process, the public HTTP API,
  and the configured SQLite database.
- Durable success proof: one JSON file containing two notes was submitted by
  the CLI as one `/api/import` request. `GET /api/notes` returned both in input
  order with local IDs 1 and 2. A supplied `-07:00` timestamp was preserved as
  the same instant in canonical UTC, a missing timestamp was assigned in UTC,
  source IDs were ignored, fields were trimmed, and tags were normalized. A new
  server process using the same database returned the exact same public notes.
- Transaction rollback proof: Agent 5 seeded a preexisting note, installed a
  deterministic SQLite trigger that rejected the second batch INSERT, and ran
  the real CLI. The CLI received the server's failure, and the public list API
  returned the exact pre-import snapshot. The first batch row was not retained.
- Retry proof: after removing the controlled trigger, the same batch succeeded
  with IDs 2 and 3. There was no partial residue, duplicate, or consumed ID from
  the failed attempt. A new server process returned the complete exact result.
- Empty-batch proof: the real CLI reported zero imported notes, storage remained
  unchanged, and the next ordinary create still received ID 1.
- Validation proof: a timezone-naive `createdAt` in the second item made the CLI
  fail with the item index, and the public list remained the exact pre-import
  snapshot.
- Initial combined verification at this gate: 85 tests passed on Python 3.12;
  Python compilation, frontend syntax, and `git diff --check` passed. After the
  final hold regressions landed, Agent 5 reran the canonical check and all 89
  tests passed with the same compile, syntax, and diff checks.
- Hygiene recheck: no SQLite database, journal, WAL, or SHM artifact was tracked
  or left untracked in the repository by the process tests.
- Scope limit: rollback is verified. Retry after an acknowledged rollback is
  verified. A lost HTTP response after a successful commit can still make a
  blind retry duplicate notes; idempotency is not part of the current contract.
- Scope limit: duplicate normalized tags remain possible and were explicitly
  outside Agent 3's accepted batch-import work.

### Trace update after Agent 3

- Forward connection: JSON file -> real CLI -> one HTTP batch request -> one
  service call -> one SQLite transaction -> durable notes is verified green.
- Backward connection: notes returned after process restart trace to the single
  committed import request and its original payload.
- Failure connection: controlled second-row storage failure -> one transaction
  rollback -> exact prior public state is verified green.
- Next red boundary: atomic export and export-to-import recovery.

### Agent 1 ledger reconciliation (completed)

- The shared ledger now records the current 89-test result, one-request import,
  implemented batch contract, accepted atomic-import trace, and resolved
  malformed-port startup-order hold.
- Export and recovery are now the next red boundary.

## Second wave: pre-implementation acceptance matrix

Baseline independently observed before second-wave edits:

- milestone commit `7c18e13` (`Complete first multi-agent repair wave`);
- branch `codex/field-notes-triage`;
- author `Jennifer Naomi Nguyen <328120735+naomijnguyen@users.noreply.github.com>`;
- clean working tree; and
- no configured Git remote.

This matrix describes observable outcomes before implementation claims are
accepted. Tests should cross the named real boundary; a mock may create a
controlled timing or failure condition, but must not replace the connection
being proved.

| Connection | Success case | Controlled failure case | Real boundary that must be crossed | Contract dependency |
| --- | --- | --- | --- | --- |
| Populated state -> export | Create notes through the running API, invoke the accepted public export entry point, and parse readable UTF-8 JSON containing the required public fields and timestamps. | Reject or fail the export without reporting success or publishing a partial document. | Real server/entry point, configured SQLite database, and filesystem destination. | Agent 1 must freeze the export JSON shape and public entry point. |
| Export -> fresh recovery | Import that exported document through the real import command into a separate empty configured database; after a process restart, compare recovered fields and timestamps under the accepted local-ID policy. | Corrupt or contract-invalid export input must leave the fresh destination database unchanged. | Two distinct SQLite files, real commands/API, and at least one complete server restart. | Agent 1 must state whether equality excludes source IDs and how ordering is compared. |
| Atomic publication | Successful export publishes one complete destination document. | Inject a write, flush, close, or publish failure after an older valid destination exists; the older file must remain byte-for-byte identical and no temporary sibling may remain. | Actual destination-directory filesystem operations, not only an in-memory writer. | Agent 1 must freeze fail-if-exists versus intentional-replace behavior. |
| HTTP trust boundary | An allowed same-origin browser-style mutation with the required JSON media type succeeds and persists. | A disallowed or opaque origin and a wrong/missing mutation media type receive the accepted structured error and cause zero mutation. | Actual listening `ThreadingHTTPServer` socket and subsequent public state read. | Agent 1/4 must freeze allowed origins, `Origin: null`, media-type, and status/error rules. |
| Unsupported methods and limits | Supported preflight/methods and an in-limit request retain structured API behavior. | Unsupported methods and oversized bodies return the accepted JSON errors rather than HTML/default-handler output, with zero mutation. | Raw HTTP against the actual server handler. | Agent 4 transport contract and Agent 1 acceptance. |
| One-command local topology | The documented command starts loopback-only UI and API service, prints the exact usable browser URL, and uses the configured database. | Invalid port or storage configuration fails visibly without a false-ready message, hidden memory fallback, or leaked lifecycle owner. | Real subprocess, listening socket, static asset request, API request, stop, and restart. | Agent 1 must accept the topology Agent 4 proposes. |
| Slow browser save | A save captures draft A; while it is pending, the user types draft B; completion of A does not erase B. | A failed save leaves recoverable input and an honest error/pending state. | Real browser DOM and controlled delayed/failed HTTP response. | Agent 4 must freeze form-state semantics. |
| Stale browser reads | The newest search/list intent remains rendered when responses arrive out of order. | A late older response or a refresh failure cannot overwrite newer results or misreport a committed mutation as failed. | Real browser event loop, DOM, and controlled response ordering. | Agent 4 must freeze its generation/invalidation rule. |
| Artifact hygiene | Successful tests clean up temporary databases, exports, browser artifacts, and sidecars. | A deliberately failed operation also leaves no tracked/unignored runtime artifact or abandoned export temporary. | Filesystem plus Git tracked/ignored-state inspection after success and failure runs. | Export temporary naming must be known once Agent 2 proposes it. |

### Vocabulary attached to the matrix

- **Untrusted input** means data crossing into a boundary where this component
  cannot assume it is valid. A browser's `Origin` header, an import JSON field,
  a URL note ID, and an environment-variable port are all untrusted—even when
  the expected caller is our own UI or command—because a caller can be buggy,
  stale, hand-written, or malicious.
- **Durable mutation** means a state change that is intended to outlive the
  function and usually the process. Appending to a local Python list is a
  mutation, but it is not durable. Committing a SQLite transaction or atomically
  publishing an export file is durable mutation.
- **Publication point** is the moment incomplete private work becomes the
  official visible result. For import it is SQLite `COMMIT`; for atomic export
  it should be the final filesystem replacement/rename after the temporary file
  has been completely written and closed.
- **Invariant** is a statement that must remain true through success and
  failure. The central export invariant is: after any attempt, the destination
  is either the complete old export or the complete new export, never a partial
  mixture.
- **Connection proof** follows the actual arrow named in the architecture. A
  mocked repository can prove service policy, but it cannot prove that an HTTP
  request reached committed SQLite state or survived a new process.

### Initial status

- Matrix written before second-wave production changes.
- Export, trust-boundary, topology, and browser contracts await Agent 1 freeze.
- No second-wave production file or acceptance-test implementation changed by
  Agent 5 at this checkpoint.

## Handoff

Complete `agents/shared/HANDOFF_TEMPLATE.md` in the agent conversation when evidence is ready for Agent 1 review.
