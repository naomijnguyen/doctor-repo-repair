# Field Notes Triage

Working document for independent repository-review passes. This is an evidence log, not yet the consolidated remediation plan.

> **Current-state note (2026-09-12):** This file preserves the investigation in
> chronological order, so many findings and test counts below describe earlier
> snapshots. Durable SQLite runtime composition, atomic one-request import, hold
> regressions, and public restart/rollback evidence are now implemented in the
> 89-test working tree. Use `agents/shared/SHARED_NOTES.md` for the accepted
> integration ledger, `agents/shared/ARCHITECTURE_MAPS.md` for current traces,
> and `agents/NEXT_WAVE.md` for remaining work.

## How to contribute

- Append a new, named review pass under **Agent review passes**. Do not rewrite another reviewer's findings during collection.
- Give every finding a stable ID using the reviewer's prefix, such as `A1-01`.
- Include severity, affected behavior, direct file-and-line evidence, and verification performed.
- Distinguish observed failures from inferred risks.
- Note duplicates or disagreements instead of silently merging them. Consolidation happens after the independent passes are complete.
- Do not implement fixes during triage unless separately requested.

## Severity guide

- **Critical:** Prevents a primary product workflow, creates a meaningful security exposure, or makes the current branch unsuitable for its stated milestone.
- **High:** Breaks an advertised feature, loses data, reports failure as success, or invalidates a major architectural claim.
- **Medium:** Reliability, maintainability, or contract issue likely to affect real use but not necessarily every session.
- **Low:** Limited-scope inconsistency, tooling gap, or cleanup item with modest immediate user impact.

## Repository snapshot

- Review date: 2026-09-12
- Branch: `main`
- Commit: `1884f4d` (`baseline: late prototype handoff`)
- Initial worktree state: clean
- Configured Git remotes: none
- Review mode: read-only
- Stated project stage: late prototype, approaching a small internal beta

## Agent review passes

### A1 — Initial repository audit

Reviewer: Codex primary agent

Scope: repository structure, Git state, Python application, browser UI, tests, CI, configuration, and project documentation.

#### A1-01 — The documented browser workflow is not viable as written

- Severity: **Critical**
- Status: **Observed in code; browser behavior inferred from the platform boundary**
- Affected behavior: launching the UI and creating notes
- Evidence:
  - `README.md:19` tells the user to open `web/index.html` directly.
  - `web/index.html:21` loads `app.js` as an ES module.
  - `web/api.js:9-14` sends cross-origin JSON to the API.
  - `fieldnotes/server.py:29-31` provides GET, POST, and DELETE handlers but no OPTIONS handler.
- Assessment: serving the page from `file://` is not a dependable way to load an ES-module application. If the application is served from another local origin, its JSON POST requires a CORS preflight, but the server cannot handle OPTIONS and will return its default 501 response.
- Expected impact: a user following the README may get an empty/nonfunctional page, and the normal create-note request will not reach the API in a conventional browser setup.
- Suggested direction: serve the UI over HTTP and define an intentional same-origin or narrowly scoped CORS/preflight arrangement.

#### A1-02 — Note rendering permits HTML injection

- Severity: **Critical**
- Status: **Observed in code**
- Affected behavior: rendering notes from the API or importer
- Evidence: `web/app.js:8-17` interpolates note ID, title, body, and tags directly into `innerHTML`.
- Assessment: user- or file-supplied note content is treated as active markup rather than text. Crafted content can inject DOM elements and potentially script-capable attributes into the UI origin.
- Expected impact: untrusted or accidentally malformed notes can execute active content in the browser UI.
- Suggested direction: create DOM nodes and assign untrusted values through `textContent`; introduce sanitization only if rich HTML is an explicit product feature.

#### A1-03 — The test suite and CI are failing on `main`

- Severity: **Critical**
- Status: **Verified**
- Verification: ran `./scripts/check.sh`; 9 tests ran and 4 failed.
- Failures:
  - `tests/test_api.py:22`: response lacks `createdAt`.
  - `tests/test_api.py:31`: deletion returns 404 rather than 204.
  - `tests/test_api.py:37`: error response lacks `error`.
  - `tests/test_service.py:14`: tag normalization returns `deeplearning` rather than `deep-learning`.
- CI evidence: `.github/workflows/ci.yml:11` runs the same unit-test command.
- Expected impact: the branch does not satisfy its committed contract tests, and the configured CI job will fail.

#### A1-04 — Timestamp field names disagree across the runtime contract

- Severity: **High**
- Status: **Observed in code and tests**
- Evidence:
  - `fieldnotes/models.py:23-24` serializes the dataclass as `created_at`.
  - `web/app.js:12` reads `createdAt`.
  - `tests/test_api.py:22` requires `createdAt`.
  - `fieldnotes/legacy_adapter.py:4-10` contains a conversion, but the request path does not use it.
- Expected impact: rendered notes receive an undefined timestamp and generally display an invalid date.
- Suggested direction: select one public API name, serialize it at the API boundary, and remove or deliberately integrate the unused adapter.

#### A1-05 — Deletion is broken in both backend and frontend paths

- Severity: **High**
- Status: **Verified by unit test and observed in code**
- Evidence:
  - `fieldnotes/repository.py:22-24` always returns `False` from `delete()`.
  - `fieldnotes/api.py:38-40` therefore returns 404 for an existing note.
  - `web/app.js:45` sends DELETE to port 8080, while the active API default and other UI requests use 8000.
  - `web/app.js:45-46` does not check the response and removes the article unconditionally.
- Expected impact: deletion fails while the UI can make it appear successful until the next refresh.
- Suggested direction: implement repository deletion, route deletion through `web/api.js`, use one API base, and update the DOM only after a confirmed successful response.

#### A1-06 — Save failures are displayed as successful

- Severity: **High**
- Status: **Observed in code**
- Evidence: `web/app.js:24-38` sets the status to `Saved` before making the request; the catch block logs only to the developer console.
- Expected impact: users can believe a note was saved when the write failed, contrary to the stated product requirement that failed writes must not appear successful.
- Suggested direction: show a pending state, set success only after the request and refresh succeed, and display a user-visible failure state.

#### A1-07 — Notes are not persisted

- Severity: **High**
- Status: **Observed in code**
- Evidence:
  - `fieldnotes/repository.py:6-27` stores notes only in an in-memory list.
  - `fieldnotes/config.py:12-13` exposes a data-file setting that no runtime code uses.
  - `PROJECT_STATE.md:7` says SQLite migration is complete.
  - `docs/ARCHITECTURE.md:7` describes the repository as SQLite persistence.
  - `docs/STATUS.md:8` correctly describes the current repository as in-memory.
