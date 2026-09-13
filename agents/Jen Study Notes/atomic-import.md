# Atomic Import: Jen's Study Notes

> **Reading note:** This chapter preserves the repair as it unfolded, including
> early red-state descriptions. Atomic import is now implemented and verified.
> See [`README.md`](README.md) for the current status and recommended study order.

## The short version

The importer currently **checks the whole file safely, but it does not save the
whole file safely**.

Imagine importing three notes:

```text
Note A
Note B
Note C
```

The importer first checks all three notes for obvious problems. That part is
good. If Note C has no title, the importer rejects the file before saving
anything.

Once validation passes, however, it saves each note separately:

```text
save A -> success
save B -> success
save C -> database error
```

At that point, A and B are already saved. The user sees an import failure, but
part of the import exists in the database. That is the data-integrity problem we
want to fix.

## What "atomic import" means

An **atomic** batch is treated as one indivisible action:

```text
A + B + C -> all saved
```

or:

```text
A + B + C -> none saved
```

There is no halfway state.

A database transaction is like a protected workspace. SQLite can provisionally
insert all three notes and then make one final decision:

```text
BEGIN TRANSACTION
  insert A
  insert B
  insert C
COMMIT
```

If inserting C fails, SQLite can undo the provisional work:

```text
BEGIN TRANSACTION
  insert A
  insert B
  insert C -> error
ROLLBACK
```

The rollback removes the provisional insertions of A and B. The database returns
to exactly how it looked before the import began. Notes that existed before the
failed import are left alone.

## Why we need `add_many()`

The repository currently provides a single-note operation:

```python
repository.add(note)
```

Each SQLite `add()` opens and commits its own transaction. This loop therefore
does not make one batch transaction:

```python
for note in notes:
    repository.add(note)
```

It creates several independent transactions:

```text
transaction for A -> commit
transaction for B -> commit
transaction for C -> fail
```

By the time C fails, SQLite cannot roll back A and B because those transactions
have already finished.

The proposed repository operation is:

```python
repository.add_many(notes)
```

Its contract is stronger than "conveniently loop over these notes." It means:

> Either store every note in this collection or leave the repository unchanged.

For SQLite, `add_many()` uses one database transaction for the complete list.
For the in-memory repository, it builds the prospective result separately and
publishes it only after every note is ready.

## The lock and deadlock trap

Both repositories use a lock. The lock prevents two operations from modifying
the same repository state simultaneously.

It might seem reasonable to write this:

```python
with repository.transaction():
    for note in notes:
        repository.add(note)
```

The problem is that the transaction wrapper would acquire the repository lock.
Then `add()` would try to acquire the same lock again.

The current lock is **non-reentrant**. The same thread cannot acquire it twice.
The result would look like this:

```text
transaction owns lock
        |
        v
add() waits for lock
        |
        v
transaction cannot finish until add() finishes
```

The program freezes because each step is waiting for the other. This is called a
**deadlock**.

The safe design is for `add_many()` to hold the lock once and perform the batch
insertion directly. It should not call the public `add()` method internally.

## Timestamp handling

An imported note might contain:

```json
{
  "title": "Field observation",
  "createdAt": "2026-09-12T13:30:00-07:00"
}
```

That timestamp represents the same instant as:

```text
2026-09-12T20:30:00+00:00
```

The first spelling uses a local UTC offset. The second spelling uses UTC.

The proposed import policy is:

- If `createdAt` is missing, Field Notes assigns the current UTC time.
- If `createdAt` is supplied, it must include timezone information.
- Field Notes preserves the actual instant but writes it in a standard UTC form.
- An invalid or timezone-naive value rejects the whole import before storage is
  called.

Examples:

```text
Accepted:
2026-09-12T20:30:00Z
2026-09-12T13:30:00-07:00

Rejected:
2026-09-12T13:30:00
September 12 around lunch
null
```

The timestamp without an offset is rejected because its meaning is ambiguous.
It could mean 1:30 PM in Los Angeles, New York, London, or somewhere else.
Guessing would silently change the note's historical creation time.

Normal note creation remains different from import. A normal API client does not
choose `createdAt`; Field Notes assigns it. Import is allowed to preserve a valid
historical creation time because it is reconstructing an existing note.

## Why imported IDs are ignored

An export might contain:

```json
{
  "id": 42,
  "title": "Field observation"
}
```

The destination database may already have a different note numbered 42. Field
Notes therefore preserves the meaningful note data but lets the destination
database assign a new local ID:

```text
source ID:    42
new local ID: 107
```

The ID belongs to a particular database. It is not treated as a globally
portable identity.

## Why the API should receive one request

