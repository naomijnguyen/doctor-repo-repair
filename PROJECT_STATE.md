# Project State

Last reviewed: 2026-09-18

Current direction:
- Treat the implementation and accepted integration ledger as the source of truth.
- One loopback server serves the browser and API on port 8000 by default.
- The running API stores notes in configured SQLite storage.
- Create, delete, and atomic import survive complete process restarts.
- Public API timestamps use `createdAt`.
- The frontend centralizes requests in `web/api.js` and displays backend failures.

Current limitations:
- The local CORS policy accepts local HTTP origins and direct-file access; it is not a hosted deployment policy.
- Mutation requests do not yet enforce the origin policy or JSON media type.
- Browser mutation and refresh requests have unresolved ordering edge cases.
- Portable export and export-to-import recovery are not implemented.
- Import rollback is atomic, but ambiguous retry after a lost successful response is not idempotent.

Next application-code pass:
- Implement portable atomic export and recovery evidence.
- Harden the local HTTP trust boundary and unsupported-method behavior.
- Repair browser request ordering and add browser-level interaction coverage.