- Expected impact: every server restart discards all notes; project planning may proceed from a false assumption that persistence work is complete.
- Suggested direction: decide whether persistence is a beta requirement, then implement it or correct all claims that it already exists.

#### A1-08 — API-created and imported tags use incompatible normalization

- Severity: **High**
- Status: **Verified by tests and observed in code**
- Evidence:
  - `fieldnotes/service.py:4,14` uses `fieldnotes.utils.normalize_tag` for API creation.
  - `fieldnotes/importer.py:4,12` uses `fieldnotes.helpers.text.normalize_tag` for imports.
  - `fieldnotes/utils.py:7` uses `r"\\s+"`, which matches a literal backslash plus `s`, not whitespace.
  - `fieldnotes/helpers/text.py:3` converts spaces to underscores.
- Expected impact: the same conceptual tag can become `deeplearning`, `deep-learning`, or `deep_learning`, depending on its input path or intended contract.
- Suggested direction: keep one canonical normalizer in the service/domain layer and test identical input through both creation paths.

#### A1-09 — Valid JSON with unexpected shapes can crash request handling

- Severity: **Medium**
- Status: **Observed in code; representative failures inferred**
- Evidence:
  - `fieldnotes/api.py:22-31` assumes the decoded value has `.get()` and catches only `ValueError` and `JSONDecodeError`.
  - `fieldnotes/service.py:11-15` assumes title and body are strings and tags is an iterable of strings.
- Representative inputs: a top-level JSON array, `null` or numeric title/body values, `null` tags, or numeric tag entries.
- Expected impact: malformed client data can cause handler exceptions or dropped connections rather than a structured 400 response.
- Suggested direction: validate the top-level object and every field type before invoking the service.

#### A1-10 — A threaded server mutates an unsynchronized repository

- Severity: **Medium**
- Status: **Observed design risk**
- Evidence:
  - `fieldnotes/server.py:40` uses `ThreadingHTTPServer`.
  - `fieldnotes/repository.py:16-20` mutates `_next_id` and `_notes` without synchronization.
  - `docs/ARCHITECTURE.md:23` claims repository operations are serialized.
- Expected impact: concurrent requests can produce inconsistent repository behavior; the implementation does not support the documented reliability guarantee.
- Suggested direction: serialize mutations explicitly or move concurrency control into the chosen persistent repository.

#### A1-11 — Search results can be overwritten by stale responses

- Severity: **Medium**
- Status: **Observed design risk**
- Evidence: `web/app.js:49-55` launches a request for each input event with no cancellation, ordering guard, debounce, or `response.ok` check.
- Expected impact: a slower response for an older query can render after a newer response and show results for the wrong text. HTTP failures may also be processed as though they were successful JSON responses.
- Suggested direction: cancel superseded requests or ignore responses that do not match the current query, and handle non-OK responses visibly.

#### A1-12 — CORS behavior contradicts the documented boundary

- Severity: **Medium**
- Status: **Observed in code**
- Evidence:
  - `fieldnotes/server.py:24` sends `Access-Control-Allow-Origin: *` on every handled response.
  - `docs/ARCHITECTURE.md:19` says CORS is restricted to the local development origin.
- Expected impact: the local API has a broader read boundary than documented. Adding preflight support without revisiting this wildcard could also broaden write access to arbitrary websites.
- Suggested direction: choose a same-origin deployment or a small allowlist appropriate to the local UI.

#### A1-13 — The sample-import utility does not run via its obvious command

- Severity: **Medium**
- Status: **Verified**
- Verification: ran `python3 tools/import_sample.py` from the repository root.
- Result: `ModuleNotFoundError: No module named 'fieldnotes'`.
- Evidence: `tools/import_sample.py:1` imports the project package, while direct script execution places `tools/` at the front of the import path.
- Suggested direction: expose the utility as a package module/entry point, or document and support a command that runs with the project root on the module path.

#### A1-14 — Configuration and status sources conflict

- Severity: **Medium**
- Status: **Observed across tracked files**

| Subject | Values currently present |
| --- | --- |
| Package version | `0.4.0` in `pyproject.toml:3`; `0.3.1` in `fieldnotes/__init__.py:1` |
| Default port | 8000 in runtime/README/API docs; 8080 in `PROJECT_STATE.md`, architecture docs, `.env.example`, and frontend deletion |
| Port environment variable | Runtime reads `FIELDNOTES_PORT`; `.env.example` advertises `FIELD_NOTES_PORT` |
| Persistence | In-memory in code/status; SQLite complete in project state/architecture |
| Timestamp | `created_at` in runtime/status; `createdAt` in tests/UI/architecture/project state |
| Error schema | `{ "message": ... }` in runtime/API docs; nested `error` object in tests/architecture |
| Deletion | Stubbed in code; implemented in project state; blocked in status |

- Expected impact: developers cannot identify a reliable source of truth, and setup or integration work based on the wrong document will fail.
- Suggested direction: settle executable contracts first, designate one status source, and update the other documents from that source.

#### A1-15 — Test and CI coverage omit important product boundaries

- Severity: **Medium**
- Status: **Observed coverage gap**
- Missing checks:
  - Real HTTP server behavior, including OPTIONS and CORS.
  - Browser startup and create/delete/error flows.
  - Repository-level deletion behavior.
  - Malformed JSON shapes and field types.
  - Persistence across restart.
  - Equivalent tag normalization through API and import paths.
  - Concurrent repository operations.
  - Frontend syntax, lint, and injection regression tests.
- Additional evidence: `.github/workflows/ci.yml:11` runs unit tests only and does not run the compile step from `scripts/check.sh:4`.
- Expected impact: contract breaks at system boundaries can merge even after the existing unit assertions are repaired.

#### A1-16 — The tracked sample-data policy is easy to misunderstand

- Severity: **Low**
- Status: **Verified**
- Evidence:
  - `.gitignore:4` ignores `data/*.json`.
  - `data/sample.json` is already tracked, so the ignore rule does not remove it.
- Expected impact: future sample fixtures in the same directory may silently remain untracked, while contributors may incorrectly assume the existing sample is ignored.
- Suggested direction: separate committed fixtures from runtime/private data with distinct directories or narrow ignore patterns.

### A1 verification record

Commands executed from the repository root:

```text
git status --short --branch
git log --oneline --decorate -8
git remote -v
rg --files
./scripts/check.sh
python3 tools/import_sample.py
git ls-files
git check-ignore -v data/sample.json .env.example fieldnotes/__pycache__/api.cpython-313.pyc
```

