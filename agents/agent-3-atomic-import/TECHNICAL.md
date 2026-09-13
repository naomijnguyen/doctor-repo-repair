# Agent 3 Technical Assignment

## Input Contract

- UTF-8 JSON object with a top-level `notes` array.
- Every item requires a nonblank string `title`.
- `body` defaults to an empty string and must otherwise be a string.
- `tags` defaults to an empty list and must contain strings.
- Tags use the canonical normalizer.
- Source IDs are not trusted or restored.
- A valid `createdAt` should be preserved under the current preferred policy.
- One invalid record rejects the entire batch before storage mutation.

## Required Failure Semantics

- Validation failure: zero records committed.
- Storage failure before commit: zero records committed.
- Storage failure during insertion: transaction rolled back to zero new records.
- Response or tool output must not claim full success for partial work.
- Retrying a failed, rolled-back batch must not encounter residue from the first attempt.

## Suggested Owned Files

- `fieldnotes/importer.py`.
- A narrowly scoped batch operation in `fieldnotes/service.py`.
- A narrowly scoped batch route in `fieldnotes/api.py`.
- `tests/test_importer_transaction.py` and focused route tests.

## Questions To Resolve In Notes

- Exact batch request and response shape.
- Timestamp parsing and canonical UTC serialization.
- Whether empty batches succeed with count zero or fail validation.
- Maximum batch size at the application boundary.
- How the service requests a transaction without depending on SQLite details.

Do not activate the path until Agent 2's transaction contract has passed isolated tests and Agent 1 has accepted the shared interface.

