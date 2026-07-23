# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The v2 knowledge ingestion layer introduced several non-obvious design choices
(canonical vs. derived storage, single-node scope, ephemeral job state). These
decisions are easy to misread from the code alone, and the reasoning behind them
was previously scattered across commit messages and a prose architecture page.

## Decision

We will keep Architecture Decision Records under `docs/adr/`, one file per
decision, using Michael Nygard's template. Records are immutable; a superseding
ADR replaces an outdated one. The `architecture.md` page holds diagrams only —
all rationale lives here.

## Consequences

- Design rationale has a single, durable home that survives refactors.
- The architecture diagram page stays small and stable.
- Contributors incur a small overhead: significant decisions require an ADR.
