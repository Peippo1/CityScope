# CityScope demo deployment runbook

## Required configuration

Keep these server-only values in the API environment, never in the web app:

- `GEMINI_API_KEY` — structured investigation planning.
- `GOOGLE_MAPS_GROUNDING_API_KEY` — Grounding MCP place resolution and search. `GOOGLE_MAPS_API_KEY` is a temporary server fallback.
- `GOOGLE_ROUTES_API_KEY` — direct bicycle Routes API execution. `GOOGLE_MAPS_API_KEY` is a temporary server fallback.
- `CITYSCOPE_CITY_DATA_MCP_URL` — City Data MCP endpoint.
- `CITYSCOPE_WEB_ORIGIN` — exact browser origin allowed by API CORS.
- `CITYSCOPE_TRUSTED_HOSTS` — comma-separated API Host header allowlist.
- `CITYSCOPE_CITY_DATA_MCP_ID_TOKEN_AUDIENCE` — private MCP Cloud Run service URL.
- `FIREBASE_PROJECT_ID` — enables Firebase token verification and Firestore-backed saved investigations.

The browser may receive only `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`. Restrict it in Google Cloud by HTTP referrer, enabled APIs, and quota. Do not put any server key in `NEXT_PUBLIC_*` variables.

## Local start

```bash
python3 -m pip install -e '.[dev]'
python3 -m pipelines.london_cycling.build_fixture
uvicorn services.city_data_mcp.server:app --port 8001
uvicorn apps.api.app.main:app --port 8000
cd apps/web && npm ci && npm run dev
```

Check `GET http://localhost:8000/health`. A `degraded` response identifies missing configuration names only; it never returns credential values.

## Minimal live route gate

Run local mocked tests first. For the optional live gate, use a single named-origin route and verify the trace contains no `routes.compute_routes` Gemini tool. The bounded route path permits two Grounding endpoint resolutions and one Routes API request. Do not run the gate in a loop or include Gemini unless agent planning itself is being tested.

Before public exposure, confirm `npm audit --audit-level=high`, `pip-audit --skip-editable`, `pytest -q`, `npm run build`, and `git diff --check` all pass. Never print `.env.local`, request headers, or raw provider responses containing credentials.

For the deployed judge walkthrough and Cloud Run topology, see [hackathon-demo.md](hackathon-demo.md). Run `python scripts/verify_deployment_artifact.py` before the image build and check API `GET /ready` after deployment.

Deploy `firestore.rules` with the Firebase CLI before enabling saved investigations. The rules deny browser Firestore access because all reads and writes must pass through the API's Firebase-token and ownership checks. See [privacy.md](privacy.md) for the POC retention disclosure.
