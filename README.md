# Field Notes

Field Notes is a small local-first research note workspace. It has a Python API and a browser UI.

## Product requirements

- Create, list, search, and delete notes.
- Notes have a title, body, tags, and creation timestamp.
- Tags should be normalized consistently regardless of whether they are created through the API or imported from a file.
- The browser UI should use the API rather than maintaining a second source of truth.
- The application is intended to run locally by default, but the API boundary should be explicit enough that it could later be hosted.
- Errors should be visible to the user; failed writes must not appear successful.

## Run

```bash
python3 -m fieldnotes.server
```

Then open `web/index.html`.

The API runs at `http://127.0.0.1:8000`.

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Repository status

The project is in a late prototype stage. The next milestone is a small internal beta. Avoid broad rewrites unless they solve a demonstrated problem.

See `docs/ARCHITECTURE.md` and `docs/STATUS.md` for implementation notes.