No files were modified during the A1 review pass.

## Additional agent passes

Append new independent reviews below this heading. Recommended heading format:

```markdown
### A2 — Review focus

Reviewer: agent or reviewer name

Scope: areas inspected

#### A2-01 — Concise finding title

- Severity: **High**
- Status: **Verified**, **Observed in code**, or **Inferred risk**
- Evidence: `path/to/file:line`
- Expected impact: ...
- Suggested direction: ...
```

### A2 — Five-agent remediation pass

Reviewers: Avicenna, Linnaeus, Wegener, Erdos, and Planck

Integration reviewer: Codex primary agent

Scope: five concurrent cleanup lanes with disjoint file ownership, followed by a combined review and full-repository verification.

#### Coordination model

| Lane | Owned area | Result |
| --- | --- | --- |
| Avicenna | models, configuration, repository, and repository tests | Completed |
| Linnaeus | importer, compatibility helpers, utilities, sample tool, and importer tests | Completed |
| Wegener | service layer and service tests | Completed |
| Erdos | API, HTTP server, and API tests | Completed |
| Planck | browser UI, documentation, CI, and maintenance files | Completed |

Agents inspected the full repository for context but were instructed to edit only their assigned files. No agent committed changes. The primary agent retained responsibility for combined review and verification.

#### A2-01 — Executable contracts were reconciled

- Status: **Fixed and verified**
- Resolves: `A1-03`, `A1-04`, `A1-05`, `A1-06`, `A1-08`, `A1-09`, `A1-12`, `A1-13`, and most of `A1-14`.
- Result:
  - Public timestamps use `createdAt`; Python continues to use `created_at` internally.
  - Existing-note deletion returns `204`; missing notes return `404`; malformed IDs return `400`.
  - API errors use `{ "error": { "code": "...", "message": "..." } }`.
  - API creation and file import share one tag normalizer.
  - Create and import inputs are validated before repository mutation.
  - Port and environment-variable documentation now match the runtime.
  - Package and module versions both report `0.4.0`.
- Verification: combined check suite passed with 33 tests.

#### A2-02 — Repository ownership and concurrency were repaired

- Status: **Fixed and verified**
- Resolves: mutable-state exposure identified during remediation and `A1-10`.
- Result:
  - Repository methods return copies, including copied tag lists, rather than exposing repository-owned mutable state.
  - A repository-owned lock protects listing, ID allocation, insertion, deletion, and clearing.
  - Concurrent ID allocation is covered by an eight-writer, 800-note regression test.
- Verification: all 800 concurrent additions received unique sequential IDs.

#### A2-03 — Import behavior is consistent and atomic

- Status: **Fixed and verified**
- Resolves: `A1-08` and `A1-13`.
- Result:
  - The duplicate legacy tag implementation now delegates to the canonical normalizer.
  - Import payloads are validated completely before any note is added, avoiding partial imports.
  - The sample-import tool has an explicit entry point and works when run from the repository root.
  - The legacy response adapter accepts both former and current timestamp keys.

#### A2-04 — HTTP boundaries now fail predictably

- Status: **Fixed and verified**
- Resolves: `A1-09`, `A1-12`, and API portions of `A1-15`.
- Result:
  - Known routes reject unsupported methods with `405`.
  - Delete routing rejects extra path segments.
  - Malformed and oversized request lengths return structured errors rather than terminating the request.
  - Unexpected request exceptions return a structured `500` response.
  - Local CORS origins and preflight requests are handled explicitly.
  - Responses include a content length, including empty `204` responses.

#### A2-05 — Browser behavior now reflects backend truth

- Status: **Fixed and smoke-tested**
- Resolves: `A1-01`, `A1-02`, `A1-05`, `A1-06`, and `A1-11`.
- Result:
  - The README provides a working local HTTP launch flow for the static UI.
  - All browser requests go through `web/api.js`.
  - Create and delete operations show success only after the backend confirms them.
  - Note content is built with DOM nodes and `textContent`, not interpolated into `innerHTML`.
  - Search results ignore responses superseded by a newer query.
  - Loading, empty, success, and error states are visible and accessible.
- Verification: frontend syntax checks and a live HTTP smoke test covered create, search, delete, static assets, and local CORS.

#### A2-06 — Documentation and automated checks match the prototype

- Status: **Fixed and verified**
- Resolves: documentation portions of `A1-07`, `A1-14`, and `A1-15`.
- Result:
  - Documentation consistently describes the repository as in-memory, not SQLite-backed.
  - Runtime port, timestamp naming, error shape, deletion status, tag behavior, and CORS behavior are aligned across maintained documents.
  - CI now runs the repository check script.
  - The check script compiles Python, checks frontend JavaScript when Node.js is available, and runs the complete unit suite.

#### A2-07 — Remaining product gaps

- Status: **Open and intentionally not expanded during cleanup**
- Persistence remains process-local; restarting the API loses notes.
- `FIELDNOTES_DATA` is recognized but is not connected to repository storage.
- The browser has syntax and live smoke coverage, but no automated interaction tests.
- Local CORS rules would need to be reconsidered before hosting.
- The sample-data ignore policy from `A1-16` remains worth clarifying before beta.

### Integration verification

Primary-agent verification after all five lanes completed:

```text
Baseline: 9 tests, 4 failures
Final: 33 tests, 33 passed
Python compilation: passed
Frontend JavaScript syntax: passed
Diff whitespace validation: passed
```

The integration review found two omissions after the first parallel pass: the package/module version mismatch and unsynchronized access to the in-memory repository. Both were returned to the data-layer owner and repaired before final verification.

## Consolidation queue

Keep the original A1 evidence until all independent notes have been reviewed. During consolidation:

1. Preserve the original baseline as the before-state.
2. Merge duplicate findings by stable ID and link each to its A2 resolution.
3. Separate fixed defects from intentionally deferred product work.
4. Retain the verification commands and results that establish each outcome.
5. Remove instructions that only applied while independent review passes were still being collected.

## Consolidation workspace

Leave this section unchanged during independent collection. After all review passes are present, use it to:

1. Merge duplicates while retaining all supporting evidence.
2. Resolve disagreements and label any remaining uncertainty.
3. Separate release blockers from later hardening work.
4. Choose canonical API, configuration, persistence, and documentation contracts.
5. Turn accepted findings into small, ordered remediation tasks.

## FN-TEAM - Concurrent field scan (2026-09-13 UTC / 2026-09-12 Pacific)

Collection pass, not an implementation plan. This entry supplements earlier evidence; it does not rewrite or erase any review. Independent teams may continue editing the repository.

### FN-LEAD - Purpose, baseline, and coordination

