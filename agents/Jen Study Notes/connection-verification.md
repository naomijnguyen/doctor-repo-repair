# Connection Verification: Jen's Study Notes

> **Reading note:** This chapter preserves multiple verification checkpoints.
> The complete import path now has public CLI, HTTP, rollback, and restart proof.
> See [`README.md`](README.md) for the current status and recommended study order.

## The short version

Agent 5 asks a deceptively simple question:

> Does this arrow in the architecture diagram actually work?

A component can pass every unit test and still be disconnected from the user.
For example, a SQLite repository might correctly save and reopen notes when a
test calls it directly. That does not prove the running HTTP server uses that
repository. The server could still be constructing the old in-memory one.

That difference is the heart of connection verification:

```text
Component proof:
SQLiteRepository -> writes and reopens correctly

Connection proof:
Browser or import command
    -> HTTP server
    -> API
    -> service
    -> SQLiteRepository
    -> database file
    -> new server process
    -> same notes are visible
```

The first proof says a part works. The second says the product reaches that part.

## The real baseline experiment

We started with a live process instead of calling Python classes directly.

First, Agent 5 started the actual server on an isolated port:

```text
python3 -m fieldnotes.server
```

For this experiment the port was `8876`, so it would not interfere with another
developer or agent using the normal port.

Then we ran the real import command against that server:

```text
python3 tools/import_sample.py data/sample.json \
  --api-url http://127.0.0.1:8876
```

The command reported two imported notes. A real HTTP request to the normal list
endpoint returned both of them:

```json
{
  "notes": [
    {
      "id": 1,
      "title": "Model routing",
      "tags": ["llm-systems", "routing"]
    },
    {
      "id": 2,
      "title": "Memory",
      "tags": ["context-memory"]
    }
  ]
}
```

That proves this complete connection:

```text
sample JSON
    -> import command
    -> HTTP POST
    -> running API
    -> live repository
    -> HTTP GET
    -> observable notes
```

This is useful positive evidence. The importer is no longer writing into a
private repository that disappears as soon as the command exits. It reaches the
same live state the browser reads.

Next, we stopped the server completely and started a genuinely new process. A
new list request returned:

```json
{"notes": []}
```

That result proves the next missing connection:

```text
running repository -> process ends -> state is gone
```

The importer is connected. Durability is not.

## Why a new process matters

It would be tempting to test persistence like this:

```python
repository = SQLiteRepository(path)
repository.add(...)
repository = SQLiteRepository(path)
assert repository.list()
```

That test may accidentally keep the first connection alive. It also does not
prove that normal shutdown closes or commits the real application connection.

A stronger repository-level test is:

```text
open adapter A
write a note
close adapter A completely
open adapter B using the same path
read the note
```

An even stronger product-level test crosses the server boundary:

```text
start server process A with a temporary database
create a note through HTTP
stop and wait for process A to exit
start server process B with the same database
retrieve the note through HTTP
```

Process B cannot be benefiting from Python objects left in process A's memory.
If it returns the note, the durable connection is real.

## The evidence ladder

Persistence is not one giant yes-or-no claim. We prove it one connection at a
time.

### Level 1: adapter evidence

Agent 2 proves the isolated SQLite adapter:

```text
SQLite adapter -> database file -> close -> reopen -> same records
```

This should cover:

- new database initialization;
- IDs and timestamps surviving reopen;
- deletion surviving reopen;
- failed writes rolling back;
- concurrent operations not duplicating IDs; and
- an invalid database failing visibly instead of being silently replaced.

This is necessary, but it does not prove the server selected the adapter.

### Level 2: composition evidence

The runtime composition work connects configuration to storage:

```text
FIELDNOTES_DATA
    -> server startup
    -> SQLite repository construction
    -> selected database file
```

Agent 5 then repeats the test through real HTTP and a real process restart.

This catches a classic integration failure: a perfect SQLite adapter sitting in
the repository while `server.py` continues to construct `NoteRepository()` in
memory.

