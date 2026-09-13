# Durable SQLite Storage: Jen's Study Notes

> **Reading note:** This chapter begins at the isolated-adapter stage. The server
> now uses the SQLite adapter and restart persistence is verified. See
> [`README.md`](README.md) for the current status and recommended study order.

## The short version

Field Notes used to remember notes the way a person remembers something while
holding it in their head: perfectly well until the process stops.

The original repository stored notes in a Python list:

```text
running server
    |
    v
Python list: [Note 1, Note 2, Note 3]
```

Restarting the server created a new list:

```text
new server process
    |
    v
Python list: []
```

The new SQLite adapter gives us a repository that can put those records on disk.
We have proved that it can save a note, close the database, reopen it, and return
the same note with the same ID and timestamp.

One important boundary remains: **the server does not use this adapter yet**.
We built and tested the durable component in isolation so that the storage
behavior is trustworthy before it becomes the application's source of truth.

## What an adapter is doing here

The service knows how to ask a repository for four things:

```python
repository.list()
repository.add(title, body, tags)
repository.delete(note_id)
repository.clear()
```

It does not need to know whether the repository uses a Python list, SQLite, or
something else. Each storage implementation is an **adapter**: it translates the
same application operations into the mechanics of a particular storage system.

```text
                    +-> in-memory adapter -> Python list
service contract ---|
                    +-> SQLite adapter ----> database file
```

This separation lets narrow service tests keep using the fast in-memory adapter.
The real runtime can later select SQLite without teaching the service SQL.

We did not add a formal abstract base class or protocol yet. Python's structural
contract is enough for this stage: if both adapters provide the required methods
and pass the same conformance tests, the service can use either one.

## What is actually in the SQLite database

SQLite stores each note as one row in a `notes` table:

```text
notes
+----+-------------------+------+----------------+--------------------------+
| id | title             | body | tags           | created_at               |
+----+-------------------+------+----------------+--------------------------+
| 1  | Pond observation  | ...  | ["field-work"] | 2026-09-13T...+00:00    |
+----+-------------------+------+----------------+--------------------------+
```

The schema gives us:

- an integer primary key for `id`;
- required text columns for title and body;
- tags encoded as JSON text;
- a required UTC creation timestamp.

Tags remain a `list[str]` at the repository boundary. The SQLite adapter turns
that list into JSON when writing and back into a fresh list when reading:

```text
Python:  ["field-work", "pond-life"]
                   |
                   v
SQLite:  '["field-work", "pond-life"]'
```

That choice keeps SQL representation details out of the service. If we later
need sophisticated tag queries, we can revisit the schema based on a real use
case rather than prematurely creating tag and join tables.

## The transaction story

A transaction is the database's protected workspace for a change. The adapter's
write sequence looks like this:

```text
BEGIN IMMEDIATE
  insert the note
  read the stored row back
COMMIT
```

The insert is not considered durable until `COMMIT` succeeds. If any operation
inside that boundary fails, the adapter runs `ROLLBACK`:

```text
BEGIN IMMEDIATE
  insert the note -> database error
ROLLBACK
```

After rollback, the database looks as though that attempted write never
happened.

`BEGIN IMMEDIATE` tells SQLite to reserve the ability to write at the beginning
of the transaction. That makes contention appear at a predictable boundary,
rather than allowing two operations to do preliminary work and collide later.
The adapter also has a Python lock so threads sharing this one repository object
do not use its connection simultaneously.

## How we proved rollback instead of merely assuming it

The failure test installs a temporary database trigger that rejects one title:

```text
existing note -> already committed
"blocked"     -> trigger forces an insert error
```

Then the test checks three things:

```text
1. The existing note is still present.
2. The rejected note is absent.
3. A later valid note can still be saved.
```

The later valid note receives ID 2. The failed transaction does not leave a
half-written record or consume an ID. This is stronger evidence than checking
only that an exception was raised: it verifies the database state after failure
and confirms the connection can recover.

## Reopen persistence: the essential proof

Saving a row and immediately reading it through the same object would prove only
that one live connection can see its own work. Durable storage needs a harder
test:

```text
open database
  add Note 1
close database

open the same database again
  list notes -> Note 1 is still present
```

The test compares the complete returned note, including its ID, title, body,
tags, and UTC timestamp. A similar test deletes a note, closes the database, and
confirms after reopening that the deletion also survived.

This is why "the SQL insert ran" and "the note is durable" are not synonymous.
The close-and-reopen boundary is where persistence earns its name.

## The surprisingly sneaky `clear()` detail

The in-memory repository resets its ID counter when cleared:

```text
add note  -> ID 1
add note  -> ID 2
clear
add note  -> ID 1
```

SQLite keeps its autoincrement counter in a separate internal table called
`sqlite_sequence`. This means the obvious implementation is subtly incompatible:

```sql
DELETE FROM notes;
```

That removes the rows, but the next note might receive ID 3 instead of ID 1.

To match the existing repository contract, `clear()` performs both operations
inside one transaction:

```text
delete every note row
delete the notes entry from sqlite_sequence
commit both changes together
```

This was the most interesting parity trap in the implementation. "Both stores
are empty" is not enough if their next observable behavior differs.

## Defensive copies and ownership

Suppose a caller does this:

```python
note = repository.add("Pond", "...", ["field-work"])
note.tags.append("changed-outside-the-repository")
```

That must not silently mutate stored data. The in-memory adapter already returns
copies so callers cannot reach into repository-owned state. SQLite naturally
constructs a new `Note` and tag list from each row, preserving the same safety
property.

The shared conformance tests deliberately mutate:

- the original tags supplied to `add()`;
- the note returned by `add()`;
- a note returned by `list()`;
- the list returned by `list()` itself.

