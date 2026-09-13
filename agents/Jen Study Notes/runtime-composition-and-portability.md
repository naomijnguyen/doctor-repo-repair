# Runtime Composition and Portability: Jen's Study Notes

> **Reading note:** This chapter preserves both the preparation and implementation
> checkpoints. Durable runtime composition and one-request CLI import are now
> verified. See [`README.md`](README.md) for the current status and study order.

## The short version

My part of the repair is to make sure every real way of using Field Notes reaches
the same durable collection of notes.

The application has several pieces that can each look correct in isolation:

```text
server
import command
export command
repository
database
```

But isolated correctness is not enough. If those pieces construct different
repositories, use different database paths, or disagree about when a connection
closes, the product still loses or splits the user's data.

The goal is one connected route:

```text
configuration
      |
      v
composition root
      |
      v
SQLite repository
      |
      v
one durable database
```

The server, importer, and exporter then enter that route at deliberate points.

## What "runtime composition" means

Runtime composition is the moment when the application takes its separate parts
and connects them into a working system.

Here are three perfectly reasonable pieces:

```python
repository = SQLiteRepository(path)
service = NoteService(repository)
server = FieldNotesServer(service)
```

The repository knows how to store notes. The service knows the product rules.
The server knows HTTP. None of those pieces should decide the entire application
architecture by itself.

The composition code makes that decision:

```python
def create_service(data_path=None):
    path = data_path or get_data_file()
    repository = SQLiteRepository(path)
    return NoteService(repository)
```

That example is illustrative, not the final interface. We will adopt the exact
constructor and lifecycle Agent 2 proves rather than guessing them here.

The important idea is that construction happens in one obvious place.

This place is commonly called the **composition root**. It is the top-level part
of a program that answers questions like:

- Which repository implementation are we using?
- Which database file should it open?
- Which service receives that repository?
- Who owns the repository's lifetime?
- Who closes it when the application stops?

The rest of the application uses the connected objects. It does not repeatedly
make new ones behind our backs.

## What is wrong with construction at import time

The server currently does this at module level:

```python
repository = NoteRepository()
service = NoteService(repository)
```

That code runs as soon as Python imports `fieldnotes.server`.

It seems convenient, but it hides an important event. Importing a module now
creates the application's state owner. With SQLite, importing could also open a
database connection before the caller has chosen configuration or before a test
has installed its temporary path.

For example:

```python
import fieldnotes.server

# Too late if the repository was already created during import.
os.environ["FIELDNOTES_DATA"] = "/tmp/test.sqlite3"
```

The test thinks it selected a temporary database, while the server may already
be holding the default database.

Explicit construction makes the timing visible:

```python
os.environ["FIELDNOTES_DATA"] = "/tmp/test.sqlite3"
server = build_server()
```

Now configuration is resolved when the server is built, not as a side effect of
merely examining the module.

## The one-state-owner rule

Suppose the server and an import command each create their own in-memory
repository:

```text
browser -> server -> repository A

import command -> repository B
```

The importer can honestly print:

```text
Imported 3 notes
```

while the browser still shows zero notes. The import succeeded in repository B,
then repository B disappeared when the command exited.

This was essentially the original sample-import behavior.

The repaired import command currently reaches the running HTTP server, which is
a major conceptual improvement:

```text
import command -> HTTP API -> server service -> repository A
browser        -> HTTP API -> server service -> repository A
```

Both entry points can now see the same live state.

The remaining problem belongs to atomic import: the command currently makes one
request per note. Agent 3 is replacing that with one accepted batch operation.
Agent 4 will migrate the command only after that contract is proven.

## Why a configured path is part of the architecture

A SQLite repository is not durable merely because it uses SQLite. Every process
must open the intended file.

These paths are different:

```text
./data/fieldnotes.sqlite3
/path/to/project/data/fieldnotes.sqlite3
/tmp/fieldnotes.sqlite3
```

Relative paths introduce another subtlety. This configuration:

```text
./data/fieldnotes.sqlite3
```

is resolved relative to the process's current working directory unless the
application deliberately establishes another base.

Starting the same program from two directories could therefore create two
databases:

```text
project directory/data/fieldnotes.sqlite3
home directory/data/fieldnotes.sqlite3
```

Both runs appear healthy. The notes simply seem to vanish between them because
the runs opened different files.

That is why Agent 4 owns both repository selection and data-path configuration.
They are one connection problem, not unrelated preferences.

The current configuration policy already points in a useful direction:

```text
FIELDNOTES_DATA     canonical name
FIELD_NOTES_DATA    legacy compatibility fallback
```

If both are set, the canonical name wins.

The current default still ends in `.json`, even though the target store is
SQLite:

```text
./data/fieldnotes.json
```

My proposed default is:

```text
./data/fieldnotes.sqlite3
```

We should freeze that choice when Agent 2's constructor and path behavior are
accepted. I will not silently reinterpret the old JSON-looking filename before
then.

## Repository lifetime: opening is only half the contract

Once SQLite exists, somebody must own its lifetime.

A complete lifecycle looks like:

```text
resolve configuration
        |
        v
open repository
        |
        v
start server
        |
        v
serve requests
        |
        v
stop server
        |
        v
close repository
```

The unhappy path matters too:

```text
open repository
        |
        v
server startup fails
        |
        v
close repository anyway
```

Python commonly expresses this with `try` and `finally`:

```python
repository = create_repository()
try:
    serve(repository)
finally:
    repository.close()
```

Or the repository may provide a context manager:

```python
with create_repository() as repository:
    serve(repository)
```

Agent 2 must define and test the actual lifecycle. Agent 4's responsibility is
to use it correctly in the real runtime.

## Why Agent 4 waits for Agent 2

It would be easy for composition work to guess an interface:

