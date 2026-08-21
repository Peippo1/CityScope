# ADR-002: MCP as the external contract around shared deterministic analytics

## Status

Accepted

## Decision

Expose a bounded set of CityScope analytics through the official Python MCP SDK and Streamable HTTP. MCP tool handlers remain thin adapters over the shared `MobilityAnalytics` layer.

## Alternatives considered

- Direct internal function calls only: simplest, but does not prove an external interoperable analytics contract.
- FastAPI-only tool endpoints: useful for the web application, but couples the tool interface to the application API rather than MCP-compatible clients.
- Arbitrary SQL or tool-generated queries: flexible but unsafe, non-deterministic, and exposes storage details to clients.

MCP is useful here because it makes the deterministic domain operations discoverable and consumable by multiple model providers without coupling the analytics implementation to any one agent framework.

## Consequences

- The MCP surface is deliberately smaller than the internal analytics layer.
- Input limits and allowlisted metrics are part of the public contract.
- No arbitrary SQL, database schema, named-area resolution, Places enrichment, or persistent MCP sessions are exposed.
