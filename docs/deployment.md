# CityScope demo deployment runbook

## Deployment topology

- Firebase Hosting serves the static Next.js export.
- A public Cloud Run service hosts the FastAPI API.
- An IAM-private Cloud Run service hosts deterministic City Data MCP. A separate IAM-private Cloud Run service hosts the live Paris MCP; only the API service account has `roles/run.invoker` on either service.
- An hourly Cloud Scheduler-triggered Cloud Run job writes compressed Paris GBFS station snapshots to a private Cloud Storage bucket. It is the only identity allowed to write that bucket.
- Artifact Registry stores the API, MCP, live MCP, and collector images in `europe-west2`.
- Secret Manager supplies only server-side Gemini and Google API keys.

Cloud Run, Artifact Registry, Cloud Build, and Secret Manager require billing on the GCP project. Link a billing account to `cityscope-506222` before running the one-time setup below.

## One-time GCP setup

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com \
  --project cityscope-506222

gcloud artifacts repositories create cityscope \
  --repository-format docker \
  --location europe-west2 \
  --project cityscope-506222
```

Create separate least-privilege service accounts for the API and MCP before deploying. The API account needs `roles/run.invoker` on the MCP service and Firestore access; the MCP account does not need access to Firebase or provider secrets.

## Build container images

The generated production Parquet and metadata artifacts are part of both build contexts. Verify them before spending a remote build:

```bash
.venv/bin/python scripts/verify_deployment_artifact.py

gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions _DOCKERFILE=deploy/Dockerfile.mcp,_IMAGE=europe-west2-docker.pkg.dev/cityscope-506222/cityscope/mcp:latest \
  --project cityscope-506222

gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions _DOCKERFILE=deploy/Dockerfile.live_mcp,_IMAGE=europe-west2-docker.pkg.dev/cityscope-506222/cityscope/live-mcp:latest \
  --project cityscope-506222

gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions _DOCKERFILE=deploy/Dockerfile.api,_IMAGE=europe-west2-docker.pkg.dev/cityscope-506222/cityscope/api:latest \
  --project cityscope-506222

gcloud builds submit . \
  --config deploy/cloudbuild.yaml \
  --ignore-file deploy/paris-collector.gcloudignore \
  --substitutions _DOCKERFILE=deploy/Dockerfile.paris_collector,_IMAGE=europe-west2-docker.pkg.dev/cityscope-506222/cityscope/paris-collector:latest \
  --project cityscope-506222
```

## Paris archive

The demo project uses these provisioned resources:

- bucket `cityscope-paris-velib-archive-506222`, regional `europe-west2`, uniform access, public access prevention;
- Cloud Run job `cityscope-paris-collector`;
- collector identity `cityscope-paris-collector@cityscope-506222.iam.gserviceaccount.com`, with bucket-level `roles/storage.objectCreator` only;
- scheduler identity `cityscope-paris-scheduler@cityscope-506222.iam.gserviceaccount.com`, with `roles/run.invoker` on the collector job only;
- Scheduler job `cityscope-paris-hourly`, running `0 * * * *` in UTC.

The collector joins the fixed official Vélib' `station_information` and `station_status` feeds by station ID, validates the merged rows, and archives every valid station. Objects are gzip-compressed and partitioned by UTC year/month/day/hour. The provider timestamp is part of the filename and uploads use a generation precondition, making retries idempotent for an unchanged provider snapshot. The archive remains trend-ineligible until a meaningful history exists.

Deploy MCP first with authentication required and its exact Cloud Run hostnames in `deploy/mcp.env.yaml`. Use `all` ingress unless both services are attached to a VPC path that Cloud Run recognizes as internal. Deploy the API second, granting only its service account permission to invoke MCP. The non-secret API settings live in `deploy/api.env.yaml`; Secret Manager references are supplied separately during deployment.

## Publish Firebase Hosting

Build the static web app only after the public API URL is known. The wrapper forwards `NEXT_PUBLIC_*` values from the root `.env.local` without passing server credentials to Next.js:

```bash
NEXT_PUBLIC_CITYSCOPE_API_URL=https://API_SERVICE_URL \
  .venv/bin/python scripts/build_web.py

