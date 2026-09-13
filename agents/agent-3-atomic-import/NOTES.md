# Agent 3 Notes

## Observations

- The live tree is ahead of the 34-test packet snapshot: `./scripts/check.sh`
  currently passes 47 tests, including the completed isolated SQLite adapter
  and its compatible/incompatible unversioned-schema acceptance tests. SQLite is
  not wired into the server yet.
- `fieldnotes/importer.py` validates the complete input before storage, but then
  calls `repository.add(...)` once per note. This protects against malformed
  record 2, not against a storage failure while inserting record 2.
- At the initial observation point, `tools/import_sample.py` turned those calls
  into one HTTP request per note, so a later request failure could leave earlier
  requests committed. Agent 4 has since replaced that adapter with one complete
  `POST /api/import` request.
- Both repositories use a non-reentrant `Lock`, and SQLite `add()` begins and
  commits its own transaction. A transaction callback that acquires the lock and
  then calls public `add()` would deadlock; an outer SQLite transaction around
  repeated `add()` calls would not be atomic.
- The current validator drops `createdAt`, and both repository `add()` methods
  generate a fresh timestamp. The intended portable format prefers preserving a
  valid imported creation instant.
- The existing importer failure test proves zero mutation on validation failure.
  There is no test that fails after the first row has been inserted.

## Proposed Batch Contract

- Request shape: `POST /api/import` with `{ "notes": [...] }`. Each item requires
  a nonblank string `title`; `body` defaults to `""`; `tags` defaults to `[]`;
  and `createdAt` is optional. Source `id` and unknown fields are ignored. The
  importer and route use the same validator; the API does not trust client-side
  file validation.
- Response shape: after a non-empty complete commit, return `201` with
  `{ "imported": N, "notes": [...] }`, where notes use the normal public note
  shape. For an empty batch, return `200` with
  `{ "imported": 0, "notes": [] }`. Validation returns the existing
  `400 invalid_request` envelope. Storage exceptions escape the route adapter for
  the server's generic `500 internal_error`; a failed transaction never returns
  a success count.
- Timestamp policy: absent `createdAt` receives an application-assigned UTC time.
  A supplied value must be a nonblank ISO 8601 string with `Z` or an explicit
  numeric offset. Parse it as an aware datetime, preserve its instant, convert it
  to UTC, and serialize it canonically with `+00:00`. Reject invalid, date-only,
  and timezone-naive values before calling storage. Normal `POST /api/notes`
  remains server-timestamped and does not gain a client timestamp field.
- Empty-batch policy: accept it as an atomic no-op and return
  `200 { "imported": 0, "notes": [] }`. Use `201` only when at least one note is
  created.
- Maximum-size policy: do not invent a record-count cap in this change. The HTTP
  server already rejects request bodies over 1,000,000 bytes before routing.
- Internal record: propose a shared, storage-neutral model in `fieldnotes.models`:

  ```python
  @dataclass(frozen=True)
  class NoteDraft:
      title: str
      body: str
      tags: tuple[str, ...]
      created_at: str
  ```

  `NoteDraft` contains only validated domain values. It contains no ID and knows
  nothing about the API field name `createdAt`. Using an immutable tuple prevents
  callers from mutating tags while a batch is being handed to storage. The exact
  class name and owning shared module remain subject to Agent 1 and Agent 2
  approval.
- Repository operation: exact proposed structural signature:
  `add_many(notes: list[NoteDraft]) -> list[Note]`. Output order matches input;
  IDs are assigned locally inside the repository transaction; an exception means
  none of that batch was published. A sequence-oriented annotation could later
  broaden the accepted input, but the initial cross-adapter contract should stay
  exact and testable.
  The memory adapter stages notes and next-ID before publishing under one lock.
  SQLite performs all direct inserts under one lock and one `BEGIN IMMEDIATE`,
  rolling back on any pre-commit exception. Neither implementation loops through
  public `add()`.

### API Examples

Non-empty request:

```json
{
  "notes": [
    {
      "id": 9001,
      "title": "Field observation",
      "body": "Collected near the north trail.",
      "tags": ["Field Work"],
      "createdAt": "2026-09-12T13:30:00-07:00"
    },
    {
      "title": "Follow-up",
      "tags": []
    }
  ]
}
```

Successful non-empty response (`201`):

```json
{
  "imported": 2,
  "notes": [
    {
      "id": 12,
      "title": "Field observation",
      "body": "Collected near the north trail.",
      "tags": ["field-work"],
      "createdAt": "2026-09-12T20:30:00+00:00"
    },
    {
      "id": 13,
      "title": "Follow-up",
      "body": "",
      "tags": [],
      "createdAt": "2026-09-12T20:31:00+00:00"
    }
  ]
}
```

The source ID `9001` is ignored; IDs `12` and `13` are assigned locally inside
the repository transaction. The second timestamp is illustrative: the
application supplies the actual current UTC time before storage begins.

Empty request:

```json
{"notes": []}
```

Successful empty response (`200`):

```json
{"imported": 0, "notes": []}
```

## Gotchas And Dependencies

