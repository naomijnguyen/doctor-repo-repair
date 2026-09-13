# Agent 2 Architecture

## Current Connection

```mermaid
flowchart LR
    Service["NoteService"] --> MemoryRepo["In-memory NoteRepository"]
    MemoryRepo --> Memory["Process memory"]
    MemoryRepo -.-> Missing["No durable adapter"]:::missing
    Missing -.-> Disk[("No database connection")]:::missing

    classDef missing fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d,stroke-width:2px
```

## Agent 2 Target

```mermaid
flowchart LR
    Contract["Repository operation contract"] --> MemoryRepo["In-memory adapter"]
    Contract --> SQLiteRepo["SQLite adapter"]:::new
    SQLiteRepo --> Database[("SQLite database")]:::new

    classDef new fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px
```

The new adapter remains disconnected from `server.py` during this assignment. Agent 1 and Agent 4 handle runtime selection after reopen evidence passes.