```python
SQLiteRepository(path)
repository.close()
```

But Agent 2 might correctly discover that the safe adapter needs something
different, such as:

```python
SQLiteRepository.open(path)
```

or a context-managed connection per operation.

If I build the server around an imaginary interface while Agent 2 proves a real
one, we create merge conflicts and pressure the storage design to accommodate
unreviewed assumptions.

Waiting here is not inactivity. It is respecting an architectural boundary.

Before integration, I need Agent 2's evidence for:

- constructor and database-path handling;
- schema initialization;
- connection ownership;
- thread safety;
- commit boundaries;
- rollback behavior;
- close behavior;
- records surviving close and reopen; and
- clear failure on an unusable or invalid database.

## Why Agent 4 waits for Agent 3

The current command uses a repository-shaped HTTP adapter. Calling:

```python
repository.add(title, body, tags)
```

actually sends:

```http
POST /api/notes
```

That happens once for every imported note.

Agent 3 is defining the replacement batch operation. Until that work is
accepted, these details are still contract decisions:

- batch URL;
- request shape;
- response shape;
- timestamp behavior;
- maximum batch size;
- empty-batch behavior; and
- transaction interface.

If Agent 4 picks `/api/import` today while Agent 3 proves that
`/api/notes/import` produces a cleaner or safer contract, my "integration" work
would merely create another migration.

So the command migration waits for the accepted batch route.

## Direct database access versus going through the API

The server and import command have a special coordination problem.

If both independently write the SQLite file:

```text
server ------> database
import tool --> database
```

SQLite can coordinate many access patterns, but now two processes own write
behavior and must agree on schema, transactions, errors, and lifecycle.

The intended import route is simpler:

```text
import tool -> one HTTP batch -> running server -> service -> database
```

The running server remains the authority for business rules and writes.

Export has a different shape. A read-only export command may reasonably open the
configured repository through the same composition factory, take a consistent
snapshot, write the export, and close it. That avoids requiring the browser or
server merely to make a portable backup.

Whichever route is accepted, "same repository" means the same implementation,
configuration policy, schema, and authoritative database—not necessarily the
same Python object across separate processes.

## What portable export means

SQLite is excellent application storage, but a database file is not the nicest
portable interchange format.

A Field Notes export should look like ordinary UTF-8 JSON:

```json
{
  "notes": [
    {
      "id": 7,
      "title": "Observation",
      "body": "Something happened.",
      "tags": ["field-work"],
      "createdAt": "2026-09-12T20:30:00+00:00"
    }
  ]
}
```

The portable representation uses the public field name `createdAt`, even if the
Python model or SQLite column uses a different internal spelling.

An export must contain Field Notes data only. It should not accidentally include
configuration, logs, filesystem paths, SQLite journal files, or other machine
information.

## Why export must be atomic too

Imagine that `notes.json` is yesterday's complete backup. The exporter opens it
directly and begins writing today's backup:

```text
write note 1
write note 2
disk full
```

The command fails, but yesterday's valid backup has already been truncated and
replaced by an incomplete JSON fragment.

The safer pattern is:

```text
notes.json             existing valid export
notes.json.temporary   new export being written
```

The exporter:

1. creates a temporary file beside the destination;
2. writes the entire JSON document as UTF-8;
3. flushes and closes the completed temporary file;
4. atomically replaces the destination; and
5. removes the temporary file if anything fails before replacement.

Conceptually:

```python
write_complete_export(temporary_path)
os.replace(temporary_path, destination_path)
```

Because the temporary file is a sibling of the destination, the final rename is
performed within the same filesystem, where atomic replacement can provide the
guarantee we need.

The observable outcomes become:

```text
success -> destination contains the complete new export
failure -> destination still contains the complete old export
```

There should be no state in which Field Notes reports failure after destroying
the user's previous good backup.

## Interesting findings from the readiness pass

### The suite passes, but the target connection does not exist yet

The current working tree passes 34 tests. That is encouraging, but the passing
tests mostly prove repaired in-memory behavior and component-level contracts.

They do not yet prove:

- SQLite persistence;
- close and reopen behavior;
- server restart persistence;
- batch rollback after a mid-write failure;
- import timestamp preservation;
- atomic export; or
- recovery from an unusable database path.

This is a useful testing lesson: **a green suite proves only what the suite
actually exercises**.

### Full-file validation is not the same as atomic storage

The importer checks all records before it begins sending requests. That prevents
a malformed third record from being discovered only after two writes.

But a storage or network failure can still occur during the third request:

```text
validation of A, B, C -> success
POST A                 -> committed
POST B                 -> committed
POST C                 -> connection failure
```

Pre-validation reduced one failure mode. It did not create an atomic import.

### The repaired importer found the right state owner but the wrong unit of work

The original tool wrote to a private temporary repository. The repaired tool
correctly contacts the running server, so imported notes can appear in the same
live state as browser-created notes.

Its remaining weakness is granularity: one request per note instead of one
request for the batch.

That distinction is subtle and important:

```text
Connection question: Are we talking to the authoritative application?
Atomicity question: Are all notes committed as one operation?
```

The current tool improved the first without yet solving the second.

### A file extension can expose architectural drift

The target store is SQLite, but the default configured path still ends in
`.json`. The extension does not technically prevent SQLite from opening the
file, but it miscommunicates the storage format to humans and tools.

That tiny inconsistency is evidence that configuration moved ahead on one track
while persistence remained on another.

### Runtime artifacts need more than one ignore pattern

SQLite may create companion files during normal operation:

```text
fieldnotes.sqlite3
fieldnotes.sqlite3-journal
fieldnotes.sqlite3-wal
fieldnotes.sqlite3-shm
```

