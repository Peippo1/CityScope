# Google hackathon demo runbook

## Judge story (2–3 minutes)

1. Open the CityScope URL and show the four-city May 2026 comparison. Point out that it uses normalized metrics, never raw trip totals.
2. Select London, NYC, Chicago, or Washington, DC and ask where historical cycling activity was highest; open the evidence disclosure to show deterministic City Data MCP provenance.
3. Drill into New York City, switch from its historical activity to its Citi Bike live station map, and show bikes, docks, provider freshness, and the non-comparability statement. Switch to Paris to demonstrate the same bounded MCP contract across providers.
4. Return to London and ask which busy areas have few cafés, then request a bicycle route between King's Cross and Borough.
5. If a live provider is unavailable, show the explicit partial/error state rather than retrying in a loop.

## Cloud Run topology

- **Web** is public and receives only `NEXT_PUBLIC_*` browser configuration.
- **API** is public, accepts only the exact `CITYSCOPE_WEB_ORIGIN`, and receives Google/Gemini secrets from Secret Manager.
- **City Data MCP** has Cloud Run ingress `internal` and does not allow unauthenticated invocation. The API service account receives `roles/run.invoker`; set `CITYSCOPE_CITY_DATA_MCP_ID_TOKEN_AUDIENCE` to the MCP service URL.
- **City Live Data MCP** is independently IAM-protected and accepts only four registry-backed city IDs; callers cannot supply external URLs.

Build API and MCP images from the repository root so the generated Parquet artifacts and production provenance manifest are included. `.gcloudignore` excludes raw TfL inputs and quarantine data. Before deployment run `python scripts/verify_deployment_artifact.py`; API `/ready` checks the same production checksum at runtime.

## Required configuration

Configure Secret Manager references for `GEMINI_API_KEY`, `GOOGLE_MAPS_GROUNDING_API_KEY`, and `GOOGLE_ROUTES_API_KEY`. Set `FIREBASE_PROJECT_ID` only after Firebase Authentication and Firestore are enabled. Firebase Web configuration is public build-time configuration; it must never contain an Admin SDK credential.

Configure the browser Maps key to the deployed web origin and allowed Maps APIs. Configure `CITYSCOPE_TRUSTED_HOSTS` with the deployed API host, and set `CITYSCOPE_WEB_ORIGIN` to the exact public web URL.

## Post-deploy smoke gate

Run one request each for a normalized comparison, city drill-down, live NYC status, historical hotspots, amenity enrichment, and a named-endpoint bicycle route. Check `/health` and `/ready`, verify source attribution is shown, and confirm provider failures display the bounded fallback. Record only status, source labels, and timestamps, never requests, provider payloads, headers, or credentials.