### Level 3: import evidence

Agent 3 connects the entire import batch to one repository transaction:

```text
one import request
    -> validation
    -> one service operation
    -> one database transaction
    -> commit everything or roll back everything
```

Agent 5 checks the result through the ordinary list API rather than reaching
into the database with test-only SQL. That proves the user-visible application
can see the imported state.

### Level 4: recovery evidence

Export and import form a recovery loop:

```text
database A
    -> export JSON
    -> database B
    -> import
    -> equivalent notes
```

This is stronger than checking that an export file merely exists. We prove the
file contains enough meaningful information to reconstruct the notes.

## Success tests need failure partners

A happy-path test tells us traffic can cross a connection. A controlled failure
tells us where the connection stops and what it leaves behind.

For every important arrow, Agent 5 wants a pair:

| Connection | Expected success | Controlled failure |
| --- | --- | --- |
| SQLite adapter -> file | Note survives reopen | Failed write leaves prior state intact |
| Server -> SQLite | HTTP note survives restart | Unusable path causes visible startup failure |
| Import -> transaction | Entire batch becomes visible | Mid-batch failure leaves the database unchanged |
| Export -> file | Valid portable JSON is produced | Interrupted write preserves the previous valid file |

The failure side is often where a design reveals its real contract.

## The useful oversized-note experiment

The current importer sends one HTTP request per note. That gives us a concrete
way to expose partial success.

Imagine an import containing two structurally valid notes:

```text
Note A: ordinary size
Note B: body larger than the API's one-megabyte request limit
```

With the current connection:

```text
POST A -> 201 Created
POST B -> 413 Request Too Large
```

Note A has already been committed by the time Note B fails. The command reports
failure, but the repository contains part of the batch.

After atomic import is implemented, the same conceptual test should behave
like this:

```text
POST complete batch -> failure
database after request == database before request
```

There is an important nuance: if the server rejects the request before any
insertion begins, we have proved input rejection, not database rollback.

To prove a transaction really rolls back, the test must trigger a controlled
failure after at least one insertion attempt. That may require a narrow test
seam, such as a repository wrapper that raises on the second insert. The seam
should make the failure deterministic without corrupting a real database.

## "No new notes" is not always the right assertion

Suppose the database already contains Jennifer's note before an import fails.
The correct rollback assertion is not:

```text
database is empty
```

It is:

```text
database after failed import == database before failed import
```

Preexisting notes must survive. Only the uncommitted batch should disappear.

A good Agent 5 test therefore takes a snapshot first:

```text
before = existing records
attempt failing batch
after = existing records
assert after == before
```

This is a small testing choice with a large data-safety meaning.

## Transaction safety is not the same as retry safety

The atomic-import study note explains this in more depth, but Agent 5 must keep
the distinction visible.

A transaction answers:

> Did a failed operation leave half the batch in the database?

Retry safety answers:

> If the server committed successfully but the response was lost, will retrying
> create duplicates?

The first guarantee requires a transaction. The second may eventually require
an idempotency key. We should not claim retry safety merely because rollback
tests pass.

## SQLite creates more than one possible file

Runtime-data hygiene is part of connection verification because a successful
database connection produces artifacts on disk.

Depending on SQLite's journal mode and what the process is doing, the working
set may include:

```text
fieldnotes.db
fieldnotes.db-journal
fieldnotes.db-wal
fieldnotes.db-shm
```

The current ignore rules cover JSON files under `data/`, but Agent 5 verified
that these prospective SQLite paths are not ignored:

```text
data/fieldnotes.db
data/fieldnotes.sqlite
data/fieldnotes.db-wal
data/fieldnotes.db-shm
data/fieldnotes.db-journal
```

None is tracked now, which is good. The problem is preventive: once runtime
composition creates a real database, `git status` could offer private research
data or SQLite sidecar files for staging.

A hygiene test should check the configured database path and its known SQLite
siblings explicitly. Simply checking that `data/` "looks ignored" can be
misleading because one matching JSON rule does not protect database files.