Ignoring only the main database can leave journals or shared-memory files
visible to Git. Agent 4 will add narrow patterns for the accepted database name
and its runtime companions without hiding committed sample JSON.

### Composition changes overlap with HTTP hardening

Another agent has already improved `server.py` with request-size checks, error
containment, and narrower CORS behavior.

Agent 4 also needs to change `server.py`, but only around construction and
lifecycle. Replacing the whole file with a clean composition rewrite would erase
valid independent work.

The safe approach is a surgical change:

```text
preserve Handler request behavior
preserve CORS and error handling
replace global repository construction
inject composed service
add repository shutdown lifecycle
```

This is one reason isolated branches and narrow ownership matter even in a small
codebase.

## My implementation plan

### Gate 1: accept durable storage

Wait for Agent 2's adapter and evidence. Record its exact constructor, path
semantics, threading model, transaction interface, and close lifecycle.

### Step 1: establish one composition root

Add one small module responsible for:

```text
configured data path
        +
accepted repository constructor
        +
service construction
```

No SQLite queries or schema decisions belong in this module.

### Step 2: connect the server

Refactor server startup so it:

1. resolves configuration at startup;
2. opens the accepted SQLite repository;
3. builds the service with that repository;
4. supplies the service to request handling;
5. starts listening only after composition succeeds; and
6. closes the repository during clean or failed shutdown.

An unusable configured path should produce a clear startup failure. The server
must not silently fall back to memory, because that would make the application
appear healthy while discarding notes on restart.

### Step 3: give Agent 5 a restart test route

Agent 5 will independently verify the real process boundary:

```text
start server with empty database
create note over HTTP
stop process
start fresh process with same path
GET notes
confirm same note and ID
```

That test proves the complete connection rather than merely calling repository
methods inside one Python process.

### Gate 2: accept atomic import

Wait for Agent 3's batch URL, payload, response, timestamp policy, and rollback
evidence.

### Step 4: migrate the command to one batch request

Preserve the useful CLI behavior already added:

- configurable API URL;
- clear connection failures;
- useful messages from structured API errors; and
- support for an explicitly supplied input path.

Replace only the per-note transport with the accepted batch operation.

### Gate 3: verify persistence and import together

Confirm that a batch imported through the running server remains present after a
fresh server process opens the same database.

### Step 5: add portable atomic export

Build export against the same repository selection and data-path configuration.
Test both:

```text
complete export replaces destination
failed export preserves previous destination
```

### Step 6: integration handoff

Give Agent 5 exact commands and expected observations for:

- configured startup;
- invalid-path startup failure;
- create and restart persistence;
- successful batch import;
- failed batch rollback;
- export contents;
- export atomicity; and
- import/export portability.

## What Agent 4 deliberately does not own

Clear boundaries prevent "integration" from becoming permission to rewrite the
whole application.

Agent 4 does not define:

- SQLite tables or queries;
- transaction internals;
- import validation semantics;
- general API cleanup;
- browser request behavior;
- CSS or UI states; or
- unrelated documentation.

If one of those areas blocks the connection, I will return evidence to its owner
rather than quietly implementing a second version inside the composition layer.

## The mental model to keep

Agent 2 builds and proves the safe.

Agent 3 defines how a sealed package of imported notes enters the safe.

Agent 4 installs the safe in the actual building, gives every approved entrance
a route to it, and makes sure the safe is closed properly when the building shuts
down.

Agent 5 then leaves the building, comes back through every entrance, pulls the
power, restarts everything, and checks whether the same valuables are still
there.

That is why composition is not merely "wiring." It is where separately correct
components become one trustworthy product.

## What happened next: the connections became real

The earlier sections described the plan while Agent 4 was waiting at the storage
and import gates. Those gates have now advanced, and several useful engineering
lessons appeared during the actual connection work.

The current verified path is much larger than it was before:

```text
configured database path
    -> SQLite repository
    -> service
    -> HTTP server
    -> create, list, and delete
    -> complete process stop
    -> fresh server process
    -> same durable state
```

The import path has also been connected:

```text
JSON file
    -> import command
    -> one POST /api/import
    -> complete validation
    -> one service operation
    -> one repository transaction
    -> all notes committed or none committed
```

The full project check now passes **86 tests**. That count includes component,
composition, and real subprocess connection evidence. The number is useful as a
snapshot, but the kinds of boundaries those tests cross matter more than the raw
total.

## The storage adapter needed more than one version-zero fix

SQLite exposes an application-controlled integer:

```sql
PRAGMA user_version;
```

Field Notes uses version 1 for its current schema. A value of zero does not
necessarily mean "brand-new empty database." It means the database has not been
assigned an application schema version.

That creates several distinct cases.

### Case 1: truly empty database

```text
user_version = 0
no user tables
```

Field Notes can safely create its schema and mark the database as version 1.

### Case 2: compatible unversioned Field Notes table

```text
user_version = 0
notes table has the exact expected schema
existing rows are readable
```

Field Notes can safely adopt the table, preserve its rows, and mark it as version
1.

### Case 3: incompatible table named `notes`

```text
user_version = 0
notes table exists
columns do not match the Field Notes contract
```

The application must reject this database without changing its schema, rows, or
version.

The dangerous behavior would be:

```text
see version zero
    -> run CREATE TABLE IF NOT EXISTS
    -> existing incompatible table remains unchanged
    -> stamp version 1 anyway
    -> fail later when reading missing columns
```

That would label a database as compatible before compatibility had been proved.

### Case 4: unrelated unversioned database

```text
user_version = 0
some unrelated user table exists
no notes table exists
```

Silently adding a `notes` table and claiming the whole file as Field Notes storage
would mutate a database that may belong to another application. The safe behavior
is to refuse it without modification.

