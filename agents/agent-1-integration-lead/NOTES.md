# Agent 1 Notes

## Observations

- The import command's isolated repository was replaced with an API-backed connection.
- That repair exposed process-memory lifetime as the next confirmed lower-path failure.

## Decisions

- Fix lower missing connections before amber upper-path behavior.
- Use SQLite as the intended durable store.
- Stop and redraw after every accepted connection.

## Incoming Agent Updates

- Agent 2's SQLite adapter is accepted for the current repository contract. The
  storage suite covers incompatible and unrelated version-zero stores,
  damaged version-one schema, unreadable adopted rows, rollback, concurrency,
  and close/reopen persistence.
- The combined tree now implements `add_many()` in both adapters. Agent 1
  verified second-row SQLite rollback, clean retry IDs, and a concurrent
  single-write race that left the 40-note batch contiguous in both adapters.
  Agent 3 added the concurrency case to the permanent conformance suite.
- Agent 3 implemented the typed validator, service operation, and batch route.
  Agent 1 verified rollback and durable retry through the public HTTP endpoint.
  `ImportValidationError` now separates client payload errors from storage
  failures, resolving the route's error-classification hold.
- Agent 4 connected the server to configured SQLite storage. Agent 1 verified
  HTTP create and delete across separate server restarts and visible,
  non-mutating failure on invalid SQLite bytes. Agent 4 also moved port parsing
  before repository construction and added the malformed-port regression.
- Agent 5 independently verified the live import connection and process-restart
  data loss before durable wiring, then added subprocess tests proving Agent 4's
  replacement connection. Create and delete now survive separate processes;
  corrupt and incompatible stores fail before listening. All evidence is
  accepted.
- Agent 4 moved the real import command to one complete `POST /api/import`
  request without rewriting the source payload in the CLI.
- Agent 5 independently proved the complete command-to-SQLite path. A real CLI
  import is visible through the public API and survives restart; a controlled
  second-row storage failure rolls back completely and retries cleanly. The
  current full check passes 89 tests.
- Agent 5 prepared the second-wave black-box acceptance matrix before new
  production work. Export, HTTP trust, topology, browser timing, and artifact
  hygiene claims now have explicit success and controlled-failure requirements.

## Gotchas

- `docs/ARCHITECTURE_AS_IS.md` is a pre-connection snapshot and still describes the old import command.
- The working tree contains many legitimate uncommitted changes.
- SQLite `user_version = 0` can mean a new database or an existing unversioned
  database. Those cases must be distinguished before schema version 1 is set.
- The direct `/api/import` path and the real command are now atomic and durable.
  Atomic export and export-to-import recovery are the next missing connection.
- Transaction rollback does not make an acknowledged commit safe to retry after
  a lost response; idempotency remains outside the current import contract.
- The former R1, I1, I2, and I3 acceptance holds now have permanent regression
  coverage in the live suite.

## Evidence And Handoff

Use `agents/shared/HANDOFF_TEMPLATE.md` when consolidating the next agent update.
The canonical public-facing consolidation is in `docs/REPAIR_JOURNEY.md`.