The command currently makes a separate HTTP request for every note:

```text
POST note A
POST note B
POST note C
```

Three separate requests cannot safely share one ordinary database transaction.
The proposed API sends the entire batch in one request:

```http
POST /api/import
```

```json
{
  "notes": [
    {"title": "A"},
    {"title": "B"},
    {"title": "C"}
  ]
}
```

That one request travels through one service operation and one repository
transaction.

Only after all notes are committed does the API report success. A non-empty
batch returns HTTP `201 Created`:

```json
{
  "imported": 3,
  "notes": []
}
```

The real `notes` array in the response will contain the three created public note
objects. If anything fails, the API returns an error and does not claim that the
batch was imported.

An empty batch is a successful no-op, but it creates nothing. It therefore
returns HTTP `200 OK` instead of `201 Created`:

```json
{
  "imported": 0,
  "notes": []
}
```

## Transaction safety versus retry safety

There is a deeper network edge case that a database transaction cannot solve by
itself.

Suppose the server successfully commits the notes, but the network connection
breaks before the response reaches the command:

```text
server commits import
        |
        v
response connection breaks
        |
        v
command thinks the request failed
```

The command cannot tell whether the server committed the import. If it blindly
retries, the notes could be duplicated.

Preventing that requires an **idempotency key**, which acts like a unique import
receipt:

```json
{
  "importKey": "a-unique-value-for-this-import",
  "notes": []
}
```

The database remembers the key as part of the transaction. If the same request
arrives again, the server returns the original result instead of creating the
notes again.

These are two related but different guarantees:

- A **transaction** prevents a partial database write.
- An **idempotency key** prevents duplicates after an uncertain network retry.

The transaction is the essential missing connection in the current repair.
Idempotency is worth documenting, but adding it immediately would require a
larger API and database-schema decision.

## The mental model to keep

The old import behavior is:

> Save a bunch of notes one at a time and hope every save works.

The target behavior is:

> Hand the database one sealed package. It either accepts the entire package or
> gives the whole package back.

That sealed-package behavior is what **atomic batch import** means.

## Annotated code: the reusable pattern and the Field Notes version

The examples below come in pairs:

- **General pattern** means the idea you could reuse in another application.
- **Field Notes excerpt** is a small excerpt from the implementation in this
  project.

The useful skill is learning to recognize the pattern even when the class names,
database, or API framework change.

## 1. Use a typed record at the boundary

### General pattern

```python
@dataclass(frozen=True)
class ValidatedItem:
    # Only cleaned, domain-level values belong here.
    name: str
    labels: tuple[str, ...]
    created_at: str
```

Why this helps:

- Raw JSON is flexible and untrusted.
- A typed record is narrow and predictable.
- `frozen=True` prevents accidental reassignment after validation.
- A tuple prevents callers from appending tags while storage is using them.
- There is no ID because the destination repository owns local identity.

This object is a **boundary object**: it marks the point where messy external
input becomes trusted internal data.

### Field Notes excerpt

From `fieldnotes/models.py`:

```python
@dataclass(frozen=True)
class NoteDraft:
    """A validated, storage-neutral note waiting for a local ID."""

    title: str
    body: str
    tags: tuple[str, ...]
    created_at: str
```

Important details:

```text
NoteDraft has no id
        |
        +--> source IDs cannot silently become local IDs

NoteDraft uses created_at
        |
        +--> the repository does not know the API name createdAt

NoteDraft is frozen
        |
        +--> validated values cannot be reassigned in transit
```

“Storage-neutral” means the same draft can go to the in-memory repository or the
SQLite repository. It contains no SQL, HTTP, or JSON-specific machinery.

## 2. Turn raw input into drafts before touching storage

### General pattern

```python
def validate_batch(payload) -> list[ValidatedItem]:
    validated = []

    for index, raw_item in enumerate(payload["items"]):
        # Check and clean every field.
        name = validate_name(raw_item.get("name"), index)
        labels = normalize_labels(raw_item.get("labels", []))
        created_at = normalize_timestamp(raw_item.get("createdAt"))

        validated.append(
            ValidatedItem(
                name=name,
                labels=labels,
                created_at=created_at,
            )
        )

    # Storage has not been called yet.
    return validated
```

The key is not merely that validation exists. The key is **when** it happens:

```text
validate item 1
validate item 2
validate item 3
finish complete batch validation
then call storage once
```

If item 3 is invalid, storage never sees items 1 or 2.

### Field Notes excerpt

From `fieldnotes/importer.py`:

