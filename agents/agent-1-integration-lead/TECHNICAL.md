# Agent 1 Technical Notes

## Contract Checklist

- `list`, `add`, `delete`, and `clear` have equivalent observable behavior across repository adapters.
- A successful durable write is committed before success is reported.
- Server and portable tools resolve one configured database path.
- Batch import either commits every validated note or commits none.
- Imported IDs are locally assigned.
- Valid imported timestamps follow the accepted preservation policy.
- Runtime database files remain untracked.

## Acceptance Sequence

1. Run isolated SQLite conformance and reopen tests.
2. Connect the server through one composition point.
3. Create through HTTP, restart, and retrieve through HTTP.
4. Connect one-request batch import.
5. Inject a middle-of-batch failure and confirm rollback.
6. Import successfully, restart, and retrieve through the normal API.
7. Add export and prove export-to-import round trip.
8. Run `./scripts/check.sh` and `git diff --check` after each gate.

## Current Evidence

- The current suite passes 34 tests.
- The import command reaches the running API.
- Restarting the current server erases all notes.