### Case 5: database claims version 1 but lacks the schema

```text
user_version = 1
required notes table missing or incompatible
```

This is not a new database. It is an incomplete, damaged, or foreign database
claiming to satisfy the version-1 contract. Reconstructing an empty table would
mask the problem and might make missing data look intentional.

The correct response is a visible construction failure.

### Case 6: compatible columns but unreadable rows

A table can look structurally correct while containing values that violate the
repository contract. For example, the `tags` column may contain text that is not
a JSON array of strings.

```text
schema inspection -> compatible
row decoding       -> fails
```

Adoption must check both structure and readable content before stamping version
1. Otherwise construction reports success and the first ordinary list operation
fails later.

Agent 2 added focused tests for these cases. That is why the storage gate could
eventually be accepted rather than merely assumed safe.

The broader lesson is:

> Schema versioning is a claim about compatibility, not just a number to write
> after running `CREATE TABLE IF NOT EXISTS`.

## The composition root we actually installed

Agent 4 added a small module named `fieldnotes/composition.py`.

Its first function selects the durable repository:

```python
def create_repository(database_path=None):
    selected_path = get_data_file() if database_path is None else database_path
    return SQLiteNoteRepository(selected_path)
```

Its second function connects that repository to the service:

```python
def create_service(database_path=None):
    repository = create_repository(database_path)
    return NoteService(repository), repository
```

Returning both objects is deliberate:

```text
service     -> uses the repository
runtime     -> owns and closes the repository
```

The server no longer creates this hidden state while its module is imported:

```python
repository = NoteRepository()
service = NoteService(repository)
```

Instead, server startup calls the composition root explicitly and injects the
resulting service into its HTTP handler class.

The request path is now:

```text
build_server
    -> create_service
    -> create_repository
    -> SQLiteNoteRepository(configured path)
    -> NoteService(the same repository)
    -> handler_for(the same service)
    -> HTTP requests
```

The identity matters. The service is not connected to one repository while the
runtime closes another. A focused test checks that the handler's service and the
returned lifecycle owner lead to the exact same repository object.

## Why the server builder returns the repository

The server builder returns two lifecycle owners:

```python
server, repository = build_server()
```

Then the main runtime uses:

```python
try:
    server.serve_forever()
finally:
    server.server_close()
    repository.close()
```

This says something clear about responsibility:

> The code that opens long-lived resources must retain enough information to
> close them.

The repository commits successful writes before returning, so shutdown is not
being used as a substitute for transaction durability. Closing is still required
for correct connection lifecycle, cleanup, repeatable tests, and clean reopen
behavior.

## The server-bind failure window

Composition has more than one construction step:

```text
open repository
    -> create service
    -> bind HTTP port
```

Opening SQLite may succeed while binding the network port fails because another
process already owns it.

Without cleanup:

```text
repository opened
port bind raises OSError
function exits
repository connection is leaked
```

The builder therefore guards the bind:

```python
try:
    server = ThreadingHTTPServer(...)
except Exception:
    repository.close()
    raise
```

A focused test forces the bind to fail and checks that `close()` was called once.

This is an example of **partial construction cleanup**: when step three fails,
the function must unwind resources acquired by steps one and two.

## The startup-order bug we found afterward

Agent 1 and Agent 5 found a different failure window in the initial composition
implementation.

The server builder originally did this:

```python
service, repository = create_service(data_path)
selected_port = get_port() if port is None else port
```

Suppose the environment contained:

```text
FIELDNOTES_PORT=not-a-port
```

The sequence became:

```text
create SQLite database
open repository
try to convert "not-a-port" to an integer
raise ValueError
```

The server never started, but startup had already created a real database file.
The failure also occurred before the socket-binding cleanup guard.

This violates a useful startup principle:

> Validate cheap, side-effect-free configuration before acquiring resources or
> changing the filesystem.

The repaired order is:

```python
selected_port = get_port() if port is None else port
service, repository = create_service(data_path)
```

Now:

```text
parse invalid port
    -> fail
    -> no repository opened
    -> no database created
```

A regression test supplies the malformed port and confirms the configured
database path does not exist afterward.

This finding is especially interesting because normal startup and persistence
were already working. A successful-path test could not expose the ordering flaw;
we needed a controlled configuration failure.

## The public restart proof is now real

Agent 5 tested the whole connection rather than calling repository methods
directly.

The proof crosses separate server processes:

```text
start server process A with explicit database path
    -> create a note through HTTP
    -> stop process A completely

start server process B with the same path
    -> list notes through HTTP
    -> receive the same note, ID, tags, and timestamp

delete through HTTP
    -> stop process B completely

start server process C with the same path
    -> list notes through HTTP
    -> deleted note remains absent
```

That moves the durable runtime connection beyond "the objects appear wired
correctly." A fresh process cannot see process A's Python list. Returning the same
note proves the request reached committed SQLite state.

Agent 5 also tested startup against corrupt SQLite bytes and incompatible schema.
The server exited without listening and left the input files unchanged. It did
not hide the failure by constructing an empty in-memory repository.

## The atomic import path Agent 3 activated

Agent 3 added an immutable storage-neutral draft:

```python
@dataclass(frozen=True)
class NoteDraft:
    title: str
    body: str
    tags: tuple[str, ...]
    created_at: str
```

It deliberately has no ID. Imported IDs belong to the source database and are
not assumed to be safe in the destination.

The route accepts:

```http
POST /api/import
```

with:

```json
{
  "notes": [
    {
      "id": 9001,
      "title": "Field observation",
      "tags": ["Field Work"],
      "createdAt": "2026-09-12T13:30:00-07:00"
    }
  ]
}
```

The source ID is ignored. The timestamp is converted to the same instant in UTC.
The repository assigns a new local ID inside the batch transaction.

