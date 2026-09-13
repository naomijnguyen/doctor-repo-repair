# Agent 4: Runtime Composition And Portability Owner

## Assignment

Give the server, import command, and later export command one configured route to the same durable repository. This role connects accepted components; it does not define SQLite internals or batch business rules.

## Work Area

- Repository selection and data-path configuration.
- Server composition changes required to select SQLite.
- Import command migration after the batch contract is accepted.
- Portable atomic export after persistence and import are verified.
- Findings recorded in `NOTES.md`.

## Keep Outside This Assignment

- SQLite queries and schema.
- Import validation rules and transaction semantics.
- General HTTP hardening.
- Browser request behavior.
- Unrelated documentation cleanup.

## Starting Facts

- `fieldnotes/server.py` currently constructs `NoteRepository()` at import time.
- `FIELDNOTES_DATA` is the canonical data-path variable; `FIELD_NOTES_DATA` is a legacy fallback.
- The current default path is `./data/fieldnotes.json`, but no runtime component opens it.
- `tools/import_sample.py` currently reaches the server through one POST per note.
- There is no export implementation.

## Deliverable

One repository composition point used consistently by runtime entry points, followed by an atomic portable export after the persistence and import gates pass.

