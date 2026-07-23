# Knowledge Ingestion Invariants

- Processors never mutate their input contracts.
- Given the same input and configuration, processors produce identical output.
- Completed asset versions and cache objects are immutable.
- Parquet assets are canonical; LanceDB is rebuildable derived state.
- AI is optional and disabled by default.
- Every artifact has provenance, schema/version metadata, and a SHA-256 checksum.
- Every cache entry includes processor, configuration, and provider identity.
- Processors do not import FastAPI; crawler modules do not import knowledge providers.
- Storage code does not import provider implementations.
- The v2 pipeline is explicitly ordered. It is not a DAG engine.
