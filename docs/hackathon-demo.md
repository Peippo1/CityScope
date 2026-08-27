# Google hackathon demo runbook

## Judge story (2–3 minutes)

1. Open the CityScope URL, choose **Compare demand intensity**, and submit the cross-city question. Show that the agent selects the bounded `compare_cities` workflow, then open the trace and point out that rankings use normalized metrics, never raw trip totals.
2. Select London, NYC, Chicago, or Washington, DC and ask where historical cycling activity was highest; open the evidence disclosure to show deterministic City Data MCP provenance.
3. Drill into New York City, switch from its historical activity to its Citi Bike live station map, and show bikes, docks, provider freshness, and the non-comparability statement. Switch to Paris to demonstrate the same bounded MCP contract across providers.
4. Return to London and ask which busy areas have few cafés, then request a bicycle route between King's Cross and Borough.
5. If a live provider is unavailable, show the explicit partial/error state rather than retrying in a loop.

## Cloud Run topology

- **Web** is public and receives only `NEXT_PUBLIC_*` browser configuration.
- **API** is public, accepts only the exact `CITYSCOPE_WEB_ORIGIN`, and receives Google/Gemini secrets from Secret Manager.
- **City Data MCP** has Cloud Run ingress `internal` and does not allow unauthenticated invocation. The API service account receives `roles/run.invoker`; set `CITYSCOPE_CITY_DATA_MCP_ID_TOKEN_AUDIENCE` to the MCP service URL.
- **City Live Data MCP** is independently IAM-protected and accepts only four registry-backed city IDs; callers cannot supply external URLs.

Build API and MCP images from the repository root so the generated Parquet artifacts, comparison matrix, and production provenance manifest are included. Run `.venv/bin/python -m pipelines.multicity.build_comparison` after promoting the complete cohort. `.gcloudignore` excludes raw TfL inputs and quarantine data. Before deployment run `python scripts/verify_deployment_artifact.py`; API `/ready` checks the production checksums at runtime.

## Required configuration

Configure Secret Manager references for `GEMINI_API_KEY`, `GOOGLE_MAPS_GROUNDING_API_KEY`, and `GOOGLE_ROUTES_API_KEY`. Set `FIREBASE_PROJECT_ID` only after Firebase Authentication and Firestore are enabled. Firebase Web configuration is public build-time configuration; it must never contain an Admin SDK credential.

Configure the browser Maps key to the deployed web origin and allowed Maps APIs. Configure `CITYSCOPE_TRUSTED_HOSTS` with the deployed API host, and set `CITYSCOPE_WEB_ORIGIN` to the exact public web URL.

## Post-deploy smoke gate

Run one agent-submitted normalized comparison and one direct metric change, followed by city drill-down, live NYC status, historical hotspots, amenity enrichment, and a named-endpoint bicycle route. Check `/health` and `/ready`, verify the `compare_cities` trace and source attribution are shown, and confirm provider failures display the bounded fallback. Record only status, source labels, and timestamps, never requests, provider payloads, headers, or credentials.

Run all offline tests and artifact builders before starting the local reload-enabled services. Then run provider-backed smoke requests one at a time so file-watcher reloads cannot interrupt an MCP session.
