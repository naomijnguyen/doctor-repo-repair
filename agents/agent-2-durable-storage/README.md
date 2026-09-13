# Agent 2: Durable Storage Owner

## Assignment

Implement and verify the missing durable repository adapter in isolation. The immediate result should be a SQLite-backed repository that can close, reopen, and return the same records without changing the running server yet.

## Work Area

- New SQLite repository module and schema.
- Repository conformance tests shared conceptually with the in-memory adapter.
- Transaction, reopen, ID, timestamp, and failure tests.
- Findings recorded in `NOTES.md`.

## Keep Outside This Assignment

- Server repository selection.
- API routes and HTTP behavior.
- Service rule cleanup.
- Import command wiring.
- Browser behavior.

## Starting Facts

- `fieldnotes/repository.py` contains a lock-protected in-memory `NoteRepository`.
- Its current operations are `list`, `add`, `delete`, and `clear`.
- `Note.create` assigns an integer ID and UTC timestamp.
- The target store is local SQLite using the Python standard library.
- Runtime data must not be committed.

## Deliverable

An isolated SQLite adapter, tests proving parity for current repository operations, and evidence that committed records survive close and reopen.

