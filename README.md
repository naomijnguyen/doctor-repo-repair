# Field Notes

Field Notes is a small local-first research note workspace with a Python API,
browser UI, and durable SQLite storage. It is a deliberately compact prototype:
create, list, search, delete, and atomic JSON import work today.

## Product requirements

- Create, list, search, and delete notes.
- Notes have a title, body, tags, and creation timestamp.
- Tags should be normalized consistently regardless of whether they are created through the API or imported from a file.
- The browser UI should use the API rather than maintaining a second source of truth.
- The application is intended to run locally by default, but the API boundary should be explicit enough that it could later be hosted.
- Errors should be visible to the user; failed writes must not appear successful.
- Successful writes and deletes should survive process restarts.
- A multi-note import should commit completely or leave stored state unchanged.

## Run locally

Start the API from the repository root:

```bash
python3 -m fieldnotes.server
```

In a second terminal, serve the browser UI:

```bash
python3 -m http.server 8080 --directory web
```

Open `http://127.0.0.1:8080`. The UI calls the API at `http://127.0.0.1:8000`.

Notes are stored in `./data/fieldnotes.sqlite3` by default. Set
`FIELDNOTES_DATA` to use another database path and `FIELDNOTES_PORT` to change
the API port. The static browser client still targets port 8000, so custom-port
browser support remains a follow-up.

## Import notes

With the API running:

```bash
python3 tools/import_sample.py data/sample.json
```

The command sends one complete payload to `POST /api/import`. Validation happens
before storage begins, and SQLite commits the batch in one transaction.

## Test

```bash
./scripts/check.sh
```

The check runs Python compilation, frontend syntax checks when Node.js is available, and the Python test suite.

## Repository status

Durable runtime composition and atomic import are implemented and verified
through real CLI, HTTP, rollback, retry, and process-restart tests. The next
milestones are portable atomic export, browser request-state repair, and a
cleaner same-origin local runtime.

See `docs/API.md` for the current wire format, `docs/ARCHITECTURE.md` for
component boundaries, `PROJECT_STATE.md` for the active handoff, and
`agents/Jen Study Notes/README.md` for the five-agent repair walkthrough.
