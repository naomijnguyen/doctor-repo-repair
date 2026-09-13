# Agent 5 Technical Assignment

## Required Test Boundaries

### Repository reopen

- Write through the SQLite adapter.
- Close it completely.
- Open a new adapter instance against the same file.
- Compare IDs, values, tags, and timestamps.

### Server restart

- Start a real server process with a temporary configured database.
- Create through HTTP.
- Stop the process.
- Start a new process against the same database.
- Retrieve through HTTP.

### Import visibility and rollback

- Submit a valid multi-note import through its real entry point.
- Retrieve the records through the normal API.
- Inject a failure after at least one insertion attempt.
- Confirm zero notes from the failed batch remain.

### Export recovery

- Export a populated database.
- Import into a separate empty database.
- Compare meaningful fields while allowing locally assigned IDs when required by policy.
- Interrupt or force a write failure and confirm no complete-looking output replaces the prior file.

## Suggested Owned Files

- `tests/test_persistence_integration.py`.
- `tests/test_http_persistence.py`.
- `tests/test_import_connection.py`.
- `tests/test_roundtrip.py`.
- Agent-specific helpers under `tests/support/` if needed.

## Reporting Standard

Record exact commands, process boundaries, temporary paths, observed outputs, and whether a result proves a component or an actual connection. Do not treat a skipped test as passing evidence.