A non-empty committed batch returns 201:

```json
{
  "imported": 1,
  "notes": [
    {
      "id": 12,
      "title": "Field observation",
      "body": "",
      "tags": ["field-work"],
      "createdAt": "2026-09-12T20:30:00+00:00"
    }
  ]
}
```

An empty batch is an accepted no-op and returns 200:

```json
{
  "imported": 0,
  "notes": []
}
```

Using 200 for the empty case avoids claiming that a resource was created when
nothing changed.

## Why the old command still bypassed the new route

After Agent 3's work, the internal batch path was active:

```text
POST /api/import
    -> validate complete payload
    -> service.import_notes
    -> repository.add_many
    -> one transaction
```

But the user-facing command still used the earlier adapter:

```text
file
    -> validate locally
    -> POST /api/notes for A
    -> POST /api/notes for B
    -> POST /api/notes for C
```

This is a perfect example of a green component path with a missing entrance.

The atomic route could pass every direct API test while the normal command never
called it. Users of the command would still receive partial imports after a later
request failure.

Agent 4 therefore replaced the repository-shaped per-note adapter with an
`ApiImportClient` whose meaningful operation is:

```python
client.import_payload(complete_payload)
```

That method sends exactly one request to `/api/import`.

## Why the command parses but does not semantically validate

The command reads the file and runs JSON parsing locally:

```python
payload = json.loads(path.read_text(encoding="utf-8"))
```

This catches errors such as malformed JSON or unreadable files and can name the
file in a useful message.

It deliberately does not perform the full note validation and then rebuild the
payload.

If it did, it could:

- normalize tags before the server sees the source;
- assign missing timestamps in the CLI process;
- discard source IDs or unknown fields;
- canonicalize a timestamp twice; or
- drift from future server-side rules.

Instead:

```text
CLI responsibility:    can this file be read as JSON?
Server responsibility: is this a valid Field Notes import?
```

The original parsed document is sent intact. The server remains the single
semantic authority.

For example, this value must reach the server unchanged:

```json
"createdAt": "2026-09-12T13:30:00-07:00"
```

The server then applies the accepted policy and returns:

```json
"createdAt": "2026-09-12T20:30:00+00:00"
```

Both strings represent the same instant.

## Honest command success and failure

The command prints success only after receiving a complete valid response shaped
like:

```json
{
  "imported": 2,
  "notes": []
}
```

If the API returns a structured error:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "note at index 1 requires a non-empty title"
  }
}
```

the command preserves the useful message rather than reducing it to generic
"Bad Request."

It also checks that a nominally successful response actually contains an integer
`imported` count and a `notes` list. A malformed success response is not printed
as though the import completed.

The command does not automatically retry a failed request. That restraint is
important because a lost response can be ambiguous.

## Transaction safety is now connected; retry safety is not

Consider this sequence:

```text
server commits the complete batch
    -> response connection breaks
    -> command sees a network failure
```

The command does not know whether the server committed.

If it automatically repeats the request, it may create the same notes again. The
transaction guarantees that a failed database operation leaves no partial batch.
It cannot tell the client what happened when the response itself is lost after a
successful commit.

These remain distinct guarantees:

```text
Atomicity:
failed transaction -> none of the batch remains

Idempotency:
repeat uncertain request -> no duplicate batch
```

True retry safety would likely require an import key stored transactionally with
the result. That is a future API and schema contract, not something Agent 4 hid
inside the CLI.

## The new public import proof

Agent 5's current black-box import tests exercise the real command and server.

The success route is:

```text
run import CLI against server process A
    -> complete batch becomes visible through GET /api/notes
    -> stop process A
    -> start process B against the same database
    -> same imported notes remain visible
```

The failure evidence includes:

- an invalid timestamp later in the payload rejecting the complete import;
- a deterministic storage failure during the batch leaving the earlier snapshot
  unchanged;
- a clean retry after the failure; and
- an empty import behaving as a no-op without consuming an ID.

This matters because a validation rejection before storage and a rollback after
an insertion attempt prove different things. The suite now contains evidence for
both boundaries.

## What the tests now prove

The 86-test snapshot includes several layers.

### Storage component evidence

- schema initialization and cautious adoption;
- incompatible or damaged schema rejection;
- create and delete persistence;
- transaction rollback;
- batch rollback;
- stable IDs and timestamps;
- lock-protected concurrent use of one repository object.

### Composition evidence

- configured path selects SQLite;
- service and handler receive the same repository;
- invalid database content does not trigger memory fallback;
- bind failure closes the repository;
- malformed port fails before database creation; and
- port zero supports isolated server-test construction.

### Public connection evidence

- HTTP create survives a new process;
- HTTP delete survives another new process;
- corrupt and incompatible databases prevent server startup;
- the real CLI sends a durable atomic import;
- imported notes survive restart;
- invalid imports leave state unchanged;
- mid-batch failure rolls back; and
- retry after rollback succeeds cleanly.

The useful lesson is not "86 is a big number." It is:

> We now have tests at the component, composition, transport, process, and recovery
> boundaries, and each one makes a narrower honest claim.

## What remains for Agent 4

The next portability connection is export:

```text
configured SQLite database
    -> consistent repository read
    -> public note representation
    -> UTF-8 JSON temporary sibling
    -> atomic destination replacement
```

The key success and failure pair should be:

```text
success:
complete new export replaces destination

failure:
previous valid destination remains byte-for-byte intact
```

Then Agent 5 can prove the recovery loop:

```text
database A
    -> export JSON
    -> import into empty database B
    -> compare meaningful note fields
