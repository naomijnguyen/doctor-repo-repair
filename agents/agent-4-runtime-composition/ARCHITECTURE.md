# Agent 4 Architecture

## Current Composition

```mermaid
flowchart LR
    Config["fieldnotes/config.py<br/>data path available"]:::degraded
    Server["fieldnotes/server.py"]
    Memory["new NoteRepository()"]
    Tool["tools/import_sample.py"]
    API["running HTTP API"]

    Config -.->|"data path unused"| Memory
    Server --> Memory
    Tool --> API

    classDef degraded fill:#fef3c7,stroke:#b45309,color:#78350f,stroke-width:2px
```

## Agent 4 Target

```mermaid
flowchart LR
    Config["Canonical database configuration"] --> Factory["Repository factory"]:::new
    Factory --> SQLite["Accepted SQLite adapter"]
    Server["Server entry point"] --> Factory
    Import["Import command"] --> Batch["Accepted batch path"]
    Export["Export command"] --> Factory
    Batch --> SQLite
    Export --> SQLite

    classDef new fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px
```

The first active connection is server to configured SQLite. Import and export connections activate only after their preceding gates pass.