- Product: Field Notes is a local-first research-note workspace with a Python API and browser UI for creating, listing, searching, and deleting notes with titles, bodies, tags, and creation timestamps. Shared tag normalization and visible failure feedback are explicit requirements (README.md:5-12).
- Working-tree milestone: durable storage and an internal beta. Restart data loss is openly documented, not an undisclosed regression (PROJECT_STATE.md:12-20). Implementing persistence needs an explicit format and failure contract; this scan does not select either.
- HEAD: 1884f4d785f2c3042792d45854e06c0837599408, main, no configured remotes. Entry state: 29 modified tracked files plus untracked TRIAGE.md. These edits predate this team's work and are not ours.
- Verification: `env TMPDIR="$(mktemp -d /tmp/fieldnotes-scan.XXXXXX)" bash scripts/check.sh` exited 0: Python compilation, frontend syntax checks, and 32 Python tests passed. A private temporary cache path avoided this team's checks sharing the normal cache. No server, installation, browser testing, or source edits were performed by the lead.
- A1-03's failing-suite observation is historical: the inspected working tree now passes. Do not silently delete that older evidence or infer the baseline commit itself is fixed.
- Coordination risk: all application layers already contain uncommitted work. HEAD alone cannot identify the reviewed contents. Findings below refer to working-tree snapshots; recheck them before assigning fixes. Do not bulk-stage, reset, or commit other teams' work.
- Suggested collection protocol: this team's four reviewers return read-only reports; one lead appends them. This does not impose a lock on other teams. Before implementation, claim disjoint files and agree shared contracts; record resolutions as new entries. Consolidation remains deferred.

### FN-S3 - Browser/client integration (Cicero)

Static source review, independently checked by lead against web/app.js. Scenarios are inferred from control flow, not browser-executed reproductions.

#### FN-S3-01 - High - Saving can discard edits made during the request

- Evidence: web/app.js:75 disables only Submit; web/app.js:77 captures field values; web/app.js:84 resets the still-editable form after POST succeeds.
- Scenario: submit draft A, type draft B while POST is pending, resolve POST. B is cleared although only A was submitted.
- Suggested direction: preserve edits made after the submitted snapshot or disable composer fields during submission. Add a delayed-POST test. New finding relative to A1.

#### FN-S3-02 - Medium - Refreshes bypass search ordering

- Evidence: web/app.js:68 unconditionally renders refresh results. The version guard at web/app.js:110 only coordinates input-triggered searches, not startup/mutation refreshes.
- Scenario: initial list resolves after a newer search and overwrites filtered results; a pending search can also restore a deleted note after a mutation refresh.
- Suggested direction: one ordering/invalidation policy across collection reads. Residual of A1-11; the search-to-search case appears repaired.

#### FN-S3-03 - Medium - Refresh failure hides successful mutation

- Evidence: web/app.js:83 and web/app.js:101 combine mutation and following GET in the same error handler. After successful DELETE and failed refresh, the stale note's Delete button is reenabled.
- Scenario: DELETE returns 204, following GET fails; note remains actionable and another DELETE returns 404. Successful POST followed by failed GET similarly loses a clear saved-state acknowledgment.
- Suggested direction: distinguish confirmed mutation success from refresh failure and reconcile confirmed changes locally. Related to A1-05/A1-06 but their original false-success paths appear repaired.

- Positive reconciliation: textContent rendering, createdAt serialization, shared API requests, HTTP error handling, documented HTTP UI serving, and OPTIONS handling address several original A1 findings. Frontend syntax is checked; browser interaction coverage remains absent (residual A1-15).

### FN-S1 - API/service contracts (Pasteur)

#### FN-S1-01 - Medium - Unsupported HTTP methods bypass the JSON contract

- Verified by agent using in-memory Handler request/response streams, without a listening server. PUT /api/notes returns 501 HTML through Handler, while direct handle_request returns JSON 405.
- Evidence: docs/API.md:28 promises 405 for known routes; fieldnotes/server.py:92 only dispatches GET, POST, and DELETE into the API.
- Impact: transport behavior differs from the tested API function and documented error schema.
- Direction: consistently dispatch/reject unsupported methods; add transport-level tests. Concrete extension of A1-15's coverage gap.

#### FN-S1-02 - Medium - Excessive JSON nesting returns internal error

- Verified by agent: body `b'[' * 2000 + b'0' + b']' * 2000` raises RecursionError directly and produces JSON 500 through Handler.
- Evidence: fieldnotes/api.py:28 decodes before shape validation; fieldnotes/api.py:66 catches ValueError, not RecursionError.
- Direction: classify excessive nesting as invalid input and add a regression test. Residual of A1-09, not a new duplicate of already-fixed ordinary malformed inputs.

#### FN-S1-03 - Low - Direct service deletion accepts boolean/float IDs

- Verified by agent: after creating ID 1, service.delete_note(True), or 1.0 in a separate instance, deletes that note.
- Evidence: fieldnotes/service.py:44 delegates without runtime ID validation; fieldnotes/repository.py:30 uses equality.
- HTTP routing excludes these input types; impact is limited to direct Python callers. Consider validation at the service boundary. New low-priority finding.

- Positives: agent ran 27 API/service/repository tests successfully. Timestamp, deletion, ordinary malformed-input validation, tag normalization, and defensive copies now work. A1-04, backend A1-05, and parts of A1-09 have been repaired in this working tree.

### FN-S2 - Storage/import/state (Maxwell)

#### FN-S2-01 - High for beta - Notes remain non-durable

- Existing A1-07, retained rather than counted as new. fieldnotes/repository.py:11 starts empty in-memory state; fieldnotes/server.py:37 does not connect the configured storage path from fieldnotes/config.py:11.
- Verified by agent through separate repository instances, not a live server restart. Current README and PROJECT_STATE disclose restart loss, so older misleading-documentation claims are stale.
- Direction: define load/write failure behavior and persistence contract before implementing storage.

#### FN-S2-02 - Medium, persistence prerequisite - Failed batch write leaves partial import

- Evidence: fieldnotes/importer.py:43 validates the full payload, then adds rows individually; fieldnotes/repository.py:21 locks individual adds, not a transaction.
- Agent fault injection: second add raised OSError; first row remained. Retrying produced A, A, B. This was an injected failure, not an observed disk failure: current adds are in-memory.
- Direction: explicitly choose transactional import or partial-progress/retry semantics before adding durable writes. This differs from malformed-input validation, which already avoids partial mutation.