- Agent 2's isolated SQLite adapter and schema-acceptance work are complete. The
  next shared storage extension is the accepted dedicated batch primitive:
  `add_many(notes: list[NoteDraft]) -> list[Note]` in both adapters. Repeated
  calls to existing `add()` cannot satisfy this contract because each SQLite
  `add()` owns its own `BEGIN IMMEDIATE` and commit.
- Agent 2's implementation must assign every ID inside the protected batch,
  preserve input order in its return value, make the batch contiguous with
  respect to concurrent writes, and roll back every row and ID-sequence effect
  after a failed insertion.
- Agent 1 must accept the shared method and HTTP shapes before the path is
  activated; the coordination packet explicitly reserves that decision.
- Agent 4 replaced the repository-shaped per-note HTTP adapter with one
  request containing the complete payload, while retaining useful API and
  connection error messages. This is now implemented and covered by seven
  focused command tests in the live tree.
- Existing `add(title, body, tags)` remains unchanged for normal creation.
- Tags should continue using the canonical normalizer. Stable duplicate removal
  is promised in `README_INTENT.md` but is not implemented by either current
  entry path. Duplicate-tag cleanup is explicitly outside this assignment.
- General HTTP security, browser behavior, and unrelated amber cleanup are also
  outside this assignment.

## Evidence

- Validation failure test: `test_invalid_timestamp_anywhere_rejects_entire_payload`,
  `test_invalid_import_never_calls_storage`, and
  `test_import_invalid_timestamp_causes_zero_mutation` prove an invalid timestamp
  at index 1 rejects the complete batch before storage mutation.
- Transaction failure test:
  `test_failed_batch_rolls_back_preserves_existing_and_retries_cleanly` uses a
  SQLite trigger to reject the second insertion after the first insert statement
  ran. The prior note remains unchanged, no batch row remains, the repository is
  usable, and retry produces IDs 2, 3, and 4 with no residue.
- Successful batch test:
  `test_add_many_preserves_order_assigns_local_ids_and_timestamps` runs against
  both repository adapters. Route and validator tests prove source IDs are
  ignored, order is retained, offset timestamps become UTC, missing timestamps
  are application-assigned, and empty import returns HTTP 200.
- Prepared test contract: `agents/agent-3-atomic-import/CONTRACT_TESTS.md` records
  the focused red-phase cases and their ownership without activating imports of
  a not-yet-approved shared type.
- Full-suite result: `./scripts/check.sh` passed 89 tests on 2026-09-12 after the
  Agent 3 implementation and hold regressions, Agent 4's one-request command and
  startup-order repair, and Agent 5's public import-connection tests.

## Recommended Trace Update

- Forward connection: file -> complete validation -> one batch HTTP request ->
  one service operation -> one repository transaction -> all rows committed.
- Backward connection: imported API-visible note -> committed batch response ->
  service batch call -> repository transaction -> authoritative state.
- Supported node-color change: the typed validator, service batch operation,
  route, repository atomic operation, and command-to-batch-route arrow can move
  from red to green based on focused success, rollback, and one-request command
  evidence. Agent 5 now supplies durable post-import restart and public failure
  evidence, so the complete end-to-end trace is ready for Agent 1 acceptance.

## Handoff

### Agent And Scope

- Agent: Agent 3, Atomic Import Owner.
- Assigned connection: validated import payload to one atomic repository batch.
- Files owned or shared by accepted contract: `fieldnotes/importer.py`,
  `fieldnotes/service.py`, `fieldnotes/api.py`, `fieldnotes/models.py`, both
  repository adapters, and focused tests.
- Subagents used: timestamp-contract reviewer, rollback-path reviewer, and test
  inventory reviewer; all remained read-only.

### Observed Before

- Entry point: file import tool.
- Call path: file validator -> per-note adapter call -> per-note HTTP request ->
  service create -> separately committed repository add.
- State owner: the runtime repository.
- Failure boundary: malformed data caused zero writes, but a failure during note N
  left notes 1 through N-1 committed.

### Work Completed

- Added immutable, storage-neutral `NoteDraft` without an ID.
- Added one shared payload validator with canonical timezone-aware UTC handling.
- Added `NoteService.import_notes`, `POST /api/import`, and the accepted 200/201
  response distinction.
- Added atomic `add_many` implementations for memory and SQLite without calling
  public `add()`.
- Added focused validator, service, route, repository success, and rollback tests.
- Contract assumptions: Agent 4 owns the remaining command rewrite; source IDs
  remain ignored; unrelated tag, browser, and HTTP cleanup remains deferred.

### Findings For Other Agents

- Agent 4 now sends one complete payload to `/api/import`; its focused tests prove
  one request, original field preservation, empty success, and honest errors.
- Agent 5 now exercises the route against the durable runtime, including the real
  command, restart visibility, invalid-later-input rejection, and deterministic
  mid-batch storage failure with clean retry.
- Runtime composition, public persistence, and atomic import connection tests are
  green in the 89-test full-suite run.

### Remaining Unknowns

- A connection loss after commit but before the response remains an ambiguous
  retry and can duplicate a batch. True retry safety would require an idempotency
  key and is outside this rollback contract.
- No Agent 3 acceptance evidence remains outstanding. Agent 1 should reconcile
  the 89-test state and redraw the atomic-import path as green.
