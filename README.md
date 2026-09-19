# Bootwitch Doctor

> **A multi-agent architecture repair experiment**

**Jennifer Naomi Nguyen** · agent orchestration · built with Claude Code and Codex

Bootwitch Doctor documents how I coordinated five coding agents to diagnose and
repair a deliberately chaotic repository. The repair subject, **Field Notes**,
is a small local-first workspace for capturing research notes before they are
polished enough for a report, wiki, or project document.

The experiment started by tracing the application backward from what a user
could actually observe. From there, each agent received one architectural
boundary to investigate or repair. I used shared diagrams, acceptance gates,
and repeated forward and backward traces to keep the parallel work connected.
The result is both a working application and a record of the orchestration that
made the repair possible.

Read the illustrated case study in
[`docs/REPAIR_JOURNEY.md`](docs/REPAIR_JOURNEY.md), or inspect the evolving
architecture in
[`agents/shared/ARCHITECTURE_MAPS.md`](agents/shared/ARCHITECTURE_MAPS.md).

## What works

- Create, list, search, and delete notes through the browser or API.
- Store titles, plain-text bodies, normalized tags, and UTC timestamps.
- Keep committed notes and deletions across complete server restarts.
- Import a JSON file as one all-or-nothing batch.
- Export readable UTF-8 JSON atomically and recover it into a separate database.
- Reject invalid later records before storage changes begin.
- Roll back the whole batch when storage fails after an insert has started.
- Refuse corrupt or incompatible databases instead of silently replacing them
  or falling back to temporary memory.
- Serve the browser and API from one loopback origin, reject foreign browser
  mutations, and require JSON media types on JSON mutation routes.
- Preserve newer drafts and search results when browser requests finish out of
  order.

The browser and import command use the running API as their shared authority.
The in-memory repository remains as a fast test adapter; the application runtime
uses SQLite.

## Requirements

- Python 3.11 or newer
- Node.js only for the optional frontend syntax check
- No third-party runtime packages

## Run locally

Start the Field Notes UI and API from the repository root:

```bash
python3 -m fieldnotes.server
```

Open `http://127.0.0.1:8000`. The same loopback-only process serves the browser
files and API, so there is no second local server to start or keep alive.

The application binds to `127.0.0.1:8000` and stores notes in
`./data/fieldnotes.sqlite3` by default. Runtime databases and SQLite sidecars are
ignored by Git.

Configuration:

```bash
FIELDNOTES_DATA=/path/to/notes.sqlite3 python3 -m fieldnotes.server
FIELDNOTES_PORT=9000 python3 -m fieldnotes.server
```

The browser uses same-origin API paths, so `FIELDNOTES_PORT` changes the UI and
API port together. Open the corresponding loopback URL after changing it.

## Import notes

With the API running:

```bash
python3 tools/import_sample.py data/sample.json
```

The file format is UTF-8 JSON with a top-level `notes` array:

```json
{
  "notes": [
    {
      "title": "Plate review",
      "body": "Check the edge wells before repeating the run.",
      "tags": ["assay review"],
      "createdAt": "2026-09-12T20:30:00Z"
    }
  ]
}
```

The command sends the complete document to `POST /api/import`. The server owns
semantic validation, and SQLite publishes the batch in one transaction.

## Export and recover notes

With the application running:

```bash
python3 tools/export_notes.py notes-backup.json
```

The command reads `GET /api/export` through the running application and writes a
temporary sibling before atomically publishing the destination. It refuses to
overwrite an existing file unless `--replace` is supplied intentionally.

The exported top-level `notes` document is accepted by the import command. A
round-trip process test exports a populated database, imports into a separate
empty database, restarts the destination server, and compares titles, bodies,
tags, and timestamps. IDs remain database-local.

## Verify the project

```bash
./scripts/check.sh
```

The check compiles the Python package, checks frontend JavaScript syntax, runs
two deterministic browser-state tests when Node.js is available, and runs the
complete 110-test Python suite. The evidence includes real CLI, HTTP, atomic
filesystem publication, controlled-failure, and process-restart coverage.

Run the real Chrome acceptance flow separately:

```bash
node scripts/browser_acceptance.mjs
```

It drives create, delayed save, out-of-order search, refresh failure, delete,
desktop layout, and narrow layout through the locally running application.

## Repository map

```text
fieldnotes/    domain, API, composition, and repository implementations
tools/         JSON import command
web/           static browser interface
tests/         unit, contract, integration, subprocess, and restart tests
docs/          current product and engineering documentation
agents/        coordination packets, raw handoffs, and architecture maps
diagrams/      visual snapshots and the connection-first repair plan
```

## Tech stack and AI collaboration

The application uses Python 3.11, the Python standard-library HTTP server, SQLite, browser-native HTML/CSS/JavaScript, Bash checks, and Python unittest coverage.

Since 2025, I’ve been making software in active collaboration with AI coding systems across providers, and I want to do more of it. I built Bootwitch Doctor with five Codex coding agents from OpenAI, using the project to turn multi-agent architecture repair into a method I could inspect, test, and reuse.

## Documentation

- [`docs/README.md`](docs/README.md): documentation map and reading order
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): system structure, flows, and
  failure boundaries
- [`docs/TECHNICAL.md`](docs/TECHNICAL.md): implementation readthrough
- [`docs/API.md`](docs/API.md): current HTTP contract
- [`README_INTENT.md`](README_INTENT.md): product intent and acceptance target
- [`PROJECT_STATE.md`](PROJECT_STATE.md): current handoff and next work

The five-agent experiment is summarized in
[`CHALLENGE_UPDATE.md`](CHALLENGE_UPDATE.md). The before, intermediate, and
after story is in [`docs/REPAIR_JOURNEY.md`](docs/REPAIR_JOURNEY.md).

## Reusable outcome: Bootwitch AGENTS

The repair produced more than a working application. I turned the coordination
method into [Bootwitch AGENTS](https://github.com/naomijnguyen/bootwitch-agents),
an installable skill for running future multi-agent repository sessions.

The skill creates bounded assignments, project-specific notes, append-only
cross-agent messages, evidence-backed handoffs, and forward and backward
architecture traces. A session overview agent updates the README, architecture
diagrams, and technical notes for every project touched by the work. One
architecture lead reviews the combined evidence before handling authorized
commits, versioning, and pushes.

[View the source](https://github.com/naomijnguyen/bootwitch-agents) ·
[Download v0.2.0](https://github.com/naomijnguyen/bootwitch-agents/releases/tag/v0.2.0)

## Next pass

The two repair waves are complete for the local beta contract. The original
broken fixture remains reproducible at
[`1884f4d`](https://github.com/naomijnguyen/doctor-repo-repair/tree/1884f4d),
while the default branch remains runnable and repaired.

Explicitly deferred work includes retry idempotency after an unknown
post-commit response, broader multi-process write guarantees, and a hosted trust
model beyond this loopback-only application.