## A safe process test harness

Black-box tests involve real child processes, which means the harness itself
needs manners.

The planned harness will:

1. Create a private temporary directory.
2. Select an isolated local port.
3. Set `FIELDNOTES_PORT` and `FIELDNOTES_DATA` explicitly.
4. Start the server with captured stdout and stderr.
5. Poll the list endpoint with a short deadline until the server is ready.
6. Perform the real HTTP or command-line operation.
7. Terminate the exact child process it started.
8. Wait for that process to exit, killing it only after a bounded timeout.
9. Start a genuinely new process for restart verification.
10. Preserve logs in the test failure message and let the temporary directory
    clean up afterward.

One subtlety is port allocation. Asking the operating system for a free port and
then releasing it before the child binds introduces a tiny race: another process
could claim it in between. If runtime composition eventually allows the server
to bind port zero and report its chosen address, that is cleaner. Until then,
the harness should use bounded readiness checks and report clear child logs.

## Why Agent 5 waits instead of faking progress

Some verification gates do not exist yet:

- There is no SQLite adapter to reopen.
- The server does not yet select a repository from `FIELDNOTES_DATA`.
- There is no one-request transactional import route.
- There is no exporter to recover from.

Agent 5 could write skipped tests or tests that call imaginary interfaces, but
neither would be evidence. A skipped test is not a passing connection, and a
mocked connection is not a process boundary.

The honest sequence is:

```text
Agent 2 supplies isolated SQLite evidence
    -> Agent 1 accepts the repository contract
    -> runtime composition connects the server
    -> Agent 5 proves restart persistence
    -> Agent 3 connects atomic import
    -> Agent 5 proves rollback and post-restart visibility
    -> export is connected
    -> Agent 5 proves recovery and hygiene
```

That waiting is not inactivity. Agent 5 prepares the experiments, identifies
the required observability and failure seams, and makes sure nobody mistakes a
component test for a completed architecture connection.

## Interesting findings so far

### The import repair was real

The command now reaches the same live repository as the browser/API. The
black-box experiment proved it rather than inferring it from code.

### The next failure moved downward

Once import visibility worked, restart loss became the next exposed boundary.
That is a healthy repair pattern: fix one missing arrow, then observe where the
data stops next.

### Configuration can exist without being connected

`FIELDNOTES_DATA` has parsing code and tests, but the server does not use it to
construct storage. A tested configuration helper is not the same as a working
configuration path.

### Mocked HTTP tests prove a different thing

The import-tool unit test proves that the command constructs the correct POST.
It does not prove a real server accepts it or that the resulting note becomes
visible. Both tests are valuable; they answer different questions.

### Closing is part of persistence

Agent 2's adapter needs an explicit close or context-manager lifecycle. Reopen
evidence is weaker if the old connection remains alive or has not finished its
commit and cleanup behavior.

## The mental model to keep

Think of an architecture diagram as a subway map.

A unit test can prove that one station is beautifully built. Connection
verification boards the train, crosses the tunnel, gets off at the next
station, and checks that the luggage arrived too.

For Field Notes, the "luggage" is the user's data. Agent 5 follows it from the
entry point to the state owner, across failures, across process restarts, and
through recovery. The job is complete only when the note arrives intact and the
system tells the truth when it cannot.

## Field update: the SQLite adapter has arrived

Agent 2 has now completed the isolated `SQLiteNoteRepository`. The full check
passes 47 tests on Python 3.12.

This moves one part of the architecture from missing to verified:

```text
repository contract
    -> SQLite adapter
    -> SQLite database
    -> close
    -> reopen
    -> same note
```

The adapter has an explicit `close()` method and can be used as a context
manager. That is important because reopening is only convincing after the first
connection has really released the database.

Its initialization behavior is careful too. A brand-new database gets the
schema safely. An unversioned database with the exact compatible table can be
adopted. An incompatible table, corrupt database, or unsupported schema version
raises visibly rather than being overwritten.

But the application is not durable yet:

