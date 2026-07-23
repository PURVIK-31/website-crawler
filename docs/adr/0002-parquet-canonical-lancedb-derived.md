# ADR-0002: Parquet is canonical, LanceDB is derived

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The knowledge layer persists pages, chunks, and embeddings, and also needs a
vector index for similarity search. We must decide which representation is the
source of truth. Vector databases evolve quickly and their on-disk formats are
not stable long-term contracts; a columnar file format is.

## Decision

Parquet artifacts written by `AssetStore` are the canonical, versioned source of
truth. The LanceDB vector store is a **derived index** that can be rebuilt at any
time from the embedding artifacts. Manifests reference the Parquet artifacts with
SHA-256 checksums; the vector index is never treated as authoritative.

## Consequences

- The vector index can be dropped and rebuilt without data loss.
- We can migrate or replace the vector backend without touching canonical data.
- Writes cost slightly more: embeddings are persisted to Parquet *and* indexed.
- Search correctness depends on the query embedding profile matching the asset's
  indexed profile — enforced at the API layer with a `409` mismatch response.