```python
def validate_import_payload(payload: Any) -> list[NoteDraft]:
    if not isinstance(payload, dict):
        raise ImportValidationError("import file must contain a JSON object")

    notes = payload.get("notes")
    if not isinstance(notes, list):
        raise ImportValidationError("import file must contain a 'notes' list")

    validated = []
    for index, item in enumerate(notes):
        label = f"note at index {index}"

        # Field checks occur while we are still outside storage.
        title = item.get("title")
        body = item.get("body", "")
        tags = item.get("tags", [])

        # ...type and value checks...

        validated.append(
            NoteDraft(
                title=title.strip(),
                body=body.strip(),
                tags=cleaned_tags,
                created_at=created_at,
            )
        )

    return validated
```

The `index` becomes part of the error message. Instead of saying “something in
the import is wrong,” Field Notes can say “note at index 1 has a bad timestamp.”
That is much more useful to both users and tests.

## 3. Use a dedicated validation exception

### General pattern

```python
class PayloadValidationError(ValueError):
    pass


try:
    items = validate_batch(payload)
except PayloadValidationError as error:
    return client_error(400, str(error))

# Do not catch every ValueError around storage.
saved = repository.add_many(items)
```

Why create a special exception when `ValueError` already exists?

Because the **source of the error changes its meaning**:

```text
PayloadValidationError
    -> the caller supplied bad input
    -> HTTP 400

Repository error
    -> the server/storage failed
    -> HTTP 500
```

If the route catches every `ValueError`, a storage failure could be reported as
the user's fault. Precise exception types preserve honest error ownership.

### Field Notes excerpt

From `fieldnotes/importer.py`:

```python
class ImportValidationError(ValueError):
    """The import payload is invalid before repository mutation begins."""
```

From `fieldnotes/api.py`:

```python
try:
    notes = service.import_notes(payload)
except ImportValidationError as exc:
    return _error(400, "invalid_request", str(exc))
```

Notice what is absent:

```python
# This would be too broad around the service/storage call:
except ValueError:
    return bad_request()
```

A repository `ValueError` now escapes the route adapter. The server's existing
error boundary turns it into an internal error instead of falsely blaming the
request.

## 4. Canonicalize timestamps by instant, not spelling

### General pattern

```python
def canonical_utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PayloadValidationError("timestamp needs a timezone")

    return parsed.astimezone(timezone.utc).isoformat()
```

Two timestamp strings can describe the same instant:

```text
2026-09-12T13:30:00-07:00
2026-09-12T20:30:00+00:00
```

Canonicalization does not preserve the original spelling. It preserves the
meaning and writes that meaning in one standard form.

### Field Notes excerpt

From `fieldnotes/importer.py`:

```python
candidate = value.strip()
if candidate.endswith(("Z", "z")):
    candidate = f"{candidate[:-1]}+00:00"

parsed = datetime.fromisoformat(candidate)

if parsed.tzinfo is None or parsed.utcoffset() is None:
    raise ImportValidationError(
        f"{label} createdAt must include a timezone offset"
    )

return parsed.astimezone(timezone.utc).isoformat()
```

The two timezone checks are intentionally defensive. A `tzinfo` object can exist
yet still fail to provide a usable UTC offset, so checking `utcoffset()` protects
the actual conversion requirement.

## 5. Keep the service operation boring

### General pattern

```python
def import_items(self, payload):
    items = validate_batch(payload)

    if not items:
        return []

    return self.repository.add_many(items)
```

This is “boring” in the best sense. The service does three things:

1. Produce trusted drafts.
2. Handle the empty no-op.
3. Make exactly one storage call.

It does not open SQL transactions, assign database IDs, or invent compensating
deletes. Those are repository responsibilities.

### Field Notes excerpt

From `fieldnotes/service.py`:

```python
def import_notes(self, payload: Any):
    drafts = validate_import_payload(payload)
    if not drafts:
        return []
    return self.repository.add_many(drafts)
```

This tiny function is also an architectural map:

```text
untrusted payload
      |
      v
validated NoteDraft values
      |
      v
one repository batch operation
```

## 6. Stage in-memory state before publishing it

### General pattern

```python
def add_many(self, drafts):
    with self._lock:
        staged = build_all_items(drafts, starting_id=self._next_id)

        # Publication begins only after staging succeeded.
        self._items.extend(staged)
        self._next_id += len(staged)

        return copy_items(staged)
```

Holding a lock prevents interleaving. Staging prevents partial publication.
Those are related but separate properties:

```text
lock    -> another writer cannot interrupt the batch
staging -> this batch does not publish half of itself
```

### Field Notes excerpt

From `fieldnotes/repository.py`:

```python
def add_many(self, notes: list[NoteDraft]) -> list[Note]:
    with self._lock:
        staged = [
            Note(
                id=self._next_id + index,
                title=draft.title,
                body=draft.body,
                tags=list(draft.tags),
                created_at=draft.created_at,
            )
            for index, draft in enumerate(notes)
        ]

        self._notes.extend(staged)
        self._next_id += len(staged)
        return [self._copy(note) for note in staged]
```

The list comprehension finishes before `_notes` or `_next_id` is changed. If
constructing one of the notes raises, the repository's published state is still
unchanged.

IDs are calculated from `_next_id` while the lock is held. A concurrent normal
write can happen before or after this batch, but it cannot receive an ID between
two imported notes.

## 7. Use one real database transaction

### General pattern

```python
def add_many(self, drafts):
    with self._lock:
        try:
            connection.execute("BEGIN")

            created = []
            for draft in drafts:
                created.append(insert_directly(draft))

            connection.execute("COMMIT")
            return created
        except Exception:
            connection.execute("ROLLBACK")
            raise
```

The important word is **directly**. `insert_directly()` here represents internal
transaction-aware work. It must not secretly call a public method that starts and
commits its own transaction.

### Field Notes excerpt

From `fieldnotes/sqlite_repository.py`:

```python
def add_many(self, notes: list[NoteDraft]) -> list[Note]:
    with self._lock:
        created = []
        try:
            self._connection.execute("BEGIN IMMEDIATE")

            for draft in notes:
                cursor = self._connection.execute(
                    "INSERT INTO notes (title, body, tags, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        draft.title,
                        draft.body,
                        json.dumps(list(draft.tags), ensure_ascii=False),
                        draft.created_at,
                    ),
                )

                # Read the row back while it is still inside this transaction.
                row = self._connection.execute(
                    "SELECT id, title, body, tags, created_at "
                    "FROM notes WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
                created.append(self._note_from_row(row))

            self._connection.execute("COMMIT")
        except Exception:
            self._rollback()
            raise

        return created
```

Why `BEGIN IMMEDIATE`?

SQLite reserves the write transaction at the beginning instead of waiting until
the first write. For this local application, that makes the intended writer
boundary explicit: once the batch starts, another writer cannot slip into the
middle of its ID sequence.

Why catch `Exception` here?

At the repository boundary, any pre-commit failure must trigger rollback—SQL
errors, row-decoding errors, or unexpected internal errors. The exception is then
re-raised so the caller never mistakes rollback for success.

## 8. Map the result to honest HTTP semantics

### General pattern

```python
created = service.import_items(payload)

status = 201 if created else 200
return json_response(
    status,
    {
        "imported": len(created),
        "items": [serialize(item) for item in created],
    },
)
```

The response is based on the repository's actual committed result. The route does
not calculate success from the number of requested items.

### Field Notes excerpt

From `fieldnotes/api.py`:

```python
notes = service.import_notes(payload)
status = 201 if notes else 200

return _json(
    status,
    {
        "imported": len(notes),
        "notes": [_note_dict(note) for note in notes],
    },
)
```

The distinction is semantic:

```text
201 Created -> at least one note was created
200 OK      -> the empty import succeeded, but created nothing
```

## 9. Test the failure after work has actually begun

### Weak failure test

```python
payload = [valid_item, invalid_item]
validate(payload)  # fails before any insert
assert repository.list() == []
```

This is a useful validation test, but it does not prove database rollback.

### Strong rollback test pattern

```python
repository.add(existing_item)
inject_failure_on_second_batch_insert()

with assert_raises(StorageError):
    repository.add_many([first, second, third])

assert repository.list() == [existing_item]

remove_failure()
created = repository.add_many([first, second, third])
assert ids(created) == [2, 3, 4]
```

This proves much more:

- The first insertion was attempted.
- The second insertion failed.
- No imported row remained.
- Pre-existing state survived.
- The failed batch did not consume IDs.
- The repository remained usable.
- A clean retry did not encounter residue.

That combination is why the Field Notes trigger-based test is strong rollback
evidence rather than merely an exception test.

## A generalized architecture you can reuse

```text
External representation
JSON, CSV, message, form submission
            |
            v
Shared parser and validator
checks the whole unit of work
            |
            v
Immutable typed drafts
trusted values, no destination IDs
            |
            v
Application service
one call expressing business intent
            |
            v
Repository batch primitive
one lock and one transaction
            |
            v
Committed domain objects
local IDs and authoritative stored state
            |
            v
Honest response
success only after commit
```

You can reuse this shape for importing contacts, creating an order with several
line items, applying a configuration bundle, ingesting experiment observations,
or recording a group of related events. The nouns change. The safety boundaries
stay remarkably similar.