```text
server.py -> in-memory NoteRepository

server.py -X-> SQLiteNoteRepository
```

The `-X->` is the missing runtime connection. The server still constructs its
old process-memory repository and does not use the configured data path. Agent
5 therefore records the adapter as verified while refusing to call the public
application persistent.

The next experiment becomes available only after runtime composition wires that
arrow:

```text
HTTP create
    -> committed SQLite row
    -> full process stop
    -> new server process with the same database
    -> HTTP list returns the same ID and timestamp
    -> HTTP delete
    -> another restart
    -> note remains absent
```

Agent 2 also proved concurrency under a deliberately narrow condition: eight
threads shared one repository object and its one SQLite connection. The
repository's lock serialized their work and the IDs remained unique. That does
not prove every multi-process SQLite workload is safe, and Agent 5 will not
inflate the claim beyond the experiment.

Finally, each public `add()` currently begins and commits its own transaction.
That is correct for single-note creation but cannot make a batch atomic. Agent
3 needs a dedicated `add_many()` operation that acquires the non-reentrant lock
once and performs the complete batch in one transaction. Opening a transaction
and calling public `add()` from inside it would try to acquire the same lock
again and could deadlock.

This is our clearest connection-verification lesson so far:

> A green component does not automatically turn every arrow leading to it
> green. Each connection earns its own evidence.

## Field update: the public durability arrow is green

Agent 4 connected the server to the configured SQLite repository, and Agent 5
then ran the experiment we had been waiting for.

The test used three different server processes:

```text
Process A
    HTTP create -> note ID 1 and its createdAt timestamp
    stop completely

Process B, same database path
    HTTP list -> exact same note, ID, and timestamp
    HTTP delete -> 204
    stop completely

Process C, same database path
    HTTP list -> note is still absent
```

That is stronger than Agent 2's adapter reopen test. It proves the entire public
chain now reaches durable state:

```text
HTTP request
    -> composed service
    -> SQLite repository
    -> committed database row
    -> new Python process
    -> HTTP response
```

The failure side passed too. A corrupt configured database and an incompatible
existing schema both caused the server process to exit before it began
listening. The original files remained unchanged. This tells us the application
does not hide a storage problem by quietly starting with an empty in-memory
repository.

Three sneakier database cases were also checked through the public startup path:

- an unversioned database belonging to some unrelated application;
- a database marked version 1 but missing the required `notes` table; and
- an unversioned, structurally compatible table containing unreadable tag JSON.

All three failed before listening and remained unchanged. The important idea is
that a database can be valid SQLite while still being invalid *for Field Notes*.
"The file opens" is therefore not enough startup validation.

At this durable-runtime checkpoint, the combined suite passed 59 tests on Python
3.12. That count included three new Agent 5 subprocess tests, not just calls to
application classes inside the test runner. Later sections continue the timeline
through atomic import and the current 89-test suite.

The architecture trace has moved again:

```text
Import reaches live state             green
SQLite adapter reaches disk           green
Server reaches configured SQLite      green
Create and delete survive restart     green
Atomic batch import                   next red boundary
Export and recovery                   later red boundary
```

One small runtime-composition edge remains: the server opens the repository
before it parses the configured port, while port parsing sits outside the
cleanup block. An invalid port can therefore raise after the database connection
opens without explicitly closing it. That is a lifecycle-cleanup defect, not a
failure of the verified durability path.

Git hygiene is green for the documented default family under `data/`:

```text
*.sqlite3
*.sqlite3-journal
*.sqlite3-wal
*.sqlite3-shm
```

The claim is intentionally narrow. A user-configured `.db` filename or a path
elsewhere inside the repository is not automatically protected by those ignore
rules.

This is what it looks like when connection verification advances the map: we
did not merely announce that SQLite had been wired. We followed one note all the
way through the application, killed the process that created it, and made a new
process bring the same note back.

## Field update: atomic import crossed the public boundary

The atomic-import pieces are now connected, so Agent 5 repeated the same style
of experiment through the real command and server—not just through repository
tests.

