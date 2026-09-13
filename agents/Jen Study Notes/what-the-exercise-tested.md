# What Bootwitch Doctor Was Really Testing

> This chapter combines the repair record with the challenge designer's
> retrospective. The retrospective was disclosed after the first repair wave,
> so the agents could not use it as an answer key while investigating.

## The short version

Bootwitch Doctor did not begin as a normal bug-fix exercise. The repository was
deliberately built without one trustworthy source of truth. Its README, status
notes, architecture documents, tests, configuration, and implementation told
different versions of the system.

The real question was not:

> Which lines of code are broken?

It was:

> What is this system supposed to do, which evidence should we trust, and what
> must be connected for the user-visible result to be real?

That is why backward tracing worked so well. Starting with a visible outcome,
such as "the imported notes still exist after restart," forced every required
connection into view.

## The deliberate traps

The challenge designer later disclosed roughly 21 intended findings. They fell
into a few recurring categories.

### Competing contracts

The repository disagreed about:

- SQLite persistence versus in-memory storage;
- `createdAt` versus `created_at` timestamps;
- several incompatible error shapes;
- package and source versions;
- ports 8000 and 8080;
- `FIELDNOTES_PORT` versus `FIELD_NOTES_PORT`; and
- what delete support actually meant.

The important lesson was not to choose whichever contract appeared first. We
had to reconstruct the intended product behavior, select one canonical
contract, and then make producers, consumers, tests, and documentation converge
on it.

### Functionality that looked connected but was not

The original import command created a private in-memory repository, loaded
notes into it, printed them, and exited. The command could look successful while
changing nothing in the running application.

Likewise, persistence-related configuration existed even though the server did
not use persistent storage. Delete traveled through several layers, but the
repository implementation always returned `False`.

These are examples of **connection failures**. The nearby components can be
valid while the product claim remains false.

### False success in the browser

Some UI paths skipped the shared API client and called `fetch` directly. Save
could display success before its request completed. Delete could remove a note
from the page without checking whether the server had deleted it.

The product rule is simple:

> User-visible success should follow accepted system state, not merely a click
> or an attempted request.

### Duplicate domain rules

Two paths normalized the same tag differently:

```text
Deep Learning -> deep-learning
Deep Learning -> deep_learning
```

Both transformations are plausible. The architectural failure was allowing two
definitions of canonical behavior to coexist.

### Documentation that described an aspirational system

The architecture document claimed SQLite, serialized repository operations,
durable writes before success, restricted CORS, and standardized errors. The
running system instead used mutable process-local memory, a threaded server,
wildcard CORS, and inconsistent error handling.

This made documentation part of the evidence, but not automatic proof. The
runtime still had to be traced.

### Less obvious review findings

The challenge also included:

- an abandoned compatibility adapter that acted as evidence of an incomplete
  migration;
- configuration values that did not affect runtime behavior;
- missing frontend checks in the main verification path; and
- unsafe insertion of stored note content through `innerHTML`, creating a
  stored cross-site scripting risk.

The security issue mattered because it sat outside the most obvious persistence
and architecture failures. A deep architecture investigation still needs a
wide enough field of view to notice unsafe trust boundaries.

## Why the repair order mattered

The challenge had an intended dependency order:

```text
settle the public contracts
        ↓
settle canonical domain behavior
        ↓
decide what persistence means
        ↓
connect the runtime to that storage
        ↓
repair user-facing success behavior
        ↓
update documentation to match reality
```

Without this order, agents could make individually reasonable changes that
contradicted one another. One could preserve `createdAt` through an adapter
while another standardized everything on `created_at`. More parallel work would
then produce more drift, not more progress.

## How the repair went beyond the answer key

The planted challenge was mainly testing whether we could identify conflicting
contracts, reconstruct the runtime, and repair it in a defensible order. The
first wave went further and built:

- guarded SQLite durability;
- close, reopen, and complete process-restart proof;
- schema identity and incompatible-database protections;
- an atomic batch API and one-request CLI import;
- complete-payload validation;
- transactional rollback and clean retry proof;
- concurrency regression coverage; and
- real subprocess and HTTP verification.

The original repository had 9 tests. The completed first-wave check had 89.
The number is memorable, but the important improvement was the strength of the
evidence: the new tests crossed HTTP, CLI, process, restart, persistence,
failure, and concurrency boundaries.

## What Jennifer's approach demonstrated

Jennifer's main contribution was not writing five agents a list of files to
change. It was turning uncertainty into an inspectable coordination system.

She:

- asked for independent reviews before implementation;
- used architecture diagrams to compare current, backward-traced, and proposed
  flows;
- noticed that grey components could pass while adjacent red connections still
  broke the product;
- chose connection repair as the first priority;
- divided ownership by architectural boundary;
- kept one integration role responsible for accepted contracts;
- asked for evidence and handoff notes from each lane; and
- repeatedly redrew the forward and backward traces as changes landed.

This is **multi-agent orchestration** with architecture, dependencies, and
acceptance gates. The agents supplied parallel inspection and implementation;
Jennifer supplied the problem framing, sequencing, synthesis, and decisions
that made their work converge.

## The study lesson

The boxes in a diagram are components. The arrows are contracts, state flow,
and runtime composition. A system works only when both are true.

The same principle applied to the repair team. Five capable agents were not, by
themselves, a coherent engineering process. Shared contracts, bounded
ownership, dependency ordering, integration review, and independent
verification connected them into one.

