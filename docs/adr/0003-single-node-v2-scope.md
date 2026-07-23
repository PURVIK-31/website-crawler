# ADR-0003: v2 knowledge ingestion is single-node, single-worker

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

A general ingestion platform might include a DAG engine, a distributed task
queue, multi-tenancy, and resumable jobs. Building those up front adds
substantial complexity and operational surface before the core value —
crawl → structure → chunk → embed → index — is proven.

## Decision

v2 is intentionally single-node and single-worker. The cache uses process-local
key locks (`KeyLocks`), and the pipeline assumes one writer. We explicitly
exclude, for now: a DAG engine, a distributed queue, multi-tenancy, and
resumable/distributed execution.

## Consequences

- The design stays small and easy to reason about; atomic file writes plus a
  single writer are sufficient for correctness.
- Deployments must run with `WORKERS=1` for the knowledge layer.
- Horizontal scale and resumability are deferred. Introducing them later will
  require revisiting locking and job persistence (see
  [ADR-0004](0004-ephemeral-jobs-durable-assets.md)) and should be recorded in a
  superseding ADR.