After all of that mischief, the stored note must remain unchanged.

## Schema versions and visible failure

The adapter records schema version 1 using SQLite's `PRAGMA user_version`.

That tiny marker matters when the application evolves. A future adapter can
distinguish a known old schema that can be migrated from an unknown schema it
must not guess about.

Current behavior is intentionally conservative:

```text
new empty database          -> create schema version 1
existing schema version 1   -> open normally
version 0, matching table   -> preserve rows and adopt as version 1
version 0, different table  -> fail without changing anything
version 0, unrelated tables -> fail without changing anything
version 0, unreadable rows  -> fail without changing anything
version 1, no notes table   -> fail without creating a replacement
unknown schema version 99   -> fail visibly
invalid non-SQLite contents -> fail visibly
```

The important correction here is that version 0 means **unversioned**, not
**empty**. An older application—or even an unrelated tool—could already have
created a table named `notes` without setting `user_version`.

The first implementation used `CREATE TABLE IF NOT EXISTS` and then stamped
version 1. That phrase sounds cautious, but on an incompatible existing table it
really means:

```text
"A table already exists, so do nothing"
                    +
"Mark the database as if our current schema exists"
```

That would bless an unknown structure without migrating it. The constructor now
inspects the existing table before making any change. If the columns,
constraints, primary key, or autoincrement behavior differ, construction fails
and a regression test confirms all three pieces remain unchanged:

```text
user_version       -> still 0
original table SQL -> identical
existing rows      -> identical
```

The opposite branch is tested too. If an unversioned table exactly matches the
supported schema, its existing note is preserved, the database is marked version
1, and the next note continues at the next ID. This is a small example of a good
migration principle: recognize what you know, preserve what you do not, and
never convert uncertainty into confidence merely by changing a version number.

There is one more layer: matching columns do not prove matching data. SQLite is
flexible about stored values, and tags are JSON text, so the adapter now decodes
every existing row before adoption. A row containing malformed tag JSON, a blob
where note text belongs, or a non-UTC timestamp makes the database unreadable
under the version-one contract. Adoption stops before the version changes.

This gives initialization four useful identities:

```text
new database
  no user tables
  -> safe to create Field Notes schema

adoptable Field Notes database
  exact notes schema + every row readable
  -> safe to preserve data and mark version 1

damaged Field Notes database
  recognizable schema + unreadable rows
  -> refuse and preserve evidence for recovery

someone else's or incomplete database
  unrelated user tables, or version 1 without notes
  -> refuse instead of claiming ownership
```

That last distinction is especially protective. Automatically adding a `notes`
table to someone else's SQLite file would technically “work,” but it would be an
ownership mistake. Likewise, recreating a missing table in a version-one Field
Notes database would turn evidence of damage into a clean-looking empty store.

It does not overwrite an invalid file and pretend it created a fresh database.
For a local-first notes application, silently replacing an unreadable store
would be a particularly nasty form of apparent data loss.

## What concurrency evidence means—and does not mean

The adapter was exercised with eight worker threads adding 320 notes through one
repository object. The resulting IDs were exactly the integers from 1 through
320, with no duplicates or corrupt records.

That proves the adapter safely serializes concurrent operations through its
shared connection. It does not yet prove every possible multi-process workload
or establish performance under heavy contention. The intended application is a
small local workspace, so the current test is proportionate to the runtime we
are building.

## Why the server is still in-memory

Right now we have built a safe bridge from the SQLite adapter to the database,
but we have not redirected application traffic onto it:

```text
current runtime:
server -> service -> in-memory repository -> Python list

isolated and verified:
SQLite repository -> database file
```

This staged approach makes failures easier to locate. If we wired the server,
invented the schema, and tested restart behavior all at once, a failing restart
test could implicate configuration, shutdown, server composition, SQL, or the
repository contract. Now the storage component has its own evidence before the
runtime connection changes.

## The next plans

The next storage-related connection should be runtime composition:

```text
configured data path
        |
        v
repository factory
        |
        v
SQLiteNoteRepository
        |
        v
server and service
```

After that wiring, the important black-box proof is larger:

```text
start server
POST a note through HTTP
stop server
start server again
GET notes -> the note is still there
```

That will prove the complete application path, not merely the isolated adapter.

Atomic import came after durable runtime storage. Its key requirement could not
be implemented by calling the original `add()` repeatedly:

```text
add A -> transaction committed
add B -> transaction committed
add C -> failure
```

By then A and B would be permanent. The repositories now have a dedicated
`add_many()` operation that encloses every note in one transaction:

```text
BEGIN
  add A
  add B
  add C
COMMIT all

or, on any failure:

ROLLBACK all
```

The failure test deliberately rejects the second SQLite insert after the first
insert statement has already run. The transaction rolls back the entire batch,
keeps notes that existed before it, leaves no consumed batch IDs behind, and can
be retried successfully. That is the difference between “validation caught a
problem early” and “the database recovered after work had actually begun.”

## The evidence we have now

The focused SQLite test set covers:

- adapter parity with memory;
- database initialization and schema versioning;
- create and delete persistence across close and reopen;
- UTC timestamp preservation;
- ID allocation and reset behavior;
- defensive copies;
- rollback and recovery after a forced failure;
- concurrent additions;
- invalid database and unknown-version failures.

The original isolated storage gate passed **16 tests**. In the current shared
working tree, the complete repository check passes **80 tests**. The later work
now includes durable runtime composition, real subprocess restart evidence,
atomic `add_many()` behavior, the batch API route, and a one-request import
client. Agent 2's initialization pass itself did not edit server composition.

The honest status is therefore:

> The SQLite repository is implemented and independently trustworthy. Field
> Notes itself is not durable until the runtime is deliberately connected to it
> and persistence is proved through the public application path.