npx firebase-tools deploy --only hosting --project cityscope-506222
```

The default Hosting URL is `https://cityscope-506222.web.app`. Add that origin to `CITYSCOPE_WEB_ORIGIN` on the API and confirm it appears in Firebase Authentication's authorized domains before the public smoke test.

## Required configuration

Keep these server-only values in the API environment, never in the web app:

- `GEMINI_API_KEY` — structured investigation planning.
- `GOOGLE_MAPS_GROUNDING_API_KEY` — Grounding MCP place resolution and search. `GOOGLE_MAPS_API_KEY` is a temporary server fallback.
- `GOOGLE_ROUTES_API_KEY` — direct bicycle Routes API execution. `GOOGLE_MAPS_API_KEY` is a temporary server fallback.
- `CITYSCOPE_CITY_DATA_MCP_URL` — City Data MCP endpoint.
- `CITYSCOPE_CITY_LIVE_DATA_MCP_URL` — live Paris MCP endpoint.
- `CITYSCOPE_CITY_LIVE_DATA_MCP_ID_TOKEN_AUDIENCE` — private live MCP Cloud Run service URL used to mint the API identity token.
- `CITYSCOPE_PARIS_ARCHIVE_BUCKET` — private Cloud Storage bucket used only by the archive job.
- `CITYSCOPE_WEB_ORIGIN` — exact browser origin allowed by API CORS.
- `CITYSCOPE_TRUSTED_HOSTS` — comma-separated API Host header allowlist.
- `CITYSCOPE_CITY_DATA_MCP_ID_TOKEN_AUDIENCE` — private MCP Cloud Run service URL.
- `CITYSCOPE_MCP_ALLOWED_HOSTS` — exact MCP Cloud Run Host header allowlist used by MCP DNS-rebinding protection.
- `FIREBASE_PROJECT_ID` — enables Firebase token verification and Firestore-backed saved investigations.

The browser may receive only `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`. Restrict it in Google Cloud by HTTP referrer, enabled APIs, and quota. For the map and Places explorer, enable Maps JavaScript API, Places UI Kit, and Places API (New) on this browser key. Do not put any server key in `NEXT_PUBLIC_*` variables. Places UI Kit is current user-facing context and must not be presented as historical mobility evidence.

## Local start

```bash
python3 -m pip install -e '.[dev]'
python3 -m pipelines.london_cycling.build_fixture
python3 -m pipelines.multicity.build_fixture
uvicorn services.city_data_mcp.server:app --port 8001
uvicorn services.city_live_data_mcp.server:app --port 8002
uvicorn apps.api.app.main:app --port 8000
cd apps/web && npm ci && npm run dev
```

Check `GET http://localhost:8000/health`. A `degraded` response identifies missing configuration names only; it never returns credential values.

## Minimal live route gate

Run local mocked tests first. For the optional live gate, use a single named-origin route and verify the trace contains no `routes.compute_routes` Gemini tool. The bounded route path permits two Grounding endpoint resolutions and one Routes API request. Do not run the gate in a loop or include Gemini unless agent planning itself is being tested.

Before public exposure, confirm `npm audit --audit-level=high`, `pip-audit --skip-editable`, `pytest -q`, `npm run build`, and `git diff --check` all pass. Never print `.env.local`, request headers, or raw provider responses containing credentials.

For the deployed judge walkthrough and Cloud Run topology, see [hackathon-demo.md](hackathon-demo.md). Run `python scripts/verify_deployment_artifact.py` before the image build and check API `GET /ready` after deployment.

Deploy `firestore.rules` with the Firebase CLI before enabling saved investigations. The rules deny browser Firestore access because all reads and writes must pass through the API's Firebase-token and ownership checks. See [privacy.md](privacy.md) for the POC retention disclosure.
