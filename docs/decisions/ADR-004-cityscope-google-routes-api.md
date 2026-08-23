# ADR-004: Use the Google Routes API as a private bicycle-routing adapter

## Decision

CityScope continues to use Google Maps Grounding Lite MCP for bounded `search_places` discovery and named endpoint resolution. Bicycle routes are computed by a backend-only `GoogleRoutesService` calling the official Google Routes API. Routes API is not exposed as a Gemini tool.

The agent may classify a request as `route.intent` and provide named endpoints. CityScope resolves those names through Grounding MCP, asks City Data MCP for historical hotspots, selects at most two corridor waypoints deterministically, and calls the Routes API with `travelMode=BICYCLE`. The browser receives the validated encoded polyline and renders it on Google Maps.

## Rationale

Grounding Lite's documented `compute_routes` surface supports driving and walking, but not bicycle routing, and its documented response does not provide route polyline geometry. Substituting walking or driving would misrepresent the user's request. The official Routes API supports bicycle mode and encoded polylines, so it is the correct deterministic execution boundary.

Place IDs are used for resolved endpoints when available; otherwise the adapter uses the coordinates returned by the trusted Maps resolver. Coordinates retain Google provenance. The API response is accepted only when it contains a positive distance, positive duration, and non-empty encoded polyline.

## Bounds and failure semantics

- At most two Grounding searches resolve the named endpoints.
- City Data supplies at most ten hotspot candidates; deterministic selection uses a 3 km corridor, a maximum 0.75 detour ratio, and at most two waypoints.
- The service makes one waypoint route attempt, then at most one direct-route fallback.
- The API key is server-side (`GOOGLE_ROUTES_API_KEY`); the browser key is never used for server routing.
- Bicycle routing is beta and may omit suitable paths; the warning is returned and displayed with every route.
- Route geometry is never fabricated. Failure returns historical route geography as partial evidence without a route line.