- A1-10 correction: another team added repository locking during collection. Final agent inspection found locks around list/add/delete/clear and a passing concurrency test covering 800 unique sequential IDs. Do not retain an unqualified no-lock finding.
- Canonical API/import tag normalization and legacy timestamp conversion now agree. Malformed batches fail before mutation; defensive copies and deletion work.

### FN-S4 - Security/runtime/configuration (Carson)

#### FN-S4-01 - Medium - Disallowed-origin POST still mutates state

- Agent verified in-memory Handler POST with Origin https://example.com, Content-Type text/plain, and a JSON note body returned 201 and added the note, although the origin predicate rejected the origin.
- Evidence: fieldnotes/server.py:59 does not enforce origin/media type before mutations; origin rejection is only in OPTIONS at fieldnotes/server.py:82.
- Browser-to-loopback exploitability is inferred and depends on browser network protections; no browser exploit was attempted. API binds 127.0.0.1, not a public interface.
- Direction: enforce intended origin policy on mutation requests and require JSON media type. Residual A1-12: CORS response headers do not themselves prevent writes.

#### FN-S4-02 - Medium - Null origin is broader than trusted file access

- Verified code/predicate: fieldnotes/server.py:17 allows `null`; fieldnotes/server.py:50 reflects it; OPTIONS permits mutation methods. An agent's in-memory null-origin POST returned 201.
- Risk: opaque origins can also serialize as null; this is not an identity for a trusted local file. Browser exploitability was not tested.
- Direction: remove null-origin support if the documented HTTP-served UI is the intended entry point. Related to A1-12, not a separate confirmed remote exploit.

#### FN-S4-03 - Medium - Custom API port does not configure the client

- Agent verified FIELDNOTES_PORT=9000 changes config.get_port() while web/api.js:1 stays fixed to http://127.0.0.1:8000. Connection failure is inferred if nothing serves the old port.
- Evidence: fieldnotes/config.py:8 and web/api.js:1.
- Direction: coordinate API-base configuration or same-origin serving. Default-port/environment spelling conflicts from A1-14 are repaired; custom-port support remains incomplete.

- Positives: localhost binding, body-size checks, generic unexpected-error responses, OPTIONS, and CI invoking scripts/check.sh are present. Original A1-01 and A1-15 CI-command mismatch are stale.
- Superseding the agent's intermediate observation: lead reread fieldnotes/__init__.py after the report; it now declares 0.4.0, matching pyproject.toml. The earlier A1-14 version mismatch is no longer present at final check. No claim about package installation/build verification.

### FN-LEAD - Closing snapshot and handoff

- Final full check: 33 tests passed, including the new concurrent-add regression; Python compilation and frontend syntax checks also passed. No browser-level execution was performed. These results are local, not a remote CI run.
- Local python3 is 3.9.6; pyproject.toml declares >=3.11. Passing locally is useful evidence but does not replace verification on the declared supported runtime.
- Source snapshots at 03:02:28Z and 03:03:57Z had the same HEAD; the tracked-content hash comparison between those captures changed only fieldnotes/__init__.py. Repository locking appeared earlier during the agents' scans. Concurrent edits can still invalidate later conclusions.
- All four agents were read-only. This team only appends this report to TRIAGE.md; no implementation, staging, commit, push, or deployment is authorized by this scan.
- Consolidation remains separate and append-only. Suggested next discussion: assign non-overlapping owners for web async state; HTTP transport/origin validation; and persistence/import semantics. Agree shared contracts before anyone edits overlapping modules. Keep deferred low-priority service-ID hardening distinct from user-facing blockers.

### FN-LEAD - File-change inventory (2026-09-13T03:08:20.908Z)

This is a current working-tree inventory, not an attribution of all changes to our team.

Our team modified only TRIAGE.md by appending the FN-TEAM review and this inventory. All four scan agents were read-only. TRIAGE.md already existed and was untracked before our append; we did not create its earlier content.

Tracked files currently modified (30):

- `.env.example`
- `.github/workflows/ci.yml`
- `.gitignore`
- `PROJECT_STATE.md`
- `README.md`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/STATUS.md`
- `fieldnotes/__init__.py`
- `fieldnotes/api.py`
- `fieldnotes/config.py`
- `fieldnotes/helpers/text.py`
- `fieldnotes/importer.py`
- `fieldnotes/legacy_adapter.py`
- `fieldnotes/models.py`
- `fieldnotes/repository.py`
- `fieldnotes/server.py`
- `fieldnotes/service.py`
- `fieldnotes/utils.py`
- `pyproject.toml`
- `scripts/check.sh`
- `tests/test_api.py`
- `tests/test_importer.py`
- `tests/test_repository.py`
- `tests/test_service.py`
- `tools/import_sample.py`
- `web/api.js`
- `web/app.js`
- `web/index.html`
- `web/styles.css`

Untracked files currently present:

- `README_INTENT.md`
- `TRIAGE.md`

Provenance: 29 tracked files were already modified at scan entry. fieldnotes/__init__.py became modified during the scan; repository locking and a concurrency test also appeared in already-modified files. README_INTENT.md was first observed at this inventory check. Other edits belong to the pre-existing/concurrent work; precise authorship is not established. No files were staged or committed by this team.

## Consolidated findings (2026-09-12 Pacific)

This section is the current remediation view. It preserves the earlier review passes as historical evidence while removing duplicate counts, superseding stale observations, and separating verified fixes from remaining work. Findings were rechecked against the working tree at commit `1884f4d` plus the current uncommitted changes; they must be revalidated if that snapshot changes.

### Current verification baseline

- `PATH=/opt/homebrew/bin:/usr/bin:/bin PYTHONPYCACHEPREFIX=/tmp/fieldnotes-consolidation-pycache bash scripts/check.sh` passed on Python 3.12: Python compilation, frontend syntax checks, and 33 Python tests.
- `git diff --check` passed.
- No browser automation or remote CI result is represented by those checks.

### Open release blockers

#### C-01 — Durable persistence and export are not implemented

- Priority: **Release blocker**
- Consolidates: `A1-07`, `A2-07`, `FN-S2-01`, and the persistence/export gaps in `README_INTENT.md`.
- Current evidence: `fieldnotes/repository.py:8-14` initializes process-local memory; `fieldnotes/server.py:37-38` constructs it without using `fieldnotes/config.py:11-15`; `README_INTENT.md:184-198,237-242,397-399` requires durable SQLite storage, stable IDs across restarts, configurable storage, and export/import round trips.
- Outcome: create and delete acknowledgements are not durable, every restart loses notes, the configured data path has no runtime effect, and there is no export path.
- Decision needed before implementation: SQLite schema, startup/migration behavior, atomic-write failure semantics, and whether imported `createdAt` values are preserved.

#### C-02 — Browser request state can lose edits or display stale state

- Priority: **Release blocker**
- Consolidates: residual `A1-11`, `FN-S3-01`, `FN-S3-02`, and `FN-S3-03`.
- Current evidence: `web/app.js:75-85` disables only Submit and resets the still-editable form after the POST; `web/app.js:68-71` refreshes outside the search version guard; `web/app.js:83-88,101-106` combines a confirmed mutation and its follow-up refresh in one error path.
- Outcome: typing a second draft during a slow save can be erased; startup or mutation refreshes can overwrite newer search results; and a successful mutation followed by a failed refresh is reported ambiguously and can leave stale controls active.
- Suggested direction: use one request-generation/invalidation policy for every collection read, preserve or temporarily lock the submitted form snapshot, and distinguish mutation success from refresh failure.

#### C-03 — The local-origin boundary does not prevent cross-origin writes

- Priority: **Release blocker**
- Consolidates: residual `A1-12`, `FN-S4-01`, and `FN-S4-02`.
- Current evidence: `fieldnotes/server.py:16-19` trusts opaque `Origin: null`; `fieldnotes/server.py:42-53` uses origin checks only to decide response headers; `fieldnotes/server.py:59-80` processes mutation requests without enforcing the origin or JSON media type. The maintained README now serves the UI over local HTTP, so direct-file access is no longer required.
- Outcome: a disallowed-origin simple POST can still mutate local note data even when the response is unreadable, and `null` is not a trustworthy identity for this application.
- Suggested direction: remove `null` from the normal policy, reject disallowed origins on state-changing requests, require the intended JSON content type, and add real HTTP/browser boundary tests. Revisit the model again before any hosted deployment.

#### C-04 — The documented configurable port breaks the browser client

- Priority: **Release blocker**
- Consolidates: remaining configuration portion of `A1-14` and `FN-S4-03`.
- Current evidence: `fieldnotes/config.py:7-8` honors `FIELDNOTES_PORT`, while `web/api.js:1` always targets `http://127.0.0.1:8000`; `README_INTENT.md:104-116,344-356` requires a working configurable port and coherent startup URL.
- Outcome: starting the API on a custom port leaves the browser calling port 8000. The current two-command startup also does not meet the intended one-command/printed-browser-URL experience.
- Suggested direction: prefer serving UI and API from one process/origin; otherwise inject one shared API-base configuration and document its precedence.

