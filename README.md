# Bootwitch Doctor

> **A multi-agent architecture repair experiment**

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
- Reject invalid later records before storage changes begin.
- Roll back the whole batch when storage fails after an insert has started.
- Refuse corrupt or incompatible databases instead of silently replacing them
  or falling back to temporary memory.

The browser and import command use the running API as their shared authority.
The in-memory repository remains as a fast test adapter; the application runtime
uses SQLite.

## Requirements

- Python 3.11 or newer
- Node.js only for the optional frontend syntax check
- No third-party runtime packages

## Run locally

Start the API from the repository root:

```bash
python3 -m fieldnotes.server
```

In a second terminal, serve the browser files:

```bash
python3 -m http.server 8080 --directory web
```

Open `http://127.0.0.1:8080`.

The API binds to `127.0.0.1:8000` and stores notes in
`./data/fieldnotes.sqlite3` by default. Runtime databases and SQLite sidecars are
ignored by Git.

Configuration:

```bash
FIELDNOTES_DATA=/path/to/notes.sqlite3 python3 -m fieldnotes.server
FIELDNOTES_PORT=9000 python3 -m fieldnotes.server
```

The static browser currently targets port 8000, so the custom-port setting is
most useful for direct API and CLI work until the same-origin runtime is added.

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

## Verify the project

```bash
./scripts/check.sh
```

The check compiles the Python package, checks frontend JavaScript syntax when
Node.js is available, and runs the complete unittest suite. The first
multi-agent repair milestone passes 89 tests, including real CLI, HTTP,
controlled-failure, and process-restart coverage.

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

The durable data path is complete for the current milestone. The next focused
work is portable atomic export, stricter local HTTP mutation rules, coordinated
browser request state, browser-level testing, and one coherent local UI/API
startup path. Those assignments are mapped in
[`agents/NEXT_WAVE.md`](agents/NEXT_WAVE.md).
