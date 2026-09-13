# Agent 2 Notes

## Observations

- The live in-memory contract is structural: `list`, `add`, `delete`, and `clear`
  are the operations consumed by the service. No formal base class or protocol is
  required for the isolated adapter.
- `clear()` resets the in-memory next ID to 1. SQLite therefore must delete the
  `sqlite_sequence` row as part of the same transaction to remain conformant.
- Tags are repository values (`list[str]`), not relational entities in the
  current domain contract. They are stored as JSON text and validated when read,
  keeping SQL representation details out of `NoteService`.
- `PRAGMA user_version = 0` does not prove a database is empty. It may contain an
  older or unrelated `notes` table, so initialization must inspect that table
  before treating the database as fresh.
- Initialization now distinguishes four states: truly empty and safe to create;
  structurally compatible with readable rows and safe to adopt; structurally
  recognizable but unreadable and unsafe to adopt; or unrelated/incomplete and
  unsafe to modify.

## Proposed Decisions

- Keep a lightweight structural repository contract for now; conformance tests
  exercise both adapters without forcing a cross-owned service annotation change.
- Record schema version 1 in SQLite `PRAGMA user_version`. Refuse unknown versions
  visibly instead of guessing at or overwriting their schema.
- Use `BEGIN IMMEDIATE` for mutations. It acquires the SQLite write reservation at
  transaction start and makes insert/read-back/commit, delete, and clear atomic.
- Use SQLite `AUTOINCREMENT` IDs. They remain local, sequential for successful
  writes, and safe across repository reopen and concurrent callers.
- Before creating or version-stamping the schema, validate any existing `notes`
  table against the required columns, constraints, primary key, and
  `AUTOINCREMENT` behavior. Reject an incompatible table without attempting an
  implicit migration.
- Adoption also decodes every existing row before changing `user_version`.
  Version-one construction requires its `notes` table to already exist; it does
  not recreate a missing state owner.

## Gotchas And Dependencies

- Agent 4 should construct the adapter once per runtime and call `close()` during
  shutdown. The adapter creates missing parent directories but surfaces invalid
  database content and unsupported schema versions.
- The accepted `NoteDraft` and `add_many()` contract has now landed in both
  repositories. SQLite performs the whole batch under one lock and one
  `BEGIN IMMEDIATE`; it does not loop through public `add()`.
- A future migration design must distinguish "unversioned but compatible" from
  "unversioned and incompatible." The adapter currently adopts the compatible
  schema as version 1 and refuses the incompatible case without mutation.

## Evidence

- Success test: `test_committed_note_survives_close_and_reopen` and
  `test_committed_delete_survives_close_and_reopen` prove committed state and
  exact IDs/timestamps survive a new repository connection. Conformance and
  concurrency tests also pass against both adapters.
- Failure test: an aborting SQLite trigger makes `add()` raise
  `sqlite3.IntegrityError`; the prior row remains, the failed ID is not consumed,
  and a later write succeeds. Invalid database bytes and schema version 99 both
  fail visibly during construction without replacing the file. An incompatible
  version-0 `notes` table now also fails construction while preserving its
  `user_version`, original schema SQL, and existing data.
- Compatible adoption test: a version-0 database with the exact supported schema
  retains its existing note and timestamp, advances to schema version 1, and
  assigns ID 2 to the next note.
- Initialization classification tests: an unrelated version-0 database, a
  version-1 database missing `notes`, and a compatible version-0 table containing
  unreadable row data all fail without changing version, schema, or rows.
- Batch evidence now present in the shared tree: both adapters preserve input
  order and timestamps, assign local IDs, and treat an empty batch as an ID-neutral
  no-op. A trigger rejecting the second SQLite insertion proves full rollback,
  preservation of preexisting state, no sequence residue, and clean retry.
- Current combined result: `./scripts/check.sh` passed 80 tests, including atomic
  import, durable composition, and subprocess persistence work from other lanes.
  `git diff --check` also passed. The earlier isolated 16-test count described the
  pre-batch storage gate and is retained as historical handoff evidence.
- Commands run: `python3 -m unittest tests.test_sqlite_repository -v`;
  `./scripts/check.sh`; `git diff --check`.

## Recommended Trace Update

- Forward connection: repository structural contract -> isolated SQLite adapter
  -> SQLite database.
- Backward connection: reopened note -> SQLite row -> committed adapter transaction.
- Supported node-color change: isolated SQLite adapter and adapter-to-database
  arrow can move from red to green. Runtime selection and server-to-adapter arrow
  remain red because this assignment intentionally did not wire them.

## Handoff

Complete `agents/shared/HANDOFF_TEMPLATE.md` in the agent conversation when this assignment is ready for Agent 1 review.