### Open hardening and contract work

#### C-05 — Actual HTTP behavior remains under-tested and partly inconsistent

- Priority: **Medium**
- Consolidates: residual `A1-15`, `FN-S1-01`, the uncertain portion of `FN-S1-02`, and the browser-coverage portions of `A2-07`.
- Confirmed evidence: `fieldnotes/server.py:92-94` routes only GET, POST, and DELETE through the JSON API, so methods such as PUT receive `BaseHTTPRequestHandler` HTML/501 behavior instead of the documented JSON/405 contract. Current tests exercise `handle_request()` and `is_allowed_origin()` directly rather than a listening HTTP boundary.
- Coverage still needed: CORS headers and preflight, disallowed-origin mutation, content type, malformed `Content-Length`, body limit, unsupported methods, browser create/search/delete/error flows, safe text rendering, and mutation/search ordering.
- Uncertainty retained: `FN-S1-02` observed excessive JSON nesting becoming a Handler 500, but a 2,000-level payload recheck through `handle_request()` on Python 3.12 returned structured 400. Reproduce at the supported HTTP boundary before assigning a separate defect.

#### C-06 — Extremely long numeric delete IDs escape the API contract

- Priority: **Medium**
- Source: consolidation recheck; related to `A1-09` and `FN-S1-02` input-hardening concerns.
- Verified on Python 3.12: a 5,000-digit path segment reaches `int(raw_note_id)` at `fieldnotes/api.py:72` and raises Python's maximum-string-digit `ValueError` instead of returning `invalid_note_id` 400. The Handler converts this into a generic 500.
- Suggested direction: bound the digit count before conversion or catch conversion failure, then add direct API and HTTP regression tests on the declared Python runtime.

#### C-07 — Import is prevalidated but not transaction-safe

- Priority: **Medium; persistence prerequisite**
- Consolidates: `FN-S2-02` and the remaining import guarantees in `README_INTENT.md:227-235`.
- Current evidence: `fieldnotes/importer.py:41-47` validates the whole payload and then performs independent repository additions. Each `fieldnotes/repository.py:20-25` add is locked, but the batch has no transaction boundary.
- Outcome: an injected or future durable-storage failure after one add leaves partial state; retry can duplicate already-added notes. Import also currently replaces supplied creation times rather than implementing the intent document's preferred preservation policy.
- Suggested direction: make batch insertion a repository transaction and settle timestamp/import reporting semantics alongside persistence.

#### C-08 — Narrow domain and repository contracts remain underspecified

- Priority: **Low**
- Consolidates: `FN-S1-03`, `A1-16`, and remaining intent mismatches.
- Items:
  - `fieldnotes/service.py:44-45` and `fieldnotes/repository.py:27-33` accept `True` and `1.0` as ID 1 for direct Python callers; HTTP input is narrower.
  - `.gitignore` policy for committed sample fixtures versus private/runtime JSON remains easy to misunderstand.
  - `README_INTENT.md:134` prefers newest-first listing, while `fieldnotes/repository.py:16-18` returns insertion order (oldest first).
  - Unknown JSON-field policy, log-level configuration, and import/export command contracts are not yet settled.

### Verified fixes; close unless regression appears

The following original findings are resolved in the current working tree and should not be scheduled again as open defects:

| Historical finding | Current resolution |
| --- | --- |
| `A1-01` direct-file launch/preflight | README uses an HTTP-served UI and server implements OPTIONS; `C-03` and `C-04` retain the remaining origin/startup issues. |
| `A1-02` HTML injection | `web/app.js:22-65` creates DOM nodes and assigns note content with `textContent`. |
| `A1-03` failing tests | Current Python 3.12 check passes 33 tests, compilation, and frontend syntax. |
| `A1-04` timestamp mismatch | Public responses use `createdAt`; internal model remains `created_at`. |
| `A1-05` original delete failure | Repository deletion and the shared frontend API call work; `C-02` retains refresh-state ambiguity. |
| `A1-06` immediate false “Saved” | UI now shows pending/success/error states; `C-02` retains slow-request edit loss and post-mutation refresh handling. |
| `A1-08` tag-normalizer split | API and importer use the canonical utility. |
| Ordinary portion of `A1-09` | Top-level and field shapes are validated; `C-06` and part of `C-05` retain edge-input handling. |
| `A1-10` unsynchronized repository | All repository operations now use a lock; a concurrency test covers 800 unique sequential IDs. |
| Original search-to-search part of `A1-11` | Input searches use a version guard; `C-02` retains refresh/search races. |
| `A1-13` sample tool import failure | The tool has a guarded entry point and the project check covers current Python code. |
| Most of `A1-14` documentation drift | Maintained README, API, architecture, status, versions, and default port now agree; `C-01` and `C-04` retain intentional gaps. |

