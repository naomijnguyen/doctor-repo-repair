# Agent 2 Technical Assignment

## Repository Behavior To Preserve

- `list() -> list[Note]`
- `add(title, body, tags) -> Note`
- `delete(note_id) -> bool`
- `clear() -> None`
- Returned notes and tag lists cannot mutate stored records.

## Required SQLite Evidence

- New database initialization.
- Sequential unique local IDs.
- UTC creation timestamps retained after reopen.
- Committed create survives close and reopen.
- Committed delete survives close and reopen.
- Failed write rolls back.
- Concurrent operations do not duplicate IDs or corrupt records.
- An unreadable or invalid database fails visibly rather than being replaced.

## Suggested Owned Files

- `fieldnotes/sqlite_repository.py` or another new storage-specific module.
- `tests/test_sqlite_repository.py`.
- New repository conformance-test helpers if they do not require edits to another agent's production files.

## Contract Questions To Record

- Does a lightweight structural contract suffice, or is a formal protocol necessary?
- How are tags represented without leaking SQL details into the service?
- Where is schema version recorded?
- Which SQLite transaction mode protects the intended local concurrency pattern?

