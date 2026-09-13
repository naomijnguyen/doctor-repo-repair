# Status

Updated: 2026-09-10

- UI/API integration mostly works.
- Search is implemented.
- Delete button is still blocked on backend support.
- Persistence is currently an in-memory prototype; SQLite is planned after beta feedback.
- Canonical timestamp field is `created_at` for now.
- Local server currently uses port 8000.
- Known issue: imported tags sometimes differ from API-created tags.

Before beta:
- settle API field naming
- ensure failed writes are surfaced in UI
- consolidate project-state documentation
