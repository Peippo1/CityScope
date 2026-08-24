# Google hackathon demo runbook

## Judge story (2–3 minutes)

1. Open the CityScope URL and point out the May 2026 TfL historical-snapshot notice.
2. Ask where Saturday-morning cycling activity was highest; open the evidence disclosure to show the deterministic City Data MCP provenance.
3. Ask which busy areas have few cafés; contrast the historical TfL panel with the separately labelled current Google Maps context.
4. Ask for a bicycle route between King's Cross and Borough; show the Google Routes attribution, route warning, and deterministic waypoint rationale.
5. If a live Maps, Routes, or Gemini provider is unavailable, show the explicit partial/error state rather than retrying in a loop.

## Cloud Run topology

- **Web** is public and receives only `NEXT_PUBLIC_*` browser configuration.
- **API** is public, accepts only the exact `CITYSCOPE_WEB_ORIGIN`, and receives Google/Gemini secrets from Secret Manager.
- **City Data MCP** has Cloud Run ingress `internal` and does not allow unauthenticated invocation. The API service account receives `roles/run.invoker`; set `CITYSCOPE_CITY_DATA_MCP_ID_TOKEN_AUDIENCE` to the MCP service URL.

Build API and MCP images from the repository root so the generated Parquet artifacts and production provenance manifest are included. `.gcloudignore` excludes raw TfL inputs and quarantine data. Before deployment run `python scripts/verify_deployment_artifact.py`; API `/ready` checks the same production checksum at runtime.

## Required configuration

Configure Secret Manager references for `GEMINI_API_KEY`, `GOOGLE_MAPS_GROUNDING_API_KEY`, and `GOOGLE_ROUTES_API_KEY`. Set `FIREBASE_PROJECT_ID` only after Firebase Authentication and Firestore are enabled. Firebase Web configuration is public build-time configuration; it must never contain an Admin SDK credential.

Configure the browser Maps key to the deployed web origin and allowed Maps APIs. Configure `CITYSCOPE_TRUSTED_HOSTS` with the deployed API host, and set `CITYSCOPE_WEB_ORIGIN` to the exact public web URL.

## Post-deploy smoke gate

Run one request each for historical hotspots, amenity enrichment, and a named-endpoint bicycle route. Check `/health` and `/ready`, verify source attribution is shown, and confirm provider failures display the bounded fallback. Record only status, source labels, and timestamps—never requests, provider payloads, headers, or credentials.
