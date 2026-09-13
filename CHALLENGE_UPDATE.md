# Bootwitch Doctor: Five Agents, One Chaotic Repository

> **A multi-agent architecture repair experiment**

## The short version

The first repair wave worked.

We used five agent lanes in one shared repository to repair a deliberately messy
local notes application. The goal was not just to make more tests pass. It was to
see whether multiple agents could coordinate around architecture, ownership, and
evidence without turning parallel work into five incompatible solutions.

The key rule was simple: fix missing connections before polishing components
that already carried traffic.

## Where we started

Field Notes had several pieces that looked functional in isolation:

- a browser interface;
- a Python API;
- an in-memory repository;
- an import helper; and
- tests for individual behavior.

But the paths did not agree. The import command could print notes from a private
repository that the server never saw. The server forgot everything on restart.
Import validation checked a whole file, then saved records one at a time, so a
later storage failure could leave a partial import behind.

The first live checkpoint passed 34 tests, but that number did not prove the
connections users depended on.

## How the agents were divided

- **Agent 1** owned architecture, contracts, integration order, and trace updates.
- **Agent 2** built and hardened the SQLite repository.
- **Agent 3** defined and implemented atomic batch import.
- **Agent 4** connected runtime composition and moved the CLI to one batch request.
- **Agent 5** independently tested real commands, HTTP, failures, and process restarts.

Each lane kept detailed notes. Shared contracts stopped for Agent 1 acceptance,
and the team redrew both the forward and backward traces whenever a connection
changed.

## What works now

The repaired path is:

```text
JSON file
  -> real import CLI
  -> one POST /api/import
  -> complete-payload validation
  -> one service operation
  -> one repository add_many operation
  -> one SQLite transaction
  -> committed rows
  -> complete server restart
  -> the same notes through the public API
```

The current canonical check passes **89 tests**, along with Python compilation,
frontend syntax, and diff hygiene.

The evidence includes:

- create and delete persistence across separate server processes;
- safe adoption or rejection of existing SQLite schemas;
- visible failure for corrupt databases without an in-memory fallback;
- one-request CLI import with preserved source timestamps;
- zero mutation when a later input record is invalid;
- deterministic rollback when the second database insertion fails;
- clean retry with no partial rows or consumed IDs; and
- contiguous batch IDs when a single write races the batch.

## What the challenge taught us

The most useful distinction was between a working component and a working
connection. A SQLite class can pass every unit test while the running server still
uses memory. A CLI can print success while writing to an object that disappears
when the command exits.

Parallel agents were most effective when each one owned a specific architectural
arrow, shared contracts were explicit, and another lane verified the result from
outside the implementation. The integration lead was not administrative
overhead; it was what kept five locally correct solutions from drifting apart.

The agents also found each other's narrow misses. Integration review caught
startup ordering, overly broad error classification, and a missing permanent
batch-concurrency regression. Those were repaired before the first wave closed.

## What comes next

The lower data path is durable and atomic. The second wave focuses on:

1. portable atomic export and export-to-import recovery;
2. local HTTP origin and media-type enforcement;
3. consistent JSON behavior for unsupported methods and edge-case IDs;
4. browser request ordering under slow and failed operations;
5. one coherent local UI/API startup path; and
6. independent browser and HTTP acceptance evidence.

The detailed assignments are in `agents/NEXT_WAVE.md`. The full progression is
in `docs/REPAIR_JOURNEY.md`.

## Current repository status

The first repair wave and its documentation are complete in this repository.
The remaining second-wave trust-boundary and browser work is recorded separately
so the verified milestone is not confused with planned work.
