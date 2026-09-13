# Atomic Import Contract Tests

Status: prepared for Agent 1 review; not activated against shared production
files until the `NoteDraft` owner and `add_many` signature are approved.

## Validator Tests (`tests/test_importer_transaction.py`)

The file loader and API route must call the same public import-payload validator.
The validator returns `list[NoteDraft]` and performs no storage work.

1. A valid multi-note payload returns drafts in input order.
2. The draft contains trimmed `title` and `body`, canonical normalized tags, and
   canonical `created_at`, but no ID.
3. A supplied `createdAt` using `Z` remains the same instant in canonical UTC.
4. A supplied offset timestamp is converted to canonical UTC.
5. A missing `createdAt` is assigned by the application. Patch the application
   clock or timestamp helper so the assertion is deterministic.
6. Invalid, non-string, blank, date-only, and timezone-naive timestamps are
   rejected with an index-specific `ValueError`.
7. If any timestamp is invalid, the repository batch method is never called.
8. Source `id` and unknown fields do not appear in the draft.
9. An empty `notes` array validates to an empty draft list.

## Service Boundary Tests (`tests/test_service.py`)

1. `NoteService.import_notes(payload)` invokes the shared validator once.
2. It calls `repository.add_many(drafts)` exactly once for a non-empty batch.
3. It preserves the repository's returned note order.
4. It does not call storage after any validation error.
5. Its empty-batch behavior does not mutate storage.
6. Existing `create_note()` behavior and its repository `add()` call remain
   unchanged.

## Repository Contract Tests (`tests/test_sqlite_repository.py`)

Run the applicable behavioral cases against both memory and SQLite adapters.

1. A valid multi-note batch is stored and returned in input order.
2. IDs are assigned locally inside the batch and do not use source IDs.
3. Imported `created_at` values are stored exactly as the canonical draft value.
4. The returned note and tag values cannot mutate stored state.
5. An empty batch returns an empty list without changing IDs or stored records.
6. A deterministic failure during the second insertion attempt leaves the exact
   pre-batch snapshot unchanged.
7. Notes that existed before the failed batch remain unchanged.
8. After rollback, the repository remains usable.
9. Retrying the formerly failed batch succeeds without duplicate rows, leftover
   rows, or consumed local IDs from the failed attempt.
10. A concurrent single-note writer runs wholly before or after a batch. It does
    not interleave an ID between imported rows.

The SQLite failure test should use a trigger or equivalent deterministic adapter
failure that rejects the second batch item after the first insert statement has
run. The test must inspect state after the transaction exits, not merely assert
that an exception was raised.

## Route Tests (`tests/test_api.py`)

1. One `POST /api/import` request containing multiple valid notes calls one
   service batch operation.
2. A non-empty successful batch returns `201` and exactly
   `{ "imported": N, "notes": [...] }`.
3. An empty batch returns `200` and exactly
   `{ "imported": 0, "notes": [] }`.
4. Public notes use `createdAt`; no `created_at` or source ID leaks into the
   response.
5. Malformed JSON, a non-object body, or an invalid item returns the existing
   `400 invalid_request` envelope and causes zero mutation.
6. A storage exception is not converted into a success response. It reaches the
   server's existing generic `500 internal_error` boundary after the repository
   has rolled back.
7. Known-path wrong-method behavior includes `/api/import`.

## Command Contract For Agent 4 (`tests/test_import_tool.py`)

1. A file containing N notes causes exactly one HTTP request.
2. The request body is one `{ "notes": [...] }` payload and retains supplied
   `createdAt` fields for shared server-side validation.
3. The command prints success only after receiving a successful batch response.
4. API error detail and connection-error reporting remain useful.
5. Empty import accepts the route's `200` response and reports zero notes.

## Acceptance Evidence

The batch connection is not green until all of the following are true:

- Complete success is visible through the normal notes API in input order.
- Invalid input anywhere produces zero storage calls.
- A failure after the first insertion attempt produces zero new stored notes.
- Pre-existing notes remain byte-for-byte equivalent at the domain level.
- Retrying after rollback succeeds without residue.
- Successful durable imports survive repository close and reopen.
- The full project check passes after integration.
