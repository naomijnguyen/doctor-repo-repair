# Agent 3 Architecture

## Current Import Path

```mermaid
flowchart LR
    File["UTF-8 JSON file"] --> Validate["Validate complete payload"]
    Validate --> Loop["Loop over validated notes"]:::degraded
    Loop --> Post1["POST note 1"]
    Loop --> Post2["POST note 2"]
    Loop --> PostN["POST note N"]
    Post1 --> Stored["Earlier notes may be committed"]
    PostN -.-> Failure["Later failure can leave partial batch"]:::missing

    classDef degraded fill:#fef3c7,stroke:#b45309,color:#78350f,stroke-width:2px
    classDef missing fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d,stroke-width:2px
```

## Agent 3 Target

```mermaid
flowchart LR
    File["UTF-8 JSON file"] --> Validate["Validate complete payload"]
    Validate --> Batch["One batch request"]:::new
    Batch --> Service["Batch service operation"]:::new
    Service --> Transaction["One repository transaction"]:::new
    Transaction --> All["Commit all notes"]
    Transaction --> None["Rollback all notes on failure"]

    classDef new fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px
```

The repository transaction implementation belongs to Agent 2. Agent 3 owns the application-level meaning of a batch and the API/service connection into that transaction.