The successful path looked like this:

```text
JSON file with two notes
    -> real import command
    -> one POST /api/import
    -> validate the complete payload
    -> one service import operation
    -> one repository.add_many call
    -> one BEGIN IMMEDIATE transaction
    -> commit both notes
    -> restart server
    -> both notes still visible
```

The details survived too. Source IDs were ignored and the database assigned
local IDs 1 and 2. A historical timestamp written as
`2026-09-12T13:30:00-07:00` came back as
`2026-09-12T20:30:00+00:00`: a different spelling of the same instant. A note
without a timestamp received a new UTC timestamp from the application.

Then we tested the failure path. The database already contained one note. Agent
5 installed a controlled SQLite trigger that would reject the second imported
title:

```text
existing note: ID 1

batch begins
    insert proposed ID 2 -> succeeds provisionally
    insert proposed ID 3 -> trigger raises
    rollback transaction

public list after failure: only original ID 1
```

This is the proof we were waiting for. The first INSERT really happened inside
the transaction, but it never became published state. The database after the
failed import matched the database before the import.

After removing the trigger, we retried the exact same batch. It received IDs 2
and 3—not 3 and 4—showing that rollback left no record and did not consume an
ID. Another complete server restart returned all three notes exactly.

Two quieter cases passed as well:

- An empty import reported zero, changed nothing, and did not consume ID 1.
- A timezone-naive timestamp in the second item rejected the whole payload and
  preserved the preexisting public state.

At this import-connection gate, the full suite passed 85 tests on Python 3.12.
Four final hold regressions landed afterward, and the reconciled canonical suite
now passes 89 tests. The extra four do not change this experiment's result; they
close adjacent startup and contract holds around the same connected system.

### What became green

```text
File -> CLI -> one batch HTTP request            green
Request -> complete validation                   green
Service -> one add_many call                     green
add_many -> one SQLite transaction               green
Second-insert failure -> complete rollback       green
Clean retry -> no residue or ID gap              green
Successful import -> survives process restart    green
```

### What this still does not promise

Imagine the database commits successfully but the HTTP response disappears on
the network. The command may believe the operation failed even though every note
was stored. A blind retry could insert the batch again.

Our current evidence proves transaction rollback after a known failure. It does
not provide an idempotency key for an uncertain response. That is the difference
between atomicity and retry safety showing up in a real connected system.

Duplicate normalized tags are also still permitted. That behavior was outside
the accepted atomic-import slice rather than accidentally forgotten inside it.

The architecture's next red boundary is now export and recovery:

```text
durable database
    -> atomic portable JSON export
    -> separate empty database
    -> atomic import
    -> equivalent recovered notes
```

We have moved from "can a note survive the server?" to "can the user carry all
their notes safely out of the application and reconstruct them somewhere else?"

## Read the real code with me

The architecture becomes much less abstract when we follow one import through
the actual functions. These are short excerpts from the working tree at the
89-test checkpoint. A comment marks the one mechanically repetitive section I
abridged; the behavior-bearing lines are preserved.

### 1. The command sends one request for the whole file

From `tools/import_sample.py`:

```python
def import_payload(self, payload) -> dict:
    request = Request(
        f"{self.api_url}/api/import",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request) as response:
            result = json.loads(response.read())
    except HTTPError as exc:
        # Convert the API's structured failure into a useful CLI error.
        ...
```

`payload` is the complete import document. There is no loop here that sends one
HTTP request per note. That matters because the server can now make one decision
about the whole group: either accept every note or accept none of them.

The useful software-engineering phrase is **authority boundary**. The CLI does
not assign final IDs or write SQLite itself. It asks the running application—the
authority that owns the data—to perform the import.

### 2. The service validates everything before touching storage

From `fieldnotes/service.py`:

```python
def import_notes(self, payload: Any):
    drafts = validate_import_payload(payload)
    if not drafts:
        return []
    return self.repository.add_many(drafts)
```

