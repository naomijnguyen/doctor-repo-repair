# Agent 1 Architecture

## Owned View

```mermaid
flowchart LR
    A2["Agent 2<br/>SQLite adapter"] --> Lead["Agent 1<br/>contract and integration gate"]
    A3["Agent 3<br/>atomic import"] --> Lead
    A4["Agent 4<br/>runtime composition"] --> Lead
    A5["Agent 5<br/>connection evidence"] --> Lead
    Lead --> Forward["Updated forward trace"]
    Lead --> Backward["Updated backward trace"]
    Lead --> Next["Next red connection"]
```

## Integration Boundaries

- Repository contract between service/import and storage.
- Composition boundary between configuration and server repository selection.
- Transaction boundary between validated import data and committed notes.
- Evidence boundary between component tests and cross-process behavior.

Agent 1 integrates these boundaries but does not redesign unrelated amber behavior during the storage pass.

