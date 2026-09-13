# Agent 3: Atomic Import Owner

## Assignment

Define and implement the missing all-or-nothing import connection. The current importer validates the full file, but the command sends one API request per note. A later failure can therefore leave an incomplete imported batch.

## Work Area

- Import payload and timestamp policy.
- One batch-level service operation.
- One batch API contract and focused tests.
- Rollback behavior when validation or storage fails.
- Findings recorded in `NOTES.md`.

## Keep Outside This Assignment

- SQLite schema and query implementation.
- Runtime repository selection.
- Export command implementation.
- Browser behavior.
- Unrelated service or HTTP cleanup.

## Starting Facts

- `fieldnotes/importer.py` validates every input record before calling `repository.add` in a loop.
- `tools/import_sample.py` now uses an API-backed repository-shaped adapter.
- The command reaches the running server, but one POST is made for each note.
- Imported source IDs are ignored and local IDs are assigned.
- Current imports assign fresh timestamps rather than preserving supplied `createdAt`.

## Deliverable

A reviewed batch-import contract, an implementation that can use one repository transaction, and tests proving both complete success and complete rollback.