```

IDs need special interpretation in that comparison because they are deliberately
database-local. Titles, bodies, tags, and creation instants are the portable
meaningful fields.

## The updated mental model

Agent 2 built the safe, tested its lock, checked its contents, and learned how to
recognize when a different safe was already occupying the room.

Agent 4 installed it in the building, connected the front desk, arranged orderly
closing, and fixed the strange case where a malformed street address caused the
safe to be installed before anyone realized the building could not open.

Agent 3 built a loading dock that accepts one sealed shipment and commits all of
it or none of it.

Agent 4 redirected the delivery truck away from the old one-box-at-a-time side
door and toward that loading dock.

Agent 5 drove the truck through the real route, shut the building down, reopened
it, forced failures, and checked that every accepted package was still there and
every rejected shipment was completely absent.

The remaining job is to build a safe export door: one that can produce a complete
portable inventory without destroying yesterday's good inventory if today's
write fails.

## Code-reading appendix

This appendix collects the most important implementation excerpts in the order a
request travels through the application. The excerpts are intentionally small so
each one answers a specific architectural question.

### 1. Selecting the configured database path

From `fieldnotes/config.py`:

```python
DEFAULT_PORT = 8000
DEFAULT_DATA_FILE = "./data/fieldnotes.sqlite3"


def get_port() -> int:
    return int(os.getenv("FIELDNOTES_PORT", DEFAULT_PORT))


def get_data_file() -> str:
    return os.getenv(
        "FIELDNOTES_DATA",
        os.getenv("FIELD_NOTES_DATA", DEFAULT_DATA_FILE),
    )
```

`get_data_file()` has no arguments. It returns one string containing the selected
database path.

The nested lookup establishes precedence:

```text
FIELDNOTES_DATA
    -> otherwise FIELD_NOTES_DATA
        -> otherwise ./data/fieldnotes.sqlite3
```

The outer variable is the canonical spelling. The inner variable is retained for
compatibility with older configuration.

One subtle detail is that `get_port()` can raise `ValueError`:

```python
int("not-a-port")
```

That failure is useful. The application should not guess a port when the user has
provided an invalid one.

### 2. Constructing the durable repository

From `fieldnotes/composition.py`:

```python
def create_repository(
    database_path: str | Path | None = None,
) -> SQLiteNoteRepository:
    """Construct the configured durable repository for an application runtime."""
    selected_path = get_data_file() if database_path is None else database_path
    return SQLiteNoteRepository(selected_path)
```

Input:

```text
database_path = explicit str or Path
                or None to use configuration
```

Output:

```text
one open SQLiteNoteRepository
```

The conditional expression means:

```python
if database_path is None:
    selected_path = get_data_file()
else:
    selected_path = database_path
```

Using `is None` matters. An explicitly supplied but invalid value should reach the
repository and fail visibly; the composition layer should not silently replace it
because it happens to be false-like.

The function does not catch `sqlite3.DatabaseError`. If the configured file is
corrupt or incompatible, construction fails and the error travels upward. That
is what prevents an unsafe memory fallback.

### 3. Connecting the service and preserving lifecycle ownership

Also from `fieldnotes/composition.py`:

```python
def create_service(
    database_path: str | Path | None = None,
) -> tuple[NoteService, SQLiteNoteRepository]:
    """Compose the service and return its repository for lifecycle ownership."""
    repository = create_repository(database_path)
    return NoteService(repository), repository
```

The function returns a tuple:

```python
service, repository = create_service()
```

Both names lead to the same state owner:

```text
service.repository ─────┐
                       ├── same SQLiteNoteRepository object
repository ─────────────┘
```

Why not return only the service?

The service needs the repository to perform work. The runtime needs the repository
to close its lifecycle. Returning both makes that second responsibility explicit.

### 4. Giving one service to every HTTP handler

From `fieldnotes/server.py`:

```python
class Handler(BaseHTTPRequestHandler):
    service: NoteService
```

This annotation says every configured handler class must have a `service`.

The binding happens here:

```python
def handler_for(service: NoteService):
    """Bind one composed service to all handlers created by an HTTP server."""

    class ServiceHandler(Handler):
        pass

    ServiceHandler.service = service
    return ServiceHandler
```

Input:

```text
one already composed NoteService
```

Output:

```text
a Handler subclass bound to that service
```

This is a small factory. Every request-handler instance created from
`ServiceHandler` can access:

```python
self.service
```

The request path uses it here:

```python
status, headers, response = handle_request(
    self.command,
    self.path,
    body,
    self.service,
)
```

The HTTP translation layer receives the dependency it needs. It does not import a
module-global state owner or construct its own repository.

### 5. Building the server in safe order

From `fieldnotes/server.py`:

```python
def build_server(port: int | None = None, data_path=None):
    """Build a configured server and return its repository lifecycle owner."""
    selected_port = get_port() if port is None else port
    service, repository = create_service(data_path)
    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", selected_port), handler_for(service)
        )
    except Exception:
        repository.close()
        raise
    return server, repository
```

This function contains three meaningful phases.

#### Phase A: validate cheap configuration

```python
selected_port = get_port() if port is None else port
```

Invalid port configuration fails before SQLite construction can create a file.

#### Phase B: acquire storage

```python
service, repository = create_service(data_path)
```

This may create parent directories, initialize a new database, or validate an
existing one.

#### Phase C: acquire the network socket

```python
server = ThreadingHTTPServer(
    ("127.0.0.1", selected_port),
    handler_for(service),
)
```

The server binds to loopback rather than all interfaces. That preserves the
local-only default.

If phase C fails, phase B must be unwound:

```python
except Exception:
    repository.close()
    raise
