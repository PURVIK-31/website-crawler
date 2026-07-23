# ADR-0004: API jobs are ephemeral, assets are durable

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The REST API tracks crawl jobs in an in-memory dictionary (`_jobs`). This state
is lost on restart. Meanwhile, the knowledge layer persists versioned assets with
manifests that fully describe each run. The question is whether to invest in
durable job tracking now.

## Decision

Keep the two concerns separate: **jobs remain ephemeral, assets remain durable.**
Job status/history is a convenience view over in-flight work; the authoritative,
replayable record of a completed run is its asset manifest under
`storage/assets/<asset_id>/<asset_version>/`.

## Consequences

- No database or extra infrastructure is needed for the API to be useful.
- After a restart, completed work is still discoverable via asset manifests, even
  though transient job status is gone.
- Persistent job tracking is deferred. We introduce it only if/when resumable or
  distributed execution is added (see
  [ADR-0003](0003-single-node-v2-scope.md)) — at which point this decision is
  superseded by a new ADR.