### Recommended remediation order

1. Agree the runtime topology and trust boundary (`C-03`, `C-04`) because they determine server, browser client, documentation, and HTTP tests.
2. Implement SQLite persistence, transactional repository operations, import semantics, and export (`C-01`, `C-07`).
3. Unify browser request state and mutation reconciliation (`C-02`).
4. Add real HTTP and browser contract coverage, fixing unsupported methods and long IDs as part of that lane (`C-05`, `C-06`).
5. Resolve the narrow product-policy items in `C-08` and run the complete internal-beta acceptance pass.

No application files were changed during this consolidation. This section is an append-only synthesis of the current evidence; the earlier passes remain available for provenance.

## CODE-LEAD - Acceptance pass

Reviewer: Codex primary agent

Review basis: current working tree after the five-agent remediation pass, the independent FN-TEAM scan, `README_INTENT.md` as the proposed product target, and `README.md` / `PROJECT_STATE.md` as the honest current-prototype description.

This pass answers a narrower question than triage: which changes are sound enough to keep, which work in the current prototype but need a follow-up, and which claims are not yet implemented.

### Accepted - good code to keep

#### CL-A01 - Model serialization and defensive copies

- Decision: **Accept**
- Files: `fieldnotes/models.py`, relevant repository tests.
- Why: the Python model keeps `created_at` internally while public serialization emits `createdAt`; tag lists are copied rather than shared with callers.
- Evidence: unit coverage passes on Python 3.12 and the browser receives a valid timestamp.

#### CL-A02 - Thread-safe in-memory repository

- Decision: **Accept for the current prototype**
- Files: `fieldnotes/repository.py`, `tests/test_repository.py`.
- Why: locking covers ID allocation and all shared-state access; returned notes cannot mutate repository-owned tag lists.
- Evidence: the eight-writer regression produced 800 unique sequential IDs.
- Boundary: this is sound in-memory behavior, not durable persistence.

#### CL-A03 - Shared tag normalization and service validation

- Decision: **Accept with one small follow-up**
- Files: `fieldnotes/utils.py`, `fieldnotes/helpers/text.py`, `fieldnotes/service.py`.
- Why: API and imports now use the same canonical normalization, and malformed service inputs fail clearly.
- Verified behavior: `Deep Learning` becomes `deep-learning` through the service and importer.
- Follow-up: duplicate normalized tags are still retained; `README_INTENT.md` says they should be stored once.

#### CL-A04 - Import validation and compatibility cleanup

- Decision: **Accept for the in-memory prototype**
- Files: `fieldnotes/importer.py`, `fieldnotes/legacy_adapter.py`, `tools/import_sample.py`.
- Why: malformed batches are fully validated before mutation, the old timestamp adapter remains compatible, and the sample tool now has a usable entry point.
- Boundary: a repository failure during the add loop can still leave a partial import. Resolve that as part of the SQLite transaction design, not with an in-memory rollback abstraction.

#### CL-A05 - API contract and ordinary validation

- Decision: **Accept**
- Files: `fieldnotes/api.py`, most of `tests/test_api.py`.
- Why: timestamp fields, nested errors, deletion, route matching, common malformed JSON, wrong methods at the direct API boundary, and field types now behave consistently.
- Python-version note: the excessive-nesting payload returned a structured `400` on the declared-compatible Python 3.12 runtime. The earlier `RecursionError` observation came from Python 3.9, which is below the declared `>=3.11` support floor. Keep a bounded nesting test only if Python 3.11 reproduces it.

#### CL-A06 - Safe browser rendering and basic interaction states

- Decision: **Accept**
- Files: `web/index.html`, `web/styles.css`, DOM-rendering portions of `web/app.js`, and `web/api.js` request/error handling.
- Why: note text is no longer interpreted as HTML; labels, focus states, live status text, empty states, line breaks, narrow-screen layout, and backend error messages are substantially improved.
- Live verification: a note whose title contained an HTML image payload rendered as literal text with no page error; multiline body text remained intact; the 390px viewport had no horizontal overflow.

#### CL-A07 - Documentation honesty and check script

- Decision: **Accept**
- Files: maintained README/docs, `scripts/check.sh`, CI workflow, package metadata, ignore rules.
- Why: maintained documentation accurately calls the current repository an in-memory prototype, and CI exercises compilation, frontend syntax, and unit tests.
- Evidence: Python 3.12 ran all 33 tests successfully; compilation, JavaScript syntax, and diff checks passed.

### Hold - targeted fixes before accepting the whole patch

#### CL-H01 - Mutation requests do not enforce the origin policy

- Decision: **Hold the HTTP server boundary**
- Severity: **High for a local browser application**
- Files: `fieldnotes/server.py`, transport-level tests.
- Reproduction: a `POST /api/notes` with `Origin: https://example.com` and `Content-Type: text/plain` returned `201` and inserted a note.
- Why: CORS response headers control whether a browser may read a response; they do not reliably prevent a write. The server must reject disallowed origins on mutation requests and require the intended JSON media type.
- Also remove `null`-origin mutation support if HTTP-served UI is the canonical launch path.

#### CL-H02 - Unsupported transport methods bypass the API contract

- Decision: **Hold the HTTP server boundary**
- Severity: **Medium**
- Reproduction: `PUT /api/notes` returned the base server's HTML `501`, while direct `handle_request` correctly returns JSON `405`.
- Direction: dispatch or explicitly reject unsupported methods through the same JSON response path; cover the real handler, not only `handle_request`.

#### CL-H03 - Browser request ordering is only partially coordinated

- Decision: **Hold the mutation/refresh portions of `web/app.js`**
- Severity: **Medium**
- Confirmed by control-flow review:
  - only the submit button is disabled, so edits typed during a pending save can be erased by `form.reset()`;
  - `refresh()` is outside the search-version guard and can overwrite a newer filtered result;
  - a successful create/delete followed by a failed refresh is reported as though the mutation failed.
- Direction: use one collection-request generation counter, preserve or disable the submitted fields, and separate mutation success from refresh failure.

