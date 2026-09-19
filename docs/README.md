# Field Notes Documentation

## Start here

- [`../README.md`](../README.md) is the friendly project overview and quick start.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) explains the current system, request flows,
  state ownership, and failure boundaries.
- [`TECHNICAL.md`](TECHNICAL.md) is the implementation readthrough.
- [`API.md`](API.md) documents the public HTTP contract.
- [`REPAIR_JOURNEY.md`](REPAIR_JOURNEY.md) tells the before, intermediate, and
  after story, including Jennifer's orchestration decisions.
- [`STATUS.md`](STATUS.md) separates verified local-beta behavior from explicit
  remaining limits.
- [`../README_INTENT.md`](../README_INTENT.md) records the product target and
  acceptance requirements.

## Historical material

[`ARCHITECTURE_AS_IS.md`](ARCHITECTURE_AS_IS.md) is the source-derived snapshot
from before durable runtime and atomic import were connected. It is intentionally
preserved as evidence of the starting architecture, not as current documentation.

The full repair history, agent handoffs, and evolving diagrams live under
[`../agents/`](../agents/). For a readable explanation of the five-agent repair,
start with [`REPAIR_JOURNEY.md`](REPAIR_JOURNEY.md).
