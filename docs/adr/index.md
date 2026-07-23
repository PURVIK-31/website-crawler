# Architecture Decision Records

An Architecture Decision Record (ADR) captures a single significant decision:
its context, the decision itself, and the consequences. Records are immutable —
to change a decision, add a new ADR that supersedes the old one rather than
editing history.

Format follows [Michael Nygard's template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## Records

| ID | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-parquet-canonical-lancedb-derived.md) | Parquet is canonical, LanceDB is derived | Accepted |
| [0003](0003-single-node-v2-scope.md) | v2 knowledge ingestion is single-node, single-worker | Accepted |
| [0004](0004-ephemeral-jobs-durable-assets.md) | API jobs are ephemeral, assets are durable | Accepted |

## Adding a record

1. Copy the structure of an existing ADR.
2. Use the next sequential number (`NNNN-short-kebab-title.md`).
3. Start at status **Proposed**; move to **Accepted** once agreed.
4. Add a row to the table above.
