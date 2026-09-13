# Agent 4 Technical Assignment

## Configuration Contract

- One canonical environment variable for the database path.
- A documented legacy alias only if existing compatibility requires it.
- A SQLite-appropriate default filename.
- Parent-directory creation or a clear startup failure policy.
- Runtime database, journal, and temporary files excluded from Git.
- Repository creation occurs in one explicit composition function.

## Server Connection Evidence

- Start with an empty configured database.
- Create through the real HTTP transport.
- Stop the server cleanly.
- Start a fresh server process against the same path.
- Retrieve the same note and stable ID.
- Point to an unusable path and verify visible startup failure.

## Import Command Migration

After Agent 3's batch contract is accepted, update `tools/import_sample.py` to use one batch operation rather than a repository-shaped per-note HTTP adapter. Preserve useful API error details.

## Export Contract

- Read from the same authoritative repository.
- Serialize public field names, including `createdAt`.
- Write UTF-8 JSON through a temporary sibling file.
- Atomically replace the destination only after a successful complete write.
- Never include unrelated machine or application data.

## Suggested Owned Files

- `fieldnotes/config.py`.
- A new repository factory/composition module.
- Composition-only changes in `fieldnotes/server.py`.
- `tools/import_sample.py` after the batch gate.
- New exporter and export command files.
- Focused configuration, restart, and export tests that do not overlap Agent 5's black-box files.

