# ADR-001: Deterministic data-to-map vertical slice

## Status

Accepted

## Decision

The first implementation slice will stop at a deterministic H3 activity layer. It will validate a small real-data-shaped London cycling fixture, derive temporal fields and H3 cells, write Parquet, query it with DuckDB, expose a typed FastAPI endpoint, and render the result in the Next.js interface.

MCP, an LLM, Google Places, SSE, follow-ups, ranking, authentication, and durable investigation state are intentionally deferred until this path is verified.

## Rationale

This proves the core data contract and makes failures observable at the boundary where they occur. It also prevents the agent layer from masking problems in schema validation, spatial indexing, aggregation, API serialization, or map rendering.

## Consequences

- The current fixture is small and is not production coverage.
- Generated Parquet is a build artifact and is ignored by Git.
- Google Maps rendering requires a restricted browser API key; the UI retains an accessible fallback when it is absent.
- H3 cell IDs are the only spatial IDs returned by the activity endpoint.
