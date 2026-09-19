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
- Empty, loading, saving, searching, and failure states are visible.

## Known gaps

- The UI has syntax checks but no browser-level interaction tests.
- The CORS policy is designed for local use, not hosted deployment.
- Mutation requests do not yet reject disallowed origins or wrong media types.
- Slow mutation and refresh requests can still produce stale UI state.
- Portable atomic export and recovery are not implemented.

Before beta:
- implement atomic export and round-trip recovery
- enforce the local HTTP trust boundary and consistent JSON method errors
- coordinate browser mutation, refresh, and search state
- add browser-level coverage for create, search, delete, and error states
