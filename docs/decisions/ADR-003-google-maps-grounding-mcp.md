# ADR-003: Google Maps Grounding Lite MCP for external place context

## Decision

Use Google's managed Maps Grounding Lite MCP endpoint as CityScope's V1 external place-context provider. The application connects to `https://mapstools.googleapis.com/mcp` over Streamable HTTP with a server-only `X-Goog-Api-Key` and allows only `search_places`.

City Data MCP remains authoritative for historical mobility. CityScope narrows candidate H3 cells first; the application derives H3 centroids and builds Google's exact `text_query`/`location_bias` request. The model cannot invent coordinates, Place IDs, or Maps links.

## Alternatives

- Direct Places REST API: deferred because this slice needs agentic place discovery, not exhaustive or reproducible amenity census. Reconsider only when deterministic batch coverage, pagination, or fields unavailable from Grounding Lite are required.
- Custom Google wrapper tools: rejected for V1 because it would duplicate Google's MCP contract and weaken the portfolio demonstration of external MCP consumption.
- General geographic knowledge from the LLM: rejected because it is neither current nor auditable and cannot supply trusted Place IDs, coordinates, links, or attribution.

## Deterministic enrichment contract

The allowlisted categories are `cafe`, `coffee_shop`, `bicycle_repair_shop`, and `restaurant`. Searches use controlled phrases, an 800 m circle around a canonical H3 centroid, at most five candidate cells, at most two categories, and at most ten returned places per search. The implementation caps the bounded search fan-out at ten Maps calls.

For each cell/category pair, the application reports the raw returned place count and a relative scarcity rank among the candidate cells. It sorts exploratory results by historical mobility value descending and place count ascending. It does not produce a business-success prediction or a falsely precise opportunity score.

## Compliance and deployment

Google Maps Grounding Lite requires the service enabled in a billed Google Cloud project, restricted credentials, and source attribution immediately adjacent to grounded output. Place results are request-scoped in V1; no caching or durable storage is introduced. The frontend browser Maps key remains separate from the backend Grounding credential. Review Google's current Maps Platform terms and model-data restrictions before public launch.
