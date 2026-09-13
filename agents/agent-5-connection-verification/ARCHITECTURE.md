# Agent 5 Architecture

## Evidence Path

```mermaid
flowchart LR
    Input["Observable input"] --> Entry["Real entry point"]
    Entry --> Boundary["Process or adapter boundary"]
    Boundary --> State["Expected state owner"]
    State --> Restart["Close and reopen boundary"]
    Restart --> Output["Observable output"]

    Failure["Controlled failure"] -.-> Boundary
    Boundary -.-> Rollback["Expected unchanged state"]
```

Agent 5 tests connections rather than substituting direct calls for them. For example, server persistence evidence must cross a real server-process restart, not merely construct the same repository twice in one test process.

## Verification Targets

```mermaid
flowchart TD
    SQLite["SQLite reopen"] --> Server["HTTP create survives restart"]
    Server --> Import["Batch import visible through API"]
    Import --> Atomic["Injected failure rolls back batch"]
    Atomic --> Export["Export restores equivalent records"]
    Export --> Hygiene["Runtime data stays out of Git"]
```