```

The bare `raise` re-raises the original exception. It does not replace a useful
socket error with a generic cleanup error.

### 6. Closing everything the runtime opened

From `fieldnotes/server.py`:

```python
def main():
    server, repository = build_server()
    port = server.server_address[1]
    logger.info("Field Notes listening on http://127.0.0.1:%s", port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        repository.close()
```

`serve_forever()` is the long-running phase. The `finally` suite runs when control
leaves that phase through the normal Python shutdown path.

The close order is:

```text
stop accepting HTTP traffic
    -> close the listening socket
    -> close the SQLite repository
```

This reduces the chance of accepting new work while the state owner is being
closed.

### 7. Inspecting an unversioned SQLite schema

From `fieldnotes/sqlite_repository.py`, the constructor delegates schema work:

```python
try:
    self._initialize_schema()
except Exception:
    self._connection.close()
    raise
```

If initialization fails, the new connection is closed and the original failure
continues upward.

The schema inspection includes:

```python
version = self._connection.execute(
    "PRAGMA user_version"
).fetchone()[0]

if version not in (0, SCHEMA_VERSION):
    raise sqlite3.DatabaseError(
        f"unsupported database schema version: {version}"
    )
```

This rejects schema versions the application does not understand.

It separately asks whether the expected table already exists:

```python
table_exists = self._connection.execute(
    "SELECT 1 FROM sqlite_schema "
    "WHERE type = 'table' AND name = 'notes'"
).fetchone()

if table_exists and not self._notes_schema_is_compatible():
    raise sqlite3.DatabaseError("incompatible notes table")
```

The condition has two parts:

```text
table exists
AND
table is incompatible
```

Only after compatibility checks does initialization create or stamp schema.

### 8. What structural compatibility checks

The adapter asks SQLite to describe every column:

```python
columns = self._connection.execute(
    "PRAGMA table_info(notes)"
).fetchall()
```

It reduces those rows to the parts Field Notes cares about:

```python
actual = [
    (row["name"], row["type"].upper(), row["notnull"], row["pk"])
    for row in columns
]
```

Then it compares them with the expected contract:

```python
expected = [
    ("id", "INTEGER", 0, 1),
    ("title", "TEXT", 1, 0),
    ("body", "TEXT", 1, 0),
    ("tags", "TEXT", 1, 0),
    ("created_at", "TEXT", 1, 0),
]
```

It also checks that ID allocation uses `AUTOINCREMENT`:

```python
return actual == expected and "AUTOINCREMENT" in schema_sql
```

This is intentionally stricter than checking only that five columns happen to
exist. Column meaning includes type, nullability, primary-key role, and ID
allocation behavior.

### 9. A single-note SQLite transaction

The ordinary `add()` path contains the transaction pattern:

```python
with self._lock:
    try:
        self._connection.execute("BEGIN IMMEDIATE")
        cursor = self._connection.execute(
            "INSERT INTO notes (title, body, tags, created_at) "
            "VALUES (?, ?, ?, "
            "strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'))",
            (title, body, tags_json),
        )
        row = self._connection.execute(
            "SELECT id, title, body, tags, created_at "
            "FROM notes WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        self._connection.execute("COMMIT")
    except Exception:
        self._rollback()
        raise
```

The repository lock prevents two threads using this repository object from
mutating its one SQLite connection simultaneously.

`BEGIN IMMEDIATE` asks SQLite for its write reservation at transaction start. The
insert and read-back happen before `COMMIT`, so the repository can return the
actual committed representation.

The placeholders are also important:

```sql
VALUES (?, ?, ?, ...)
```

and:

```python
(title, body, tags_json)
```

Values are bound separately rather than interpolated into SQL text. A title that
contains quotes remains data rather than becoming part of the SQL command.

### 10. Rolling back only when needed

The helper is:

```python
def _rollback(self) -> None:
    if self._connection.in_transaction:
        self._connection.execute("ROLLBACK")
```

Some failures can occur before a transaction begins or after SQLite has already
ended it. Checking `in_transaction` prevents the cleanup attempt from masking the
original error with "cannot rollback - no transaction is active."

### 11. The immutable import draft

From `fieldnotes/models.py`:

```python
@dataclass(frozen=True)
class NoteDraft:
    title: str
    body: str
    tags: tuple[str, ...]
    created_at: str
```

`NoteDraft` represents a validated note before the destination database assigns
an ID.

Why `frozen=True`?

After validation creates a draft, later code should not quietly change its title
or timestamp while it is crossing into storage.

Why a tuple for tags?

A tuple is immutable. This prevents a caller from appending a tag to the same
collection while the batch operation is using it.

Why no ID?

The source ID belongs to the source database. The destination assigns its own ID
inside the protected transaction.

### 12. Canonicalizing an imported timestamp

From `fieldnotes/importer.py`:

```python
def _canonical_created_at(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{label} createdAt must be a timezone-aware ISO 8601 string"
        )

    candidate = value.strip()
    if candidate.endswith(("Z", "z")):
        candidate = f"{candidate[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(
            f"{label} createdAt must be a timezone-aware ISO 8601 string"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} createdAt must include a timezone offset")

    return parsed.astimezone(timezone.utc).isoformat()
```

Input example:

```text
2026-09-12T13:30:00-07:00
```

Output:

```text
2026-09-12T20:30:00+00:00
```

The clock spelling changes, but the instant does not.

The explicit timezone check rejects:

```text
2026-09-12T13:30:00
```

Without an offset, the application cannot know which real instant the source
intended.

### 13. Converting a complete import payload into drafts

The central validator loops through the complete list:

```python
for index, item in enumerate(notes):
    label = f"note at index {index}"
```

Including the index produces actionable errors such as:

```text
note at index 1 requires a non-empty title
```

After checking field types and normalizing tags, it constructs a draft:

```python
validated.append(
    NoteDraft(
        title=title.strip(),
        body=body.strip(),
        tags=cleaned_tags,
        created_at=created_at,
    )
)
```

The complete function returns drafts only after it has visited every input note:

```python
return validated
```

That separates validation atomicity from storage atomicity:

```text
all records validate
    -> then storage is called

any record fails validation
    -> storage is never called
```

### 14. One service call for the batch

From `fieldnotes/service.py`:

```python
def import_notes(self, payload: Any):
    drafts = validate_import_payload(payload)
    if not drafts:
        return []
    return self.repository.add_many(drafts)
```

Input:

```text
the complete decoded import document
```

Output:

```text
the complete ordered list of stored Note objects
```

The empty check makes an empty import a no-op without asking storage to begin a
transaction or consume an ID.

The non-empty path calls `add_many` once. It does not loop over `add()`.

### 15. The atomic HTTP route

From `fieldnotes/api.py`:

```python
if method == "POST" and parsed.path == "/api/import":
    try:
        notes = service.import_notes(_json_object(body))
        status = 201 if notes else 200
        return _json(
            status,
            {
                "imported": len(notes),
                "notes": [_note_dict(note) for note in notes],
            },
        )
    except ValueError as exc:
        return _error(400, "invalid_request", str(exc))
```

The status line communicates two different successful outcomes:

```python
status = 201 if notes else 200
```

```text
non-empty result -> resources were created -> 201
empty result     -> successful no-op         -> 200
```

One currently tracked review concern is that the `except ValueError` boundary may
be too broad. A validation `ValueError` belongs in a 400 response, but a storage
adapter that raises `ValueError` should reach the server's 500 boundary instead of
being mislabeled as bad client input. That distinction is being tracked as import
hold I1 rather than silently claimed as resolved.

This is a valuable review lesson: even a correct happy-path route can have an
exception-classification problem at its boundary.

### 16. Sending one complete request from the command

From `tools/import_sample.py`:

```python
class ApiImportClient:
    """Send one complete import payload to the running Field Notes API."""

    def __init__(self, api_url: str) -> None:
        self.api_url = api_url.rstrip("/")

    def import_payload(self, payload) -> dict:
        request = Request(
            f"{self.api_url}/api/import",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
```

The constructor removes a trailing slash so this input:

```text
http://127.0.0.1:8000/
```

does not produce:

```text
http://127.0.0.1:8000//api/import
```

The payload is serialized once and placed in one request body. There is no
per-note loop.

### 17. Preserving useful API errors

The client handles an HTTP error like this:

```python
except HTTPError as exc:
    try:
        error_payload = json.loads(exc.read())
        detail = error_payload.get("error", {}).get("message")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        detail = None
    message = detail or exc.reason or "request failed"
    raise RuntimeError(f"API rejected the import: {message}") from exc
```

It prefers the application's structured message:

```text
note at index 1 requires a non-empty title
```

If the response is not readable JSON, it falls back to the HTTP reason. If that
is also unavailable, it uses `request failed`.

The `raise ... from exc` syntax preserves the original `HTTPError` as the cause.
That helps debugging without exposing a low-level traceback as the only user
message.

### 18. Refusing to trust a malformed success response

After a nominally successful HTTP response, the client checks:

```python
if (
    not isinstance(result, dict)
    or not isinstance(result.get("imported"), int)
    or not isinstance(result.get("notes"), list)
):
    raise RuntimeError(
        "Field Notes API returned an invalid import response"
    )
```

Without this guard, a response such as:

```json
{"message": "probably worked"}
```

could reach the printing code and either crash confusingly or be presented as a
successful import.

This is boundary validation in the opposite direction: the server validates
client input, and the command validates the minimum response contract it relies
on.

### 19. Reading JSON locally without duplicating domain rules

The command's file helper is:

```python
def read_import_payload(path: str | Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            f"Could not read import file {path}: {exc}"
        ) from exc
```

This function answers only:

```text
Can this path be read as UTF-8 JSON?
```

It does not answer:

```text
Is this a valid Field Notes import?
```

That second question remains with the server-side validator.

### 20. The command's visible success point

The command does not print success before the request:

```python
client = ApiImportClient(args.api_url)
result = client.import_payload(read_import_payload(args.path))
print(f"Imported {result['imported']} notes")
for note in result["notes"]:
    print(note)
```

Evaluation order is important:

```text
read file
    -> wait for complete API result
    -> validate response shape
    -> only then print Imported N notes
```

If any earlier stage raises, the success line is never executed.

## Code-reading exercises

These questions are useful when reviewing the excerpts on paper.

1. In `create_repository`, what changes if the conditional uses
   `database_path or get_data_file()` instead of an explicit `is None` check?
2. Why does `create_service` return the repository separately when the service
   already contains it?
3. Which side effect is prevented by parsing the port before constructing the
   repository?
4. Why is the socket-bind exception handler responsible for closing the
   repository?
5. What product lie would a silent fallback to `NoteRepository()` create?
6. What does a fresh server process prove that a second repository object in the
   same process does not?
7. Why can `repository.add()` be correct while a loop of three `add()` calls is
   not atomic?
8. Why does an imported `NoteDraft` have a timestamp but no ID?
9. What semantic information would be lost if the CLI rebuilt the import payload
   after local validation?
10. Why is a transaction insufficient to make an uncertain network retry safe?
11. What is the difference between rejecting an invalid batch before storage and
    rolling back after the second insert statement fails?
12. Why should an empty import return 200 rather than 201?
13. Which `ValueError` exceptions belong to the client, and which would indicate
    a server/storage failure?
14. What evidence would you need before changing the export arrow from amber to
    green?

The recurring pattern behind all of them is:

```text
make ownership explicit
validate before irreversible side effects
connect one authoritative state path
pair every success proof with a controlled failure
claim only the boundary the evidence actually crossed
```