#### CL-H04 - Direct service deletion accepts booleans and floats as IDs

- Decision: **Small service hardening follow-up**
- Severity: **Low**
- Reproduction: `delete_note(True)` deletes note ID 1 because Python considers `True == 1`; `1.0` behaves similarly.
- Direction: require a positive, non-boolean integer at the service boundary.

### Product work - not defects in the accepted prototype patch

#### CL-P01 - Durable SQLite persistence

- Decision: **Not implemented**
- Why: `README_INTENT.md` defines persistence across restarts as a core product behavior, while the current repository deliberately stores notes in memory.
- Direction: design SQLite schema, startup behavior, transaction boundaries, and failure semantics as a separate implementation slice.

#### CL-P02 - Import/export contract

- Decision: **Partially implemented**
- Current: JSON import exists and validates ordinary malformed input.
- Missing from the proposed intent: durable transactional import, timestamp preservation policy, export, and round-trip tests.

#### CL-P03 - One-command application startup and configurable client endpoint

- Decision: **Not implemented**
- Current: the documented prototype uses one API process and one static-file process; the browser API base remains fixed at port 8000.
- Direction: serve the static UI from the application or introduce one launcher and a shared endpoint configuration before claiming the one-command experience.

#### CL-P04 - Stable newest-first ordering

- Decision: **Not implemented**
- Current repository order is insertion order, oldest first.
- Direction: define ordering at the repository/service boundary and protect it with API and browser tests.

### Lead recommendation

Keep all changes listed under **Accepted**. Before treating the complete working tree as integration-ready, repair `CL-H01` through `CL-H03`; include `CL-H04` if the goal is a clean domain boundary. Do not fold persistence or export into that bug-fix pass. Those are coherent next product slices and deserve their own contracts and tests.

### FN-LEAD - As-built architecture review draft (2026-09-13T03:20:18.951Z)

Added `docs/ARCHITECTURE_AS_IS.md` as a separate review draft. It maps the actual browser/API/service/repository/import paths and distinguishes current process-local storage from README_INTENT.md goals such as SQLite, export, and single-command startup. Existing docs/ARCHITECTURE.md and other agents files are unchanged by this task. No application implementation, Git staging, commit, or deployment. This entry is append-only. The working branch changed externally to codex/field-notes-triage during inspection; this task did not switch branches. Relative document links were checked before saving.

## Second-wave re-triage and resolution — 2026-09-18

### Live baseline

- Repository home: `/Users/jennifer/Bootwitch/Projects/doctor-repo-repair`.
- Starting public revision: `7e3b718` on `main`; the first repair milestone is
  `7c18e13`, and the deliberately broken fixture remains `1884f4d`.
- Baseline canonical check: 89 Python tests passed. A concurrent same-origin
  startup repair added one subprocess test, producing a 90-test intermediate
  gate.
- The original `field-notes-chaos-lab` path no longer existed. The commit graph,
  source tree, and configured GitHub remote established this repository as the
  migrated project rather than relying on the old path name.

### SW-C01 — Portable export was absent

- Observed: no export route, command, filesystem publisher, or recovery test.
- Accepted contract: `GET /api/export` returns the portable top-level `notes`
  document. The command reads through the running application. Default
  publication refuses an existing destination; `--replace` is explicit.
- Resolution: `fieldnotes/exporter.py` writes and fsyncs a temporary sibling,
  then publishes atomically. Failure removes the temporary and preserves prior
  destination bytes.
- Connection proof: the real export command reads a populated configured SQLite
  server; the real import command restores the result into a separate empty
  database; a new destination process returns equivalent ordered public fields
  and timestamps. IDs remain database-local.
- Status: **green**.

### SW-C02 — HTTP origin and media-type checks did not prevent writes

- Observed: CORS response headers were withheld for foreign origins, but POST and
  DELETE still mutated state. `Origin: null` was accepted, and JSON routes
  accepted missing or unrelated media types. `PATCH` returned HTML `501`.
- Resolution: browser origins must match the actual loopback host and port;
  opaque/foreign origins fail before mutation. CLI calls without `Origin` remain
  valid. JSON POST routes require `application/json`. `PUT` and `PATCH` reach the
  JSON API contract.
- Connection proof: real-socket tests assert both structured responses and the
  resulting public state for create, delete, media type, preflight, unsupported
  method, and oversized-body cases.
- Status: **green for the documented loopback topology**. This is not a hosted
  security policy.

### SW-C03 — Browser request completion order could lie to the user

- Observed: `form.reset()` erased newer text typed during a slow save; mutation
  refreshes bypassed the search generation guard; a committed mutation followed
  by refresh failure was presented as mutation failure.
- Resolution: one read-generation authority governs list, search, and refresh.
  Saves clear only fields unchanged since submission. Confirmed mutation success
  is separated from follow-up refresh failure.
- Evidence: two deterministic Node tests cover generation and draft clearing. A
  real headless-Chrome runner covers delayed save, out-of-order search, committed
  save plus failed refresh, delete, clean console, and 390px/desktop layouts.
- Status: **green**.

### SW-C04 — Domain edge cases crossed the wrong boundary

- Observed: direct deletion accepted booleans, floats, non-positive values, and
  values outside SQLite's positive integer range. Extremely long numeric path
  IDs could reach integer/storage behavior. Equivalent normalized tags remained
  duplicated.
- Resolution: service deletion accepts only positive non-boolean SQLite-range
  integers. The route rejects oversized numeric IDs as `400 invalid_note_id`.
  Create and import deduplicate normalized tags in first-seen order.
- Status: **green** through focused service, importer, and public API tests.

### SW-C05 — Local topology was split across two processes

- Observed at second-wave start: docs required a separate static file server and
  the browser hardcoded API port 8000.
- Concurrent repair accepted: one loopback process serves `web/` and `/api/*`;
  the browser uses relative requests and follows `FIELDNOTES_PORT`.
- Proof: real subprocess fetches HTML, JavaScript, and API from one origin.
- Status: **green**.

### Integrated gate and remaining limits

- `./scripts/check.sh`: 110 Python tests plus 2 JavaScript state tests pass.
- `node scripts/browser_acceptance.mjs`: all real-Chrome checks pass.
- Import error responses are explicitly closed; the Python 3.14 resource warning
  observed at baseline is gone.
- Deferred by contract: idempotency after an unknown post-commit import response,
  comprehensive external multi-process write behavior, and hosted-origin policy.
- Independent subagents were requested for export, runtime, and browser audits,
  but the account-wide subagent usage limit prevented those runs. No independent
  report is claimed; black-box evidence is labeled by the boundary it crosses.
