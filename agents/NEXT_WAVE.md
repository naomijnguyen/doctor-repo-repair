# Field Notes: Second-Wave Agent Assignments

## Shared objective

Move Field Notes from a durable lower-path repair to a coherent local beta.
Preserve the verified CLI -> HTTP -> service -> SQLite path while adding portable
export, tightening the local trust boundary, and making browser state honest
under slow or failed requests.

The current canonical check passes 89 tests. Every agent must inspect the live
working tree before acting; historical triage and agent notes are evidence, not
proof of current behavior.

## Coordination order

1. Agent 5 writes or records black-box acceptance cases without editing
   production files.
2. Agent 1 accepts shared contracts and freezes file ownership.
3. Agents 2, 3, and 4 implement in their disjoint lanes.
4. Agent 5 independently runs the real entry-point and failure tests.
5. Agent 1 reconciles docs, traces, and the final integration result.

No agent commits, merges, resets, pushes, or removes another lane's work. Stop at
the written handoff when a change crosses an owned boundary.

## Agent 1: Architecture and integration lead

### Owns

- `agents/shared/`
- `agents/Jen Study Notes/`
- final reconciliation of `README.md`, `PROJECT_STATE.md`, and `docs/`
- shared-contract acceptance and integration order

### To do

- Accept or revise the export format, overwrite policy, and recovery semantics
  before Agent 2 connects a public entry point.
- Freeze the trust-boundary rules Agent 4 will enforce: allowed origins,
  same-origin requests, JSON media type, and unsupported methods.
- Confirm Agent 3's narrow API/domain rules do not conflict with Agent 4's
  transport layer.
- Keep forward and backward traces aligned with evidence after each accepted
  connection.
- Review the full diff for stale historical claims, accidental duplication, and
  ownership collisions.
- Run the canonical check, diff check, secret scan, and runtime-data hygiene
  check before the next local commit.

### Acceptance evidence

- Every current-state document agrees with the live implementation.
- The shared map distinguishes green, amber, and red without relying on test
  counts alone.
- The final handoff names what is verified, what is inferred, and what remains.

## Agent 2: Portable atomic export

### Owns

- new export implementation files, preferably `fieldnotes/exporter.py`
- new export command, preferably `tools/export_notes.py`
- focused exporter tests
- storage-specific export support only when the accepted contract requires it

### To do

- Propose the portable JSON shape using the current top-level `notes` array and
  public note fields.
- Propose explicit destination behavior: fail if a file exists by default, with
  replacement allowed only through an intentional option.
- Write exports through a temporary file in the destination directory, flush and
  close successfully, then publish with an atomic replacement step.
- Preserve an existing valid destination byte-for-byte when export fails.
- Preserve timestamps and public fields needed for import recovery.
- Keep export on the application authority boundary; do not open a second SQLite
  writer from the command.
- Avoid changing `fieldnotes/api.py`, `fieldnotes/server.py`, or browser files
  until Agent 1 accepts the public export route.

### Acceptance evidence

- Populated notes export to readable UTF-8 JSON.
- A controlled write/publish failure leaves the previous destination unchanged.
- Exporting an empty collection produces a valid empty document.
- Exported content can be imported into a separate empty database and recovered
  under the accepted local-ID policy.

## Agent 3: API and domain hardening

### Owns

- `fieldnotes/api.py`
- `fieldnotes/service.py`
- normalization/domain helpers when required
- focused API and service tests

### To do

- Reject extremely long numeric delete IDs as structured `400 invalid_note_id`
  responses rather than allowing integer conversion to reach a server `500`.
- Require positive, non-boolean integer IDs at the direct service boundary.
- Reconcile duplicate normalized tags with `README_INTENT.md`: deduplicate while
  preserving first-seen order, unless Agent 1 records a different contract.
- Record the current unknown-field policy for create and import payloads; do not
  silently change it while documenting it.
- Keep `ImportValidationError` narrow so storage failures continue to reach the
  server's generic `500` boundary.
- Do not edit transport origin checks or browser code; those belong to Agent 4.

### Acceptance evidence

- Direct service and public API tests cover boolean, float, negative, malformed,
  and very long identifiers.
- API errors remain structured and do not mutate state.
- Equivalent duplicate tags normalize to one stored value in stable order.
- Existing atomic-import and storage-failure classification tests remain green.

## Agent 4: Runtime, HTTP boundary, and browser-state repair

Agent 4 may use two subagents, but the sublanes must remain separate until Agent
4 reviews their shared assumptions.

### Sublane 4A: HTTP and runtime

Own `fieldnotes/server.py`, `fieldnotes/config.py`, composition changes, and new
transport-level tests.

- Reject disallowed origins on state-changing requests; withholding CORS response
  headers is not enough to prevent a write.
- Remove normal mutation support for opaque `Origin: null` if HTTP-served UI is
  the accepted launch path.
- Require the intended JSON media type for JSON mutation routes.
- Route unsupported methods through the JSON API contract instead of returning
  the base server's HTML `501` page.
- Propose and implement one coherent local topology: preferably serve static UI
  and API from one process/origin. Do not claim one-command startup until it is
  tested.
- Preserve loopback-only binding and configured storage lifecycle behavior.

### Sublane 4B: Browser request state

Own `web/app.js`, `web/api.js`, and browser-specific tests after Sublane 4A
freezes the endpoint behavior.

- Prevent a slow save from erasing a newer draft typed after submission.
- Use one generation/invalidation policy so late list or refresh responses cannot
  overwrite a newer search result.
- Separate confirmed mutation success from a later refresh failure.
- Keep delete controls and form controls in honest pending, success, and failure
  states.
- Preserve safe text rendering, keyboard behavior, and narrow-screen layout.

### Acceptance evidence

- Real HTTP tests cover allowed and disallowed origins, JSON media type,
  preflight, unsupported methods, body limits, and structured errors.
- One documented command starts the accepted local topology and prints the exact
  browser URL.
- Browser tests reproduce and close the slow-save, stale-refresh, and
  mutation-success/refresh-failure cases.

## Agent 5: Independent connection verifier

### Owns

- new black-box, subprocess, and browser acceptance tests
- verification notes in `agents/agent-5-connection-verification/NOTES.md`
- no production implementation files

### To do

- Write the acceptance matrix for export, HTTP trust boundaries, local startup,
  and browser request ordering before implementation claims are accepted.
- Verify export through the real command or public route against a populated
  server and configured SQLite database.
- Import the export into a separate empty database and compare recovered public
  records under the accepted ID policy.
- Force export failure and prove the prior destination is byte-for-byte intact.
- Exercise actual listening-server behavior for origins, content type,
  unsupported methods, and configured port/startup.
- Exercise browser workflows at narrow and desktop widths, including delayed and
  failed responses.
- Report component proof separately from connection proof.

### Acceptance evidence

- Each new connection has one success case and one failure case.
- Tests cross the real boundary being claimed rather than replacing it with a
  mock.
- No SQLite database, sidecar, temporary export, or browser artifact is left
  tracked or unignored after verification.

## Final integration gate

The second wave is complete only when:

- `./scripts/check.sh` passes on the supported Python runtime;
- browser and real HTTP acceptance checks pass;
- portable export survives a round trip into a separate database;
- a failed export preserves the previous destination;
- the UI and API use one documented local topology;
- all current-state docs agree with the code; and
- Agent 1 redraws both traces from the final evidence.
