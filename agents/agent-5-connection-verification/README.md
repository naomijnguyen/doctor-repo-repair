# Agent 5: Independent Connection Verifier

## Assignment

Verify the arrows between processes and components. Component tests can show that a repository or importer works alone; this role establishes whether the user-visible outcome reaches the intended state owner and survives the intended lifetime.

## Work Area

- Black-box persistence tests using real process restarts.
- Cross-process import visibility tests.
- Atomic-import failure tests at the application boundary.
- Export-to-import recovery tests.
- Runtime-data and Git hygiene review.
- Findings recorded in `NOTES.md`.

## Keep Outside This Assignment

- Production code edits.
- Choosing the repository contract.
- Changing API semantics.
- Repairing a failed implementation directly.

## Starting Facts

- The current unit and syntax suite passes 34 tests.
- The import command can add notes to the running server.
- Notes disappear when that server restarts.
- Existing tests mostly exercise Python components directly rather than complete process boundaries.

## Deliverable

Independent evidence for every new connection, including one expected success and one controlled failure, plus a report of any newly exposed dependency.

