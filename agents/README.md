# Field Notes Multi-Agent Repair Workspace

This folder coordinates five agent conversations repairing Field Notes from the storage boundary outward. The shared objective is to fix missing connections before polishing components that already carry traffic.

## Current Snapshot

- Repository: this Git repository (clone path varies by machine)
- Branch observed: `codex/field-notes-triage`
- Baseline commit: `1884f4d785f2c3042792d45854e06c0837599408`
- Working tree: intentionally dirty with prior multi-agent changes
- Current check: 89 tests passing after durable runtime, atomic import, CLI,
  rollback, and process-restart verification
- Important: inspect the live working tree; the baseline commit does not reproduce it

Do not revert, reset, overwrite, commit, merge, or push unless Jennifer explicitly asks. Work with existing changes and report unexpected edits rather than removing them.

Three earlier agents have already explored the repository broadly. These packages are focused implementation deep dives, not requests to repeat the general audit. Use the prior architecture and triage documents as source notes, then verify the current code only where it affects the assigned connection.

## Shared Material

Read these before beginning:

1. [`shared/ARCHITECTURE_MAPS.md`](shared/ARCHITECTURE_MAPS.md) - current architecture, backward trace, ideal architecture, and repair flow.
2. [`../diagrams/plans/CONNECTION_FIRST_REPAIR_PLAN.md`](../diagrams/plans/CONNECTION_FIRST_REPAIR_PLAN.md) - approved connection-first sequence and acceptance gates.
3. [`../docs/ARCHITECTURE_AS_IS.md`](../docs/ARCHITECTURE_AS_IS.md) - detailed pre-repair source snapshot. Some importer details predate the first connection fix.
4. [`../TRIAGE.md`](../TRIAGE.md) - findings and prior acceptance evidence.
5. [`shared/HANDOFF_TEMPLATE.md`](shared/HANDOFF_TEMPLATE.md) - required update format.
6. [`shared/SHARED_NOTES.md`](shared/SHARED_NOTES.md) - lead-consolidated cross-agent ledger.
7. [`NEXT_WAVE.md`](NEXT_WAVE.md) - second-wave ownership, dependencies, and
   acceptance evidence for all five agents.

## Roles

| Agent | Name | Primary responsibility | Package |
| --- | --- | --- | --- |
| 1 | Architecture and Integration Lead | Contracts, connection order, integration, trace updates | [`agent-1-integration-lead/README.md`](agent-1-integration-lead/README.md) |
| 2 | Durable Storage Owner | SQLite adapter, schema, repository conformance | [`agent-2-durable-storage/README.md`](agent-2-durable-storage/README.md) |
| 3 | Atomic Import Owner | Batch contract, validation, rollback semantics | [`agent-3-atomic-import/README.md`](agent-3-atomic-import/README.md) |
| 4 | Runtime Composition and Portability Owner | Repository selection, runtime wiring, CLI and export | [`agent-4-runtime-composition/README.md`](agent-4-runtime-composition/README.md) |
| 5 | Independent Connection Verifier | Black-box persistence, cross-process, and round-trip evidence | [`agent-5-connection-verification/README.md`](agent-5-connection-verification/README.md) |

Each role folder uses the same four-document shape:

- `README.md`: what the agent owns and why it matters.
- `ARCHITECTURE.md`: current and target connections for that assignment.
- `TECHNICAL.md`: source boundaries, contract details, and acceptance evidence.
- `NOTES.md`: observations, decisions, gotchas, and the eventual handoff.

## Coordination Rules

1. Each agent writes detailed work notes only in its own `NOTES.md`.
2. Agent 1 consolidates accepted cross-agent information into `shared/SHARED_NOTES.md`.
3. Subagents may inspect anything but must remain read-only outside their parent agent's owned files.
4. No two agents edit the same production file in the same wave.
5. Proposed shared-contract changes stop at a written proposal until Agent 1 accepts them.
6. Every new connection needs one success proof and one failure proof.
7. After each accepted update, Agent 1 redraws both the forward and backward traces before the next connection is activated.
8. Amber cleanup waits unless it directly blocks a red connection test.

## Update Cycle

For every agent update:

1. Agent records findings and exact evidence in its own `NOTES.md`.
2. Agent returns the handoff template in its conversation.
3. Jennifer brings the update to Agent 1.
4. Agent 1 verifies changed files and tests.
5. Agent 1 updates `shared/SHARED_NOTES.md`.
6. Agent 1 redraws the forward trace: entry point to outcome.
7. Agent 1 redraws the backward trace: outcome to state owner.
8. The team chooses the next missing red connection from the new evidence.
