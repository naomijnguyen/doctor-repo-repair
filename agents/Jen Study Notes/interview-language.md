# Bootwitch Doctor Interview Language

This is a speaking guide, not a script you have to memorize. Learn the shape of
the story, keep the terms that help you be precise, and say the rest naturally.

## The one-sentence version

> I coordinated five AI coding agents to repair a deliberately inconsistent
> notes application by mapping its real architecture, dividing work along
> dependency boundaries, and verifying the repaired CLI-to-HTTP-to-SQLite path
> across process restarts and controlled failures.

## A 30-second answer

> Bootwitch Doctor was a multi-agent architecture repair experiment. The repo
> had working-looking components, but its tests, docs, configuration, and
> runtime contradicted one another. I had five agents inspect it, then split the
> repair into durable storage, atomic import, runtime wiring, independent
> verification, and integration ownership. The key idea was distinguishing a
> component that works from a connection that works. We finished with 89 tests,
> including real CLI, HTTP, rollback, concurrency, and restart coverage.

## A 90-second answer

> I was given a deliberately messy local notes application and a challenge: see
> whether I could coordinate five agents working in the same repository. I did
> not start by sending all five into the code. First I asked for independent
> reviews and mapped the architecture as implemented, the user-visible flow,
> and a backward trace from the result we needed.
>
> That exposed the main failure: several components worked in isolation but
> were not connected. The importer wrote to a private in-memory repository, the
> server used a different in-memory repository, and the documented SQLite path
> was not part of the runtime. Printed success therefore did not mean the
> application had changed, and restart erased the data.
>
> I divided the work by architectural boundary: one agent owned SQLite, one
> atomic batch import, one runtime composition and CLI wiring, one black-box
> verification, and one integration and contract ledger. We repaired the path
> into one request, one service operation, and one SQLite transaction, then
> proved it using the real command and server across complete process restarts.
> We also forced a second-row write failure to verify rollback. What I learned
> was that parallel agents make architectural judgment more important, not less.

## A fuller project walkthrough

Use this structure when the interviewer asks, "Tell me about the project."

### Situation

> The starting repository was intentionally inconsistent. Documentation,
> tests, and implementation described different systems, so there was no single
> source I could trust without checking it against runtime behavior.

### Task

> My job was to coordinate five agents, decide what the application should
> actually guarantee, repair the most important broken path, and produce
> evidence that the integrated system worked rather than collecting five local
> patches.

### Action

> I began with independent triage, consolidated agreements and disagreements,
> and mapped both forward and backward traces. Then I assigned bounded roles
> based on dependencies: storage before runtime wiring, the batch contract
> before CLI integration, and independent process tests after those connections
> existed. I kept one integration lane responsible for accepting shared
> contracts and updating the architecture as the implementation changed.

### Result

> The repaired import path goes from the real CLI through one HTTP batch request,
> complete-payload validation, one service operation, and one SQLite
> transaction. The notes remain visible after a new server process starts. A
> forced write failure rolls the whole batch back, and a clean retry preserves
> the expected IDs. The canonical check grew from 9 tests to 89, with stronger
> evidence across process and failure boundaries.

### Reflection

> The most useful lesson was component proof versus connection proof. A storage
> adapter can pass every unit test while the application still uses a different
> state owner. I now ask not only whether a component works, but whether the
> public entry point reaches it and whether the evidence crosses the boundary I
> am making a claim about.

## How to describe your own role

The clearest honest version is:

> I set the investigation strategy, decided the repair order, assigned
> architectural ownership, consolidated findings, resolved conflicting
> proposals, and chose the acceptance evidence. The agents performed parallel
> source inspection, implementation, and focused testing within those lanes. I
> then reviewed how the pieces connected and had a separate lane verify the
> public path.

Avoid shrinking your role to:

> I asked five agents to fix a repo.

That leaves out the difficult part: determining contracts, dependencies,
ownership, sequencing, and what counted as proof.

Also avoid claiming:

> I personally wrote every implementation line.

You do not need that claim. The project demonstrates system reasoning,
technical direction, evidence-based decisions, and effective use of coding
agents.

## How to answer "How did you use AI?"

> I used AI agents as parallel engineering lanes, not as five independent
> sources of truth. Each agent received a bounded architectural responsibility,
> shared diagrams, acceptance criteria, and a place to record findings. I kept
> an integration lane because locally correct changes can conflict when they
> share an API or storage contract. I also separated implementation from
> black-box verification so success was based on observable behavior rather
> than an agent's report about its own patch.

If they ask what you would change next time:

> I would make the contract ledger and final acceptance matrix explicit even
> earlier. We arrived at that structure during the exercise, and it made later
> handoffs much cleaner.

## Likely technical follow-ups

