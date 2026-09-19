# Status

Updated: 2026-09-18

## Working now

- The API can create, list, search, and delete notes.
- The configured SQLite repository is the running server's durable state owner.
- Create and delete survive complete server-process restarts.
- The import command sends one complete payload through the running API.
- Import validates before mutation and commits through one SQLite transaction.
- Controlled mid-batch failure rolls back completely and supports a clean retry.
- The browser uses one API module and reports request failures instead of presenting them as success.
- The browser renders note content as text, so note fields cannot inject markup.
- One loopback process serves both browser files and API routes; the browser uses
  same-origin API paths.
- Portable export uses the running API, publishes atomically, refuses accidental
  overwrite, and round-trips through a separate database and restart.
- Foreign and opaque browser origins cannot mutate state; JSON mutation routes
  require `application/json`; unsupported API methods stay inside the JSON
  error contract.
- Slow saves preserve newer draft text, late reads cannot overwrite newer
  results, and refresh failure is distinct from confirmed mutation success.
- A repeatable headless-Chrome acceptance runner covers create, search, delete,
  failure state, and desktop/narrow layouts.
- Empty, loading, saving, searching, and failure states are visible.

## Known limits

- The trust boundary is local/loopback, not a hosted deployment policy.
- Import is not idempotent after an ambiguous lost post-commit response.
- Repository concurrency evidence is scoped to shared-process threads.
- Chrome acceptance is a separate explicit command rather than a dependency of
  the portable Python check.

Current gate: 110 Python tests, 2 JavaScript state tests, and the real Chrome
acceptance flow.