This tiny function carries a surprisingly strong contract:

1. Validate the complete external payload.
2. Treat an empty import as a real no-op.
3. Make exactly one batch call to the repository.

Suppose note 1 is valid and note 2 has a timezone-naive timestamp. Validation
fails before `add_many()` is reached, so note 1 never even becomes a database
candidate. This is **fail before mutation**: reject bad input while the durable
state is still untouched.

### 3. SQLite gives the batch one commit point

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
                # Read the inserted row and append it to `created`.
            self._connection.execute("COMMIT")
        except Exception:
            self._rollback()
            raise
        return created
```

There are three nested boundaries here:

- `with self._lock` prevents another thread using this repository object from
  slipping a write into the middle of the batch.
- `BEGIN IMMEDIATE` starts one SQLite write transaction before the loop.
- `COMMIT` occurs only after every insertion succeeds.

If insertion 2 raises, control jumps to `except`, `_rollback()` erases insertion
1 from the uncommitted transaction, and `raise` preserves the failure for the
layers above. Notice that `created` being a Python list does not mean anything
has been durably published. The database transaction—not the local variable—is
the source of truth.

This is why implementing the batch as a loop over the public `add()` method
would be wrong. Each `add()` has its own transaction, so the first note could be
committed before the second failed. It would also try to acquire this adapter's
non-reentrant lock again if called while `add_many()` held it.

### 4. The test kills the process, not merely the repository object

From `tests/test_http_persistence.py`:

```python
first_server = self.start_server()
created = first_server.request("POST", "/api/notes", payload)
first_server.stop()

second_server = self.start_server()
self.assertEqual(
    second_server.request("GET", "/api/notes")["notes"],
    [created],
)
```

`first_server.stop()` sends `SIGINT` to the subprocess and waits for it to exit.
The second server is a genuinely new Python process pointed at the same temporary
SQLite path. It cannot see the first process's memory. Therefore, when its HTTP
API returns `created`, the note must have crossed the disk boundary.

That is the difference between these two claims:

```text
repository.close(); repository.reopen()  -> adapter persistence evidence
process exits; new process serves note   -> public connection evidence
```

Both tests are useful, but the second one covers more architecture.

### 5. The failure test deliberately sabotages row 2

From `tests/test_import_connection.py`:

```python
connection.execute(
    "CREATE TRIGGER reject_second_batch_note BEFORE INSERT ON notes "
    "WHEN NEW.title = 'Reject me' "
    "BEGIN SELECT RAISE(ABORT, 'controlled batch failure'); END"
)

failed = self.run_import(payload_path, failing_server)
self.assertNotEqual(failed.returncode, 0)
self.assertEqual(
    failing_server.request("GET", "/api/notes")["notes"],
    [existing],
)
```

The test creates a temporary SQLite trigger: whenever a row titled `Reject me`
is inserted, SQLite aborts that statement. The import puts a valid note first and
the rejected note second. This guarantees that the failure happens *after* the
transaction has already performed meaningful work.

The final assertion is the heart of the experiment. `[existing]` is the exact
state captured before the attempted import. We are not merely checking that an
error message appeared; we are checking the promised invariant:

```text
state after failed batch == state before failed batch
```

Then the test removes the trigger, retries the same payload, and expects IDs
`[1, 2, 3]`. If the failed transaction had leaked a row or consumed an ID, that
sequence would expose it.

## The senior-engineer reading habit hiding in these excerpts

When you read unfamiliar code, you do not need to understand every line at once.
Ask four questions:

1. **Where does untrusted input enter?** Here: the CLI payload and HTTP request.
2. **Where is policy decided?** Here: validation and the service operation.
3. **Where does durable mutation happen?** Here: the SQLite transaction.
4. **What experiment proves the boundary?** Here: a killed process and a forced
   failure on the second insertion.

That is already architecture review. Seniority is not memorizing every library
call; it is learning to locate ownership, lifetimes, commit points, and failure
boundaries—and then demanding evidence for the connections between them.
