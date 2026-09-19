# Project State

Last reviewed: 2026-09-18

Current direction:
- Treat the implementation and accepted integration ledger as the source of truth.
- One loopback server serves the browser and API on port 8000 by default.
- The running API stores notes in configured SQLite storage.
- Create, delete, and atomic import survive complete process restarts.
- Portable export publishes atomically and recovers through import into a
  separate database while preserving public fields and timestamps.
- Public API timestamps use `createdAt`.
- Same-origin browser mutations require JSON where applicable; foreign and
  opaque origins cannot mutate state.
- Browser reads use one generation policy, and completed saves preserve newer
  draft text.
- The frontend centralizes requests in `web/api.js` and displays backend failures.

Current limitations:
- The trust policy is intentionally loopback/local and is not a hosted
  deployment policy.
- Import rollback is atomic, but ambiguous retry after a lost successful response is not idempotent.
- Concurrency evidence covers threads sharing one repository object, not
  arbitrary external multi-process writers.

Current verification gate:
- `./scripts/check.sh`: 110 Python tests plus 2 JavaScript state tests.
- `node scripts/browser_acceptance.mjs`: real Chrome workflow at desktop and
  narrow widths.