**Why did the existing tests not settle the intended behavior?**

The challenge deliberately contained tests and documents that encoded
conflicting contracts. A green local test could prove internal consistency with
the wrong assumption. We compared tests with observable product behavior and
selected one canonical contract before making the layers converge.

**Why was adding a SQLite class not enough?**

Because implementation existence is not runtime integration. Persistence only
became a product property when the running server constructed the SQLite
adapter, injected it into the service, closed it correctly, and a new process
could read the committed state.

**Why use one batch request?**

It makes the file import one logical operation. The server can validate the
complete payload and publish it in one transaction instead of committing notes
one request at a time and leaving a partial result if a later request fails.

**Why validate before the transaction if the transaction can roll back?**

Validation rejects predictable client errors before taking a write lock or
starting storage work. The transaction protects against failures that occur
after mutation begins. They protect different boundaries.

**Why `BEGIN IMMEDIATE`?**

It acquires SQLite's write reservation at the start of the transaction. That
keeps another writer from interleaving with the batch and supports the promised
contiguous batch behavior under the tested concurrency case.

**Does atomicity make retries safe?**

No. Atomicity means one attempt either fully commits or has no effect. If the
database commits but the client loses the response, a blind retry can still
duplicate the batch. That is an idempotency problem and would need a request key
or another deduplication contract.

**Why test a complete process restart?**

Closing and reopening one repository proves adapter durability. Starting an
entirely new server process proves that runtime configuration selects the same
database and that the public API sees the state without relying on old process
memory.

**Why use an independent verification agent?**

The implementation agent knows the intended internal path and can accidentally
test its own assumptions. The verifier used the real CLI, HTTP server, database,
and process lifecycle, which reduced confirmation bias and tested public
behavior.

**Why was concurrency part of the first wave?**

Once durable storage and batch IDs became shared state under a threaded server,
interleaving became part of correctness. The regression test races a single
write against a batch and verifies that the batch IDs remain contiguous.

**Why not rewrite the whole application?**

The goal was to repair the most important path while preserving useful existing
boundaries. Small, dependency-ordered changes made it possible to test each new
connection and revise the architecture from evidence.

## Terminology you can reach for

- **Source-of-truth fragmentation:** several files make competing claims about
  current behavior.
- **Contract drift:** producers and consumers expect different shapes or
  semantics at one boundary.
- **Runtime composition:** the concrete dependencies the application selects
  and connects when it starts.
- **Composition root:** the startup location where those dependencies are
  constructed and connected.
- **State owner:** the repository instance holding authoritative application
  state.
- **Atomicity:** one operation becomes completely visible or has no visible
  effect.
- **Durability:** committed state survives the process that created it.
- **Rollback:** a failed transaction restores the previous database state.
- **Idempotency:** repeating a request has the same effect as making it once.
- **Black-box verification:** testing through public entry points without
  relying on private implementation details.
- **Dependency-aware scheduling:** ordering work according to the contracts and
  components each task needs first.
- **Integration ownership:** assigning someone responsibility for deciding
  which shared contracts and combined changes are accepted.
- **Evolutionary architecture:** updating the architecture deliberately as
  implementation and tests reveal real constraints.

## Claims confirmed by the project record

These are safe to use in an interview:

- The starting suite had 9 tests.
- Five primary agent lanes were used.
- The first-wave canonical check passed 89 tests.
- The real importer uses one `POST /api/import` request.
- The server uses configured SQLite storage as its state owner.
- Tests cover complete process restart, rollback after a controlled second-row
  failure, and a single write racing a batch.
- The repaired path preserves canonical public timestamps and normalized tags.
- Export and idempotent retry were explicitly left outside the first-wave
  contract.

## Details to check before making a broader claim

Check the current code, notes, or release before saying:

- every planted trap has been fixed;
- the entire product is production-ready;
- browser behavior has full automated interaction coverage;
- the API is hardened for public internet exposure;
- import retries cannot duplicate data;
- atomic export or disaster recovery is complete; or
- the project has been load-tested beyond its focused concurrency regression.

The accurate phrasing is that the **first-wave import and durability path** was
repaired and verified. That is already a substantial result.

## Practice prompts

Try answering these aloud without reading the sample answer:

1. What was the first clue that this was an architecture problem rather than a
   collection of isolated bugs?
2. Why did you work backward from the visible result?
3. How did you decide what five agents should own?
4. Tell me about a disagreement or contract conflict you had to resolve.
5. What evidence changed a connection from red to green?
6. What is the difference between atomicity and idempotency?
7. Why did the final test count matter less than the boundaries those tests
   crossed?
8. What did you personally contribute that the agents could not provide on
   their own?
9. What would you build or verify in a second wave?
10. How did your scientific training influence your debugging process?

