# CityScope

**An evidence-grounded London journey planner for better bicycle days out.**

[![CityScope checks](https://github.com/Peippo1/CityScope/actions/workflows/ci.yml/badge.svg)](https://github.com/Peippo1/CityScope/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=nextdotjs)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Auth%20%2B%20Firestore-FFCA28?logo=firebase&logoColor=black)
![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Cloud%20Run%20%2B%20Maps-4285F4?logo=googlecloud&logoColor=white)
![License](https://img.shields.io/badge/license-private-lightgrey)

CityScope turns a natural-language outing request into a bounded, traceable London journey plan: named endpoints, a scenic or quiet bicycle route, useful bathroom/coffee/lunch stops, and interesting places to explore. Historical bike-share activity remains hidden supporting evidence for corridor selection; Compare and Live modes remain available as secondary views. It combines deterministic H3 and DuckDB analytics with a Google ADK Runner and root LlmAgent powered by Gemini 3.5 Flash, current Google Maps context, bicycle routing, and user-owned investigation history. ADK plans bounded actions; the application remains authoritative for MCP execution, waypoint selection, Routes, validation, and provenance.

**[Open the live CityScope app](https://cityscope-506222.web.app)**

## Product tour

![CityScope London mobility workspace](docs/assets/cityscope-dashboard.png)

CityScope keeps the map, interactive activity chart, request flow, and investigation controls in one workspace. Every visual separates pinned historical activity snapshots from optional current station availability, Google Maps context, and Google bicycle routes.

![CityScope bicycle route result from Kings Cross to Borough](docs/assets/cityscope-route-planning.png)

<p align="center">
  <img src="docs/assets/cityscope-mobile.png" width="320" alt="CityScope mobile investigation workspace" />
</p>

The current prototype can:

- plan a London journey with outbound and optional return-loop bicycle legs;
- use curated London route ideas including Richmond Park, Thames Path, Regent's Canal, Greenwich, Wandle Trail, Lee Valley, and Epping Forest as scenic planning templates;
- use city-specific route ideas for New York City, Chicago, and Washington, DC when those route-capable workspaces are selected;
- explore curated European route concepts in Paris, Copenhagen, Barcelona, and Madrid; these are route-planning cities without historical CityScope mobility snapshots;
- suggest bounded Google Maps stops for coffee, bathrooms, lunch, shops, or repairs;
- accept optional browser-native voice input in the journey composer;
- keep H3 activity as an optional evidence layer rather than the primary map UI;
- compare those four cities using trips per active station/day, median duration, peak-hour share, weekend share, and hotspot concentration;
- inspect optional live station maps for NYC, Chicago, Washington, DC, and Paris without mixing availability into historical demand rankings;
- enrich trusted areas with current Google Maps place context;
- compute deterministic bicycle routes through selected activity areas;
- explore selectable activity charts and a request-flow view driven by real API trace state;
- show source-tagged evidence, dataset provenance, limitations, and execution traces;
- authenticate users with Google and save investigations through a Firebase-token-verified API.

> Historical comparisons use a matched May 2026 window and normalized metrics only. Activity is observed bike-share data, not a census of private or dockless cycling. Station availability is optional operational context, not historical trip demand. CityScope does not claim live cycling conditions, weather, traffic, or forecasts.

## All Things Agentic Hackathon

CityScope is being built for the [All Things Agentic Hackathon](https://allthingsagentichackathon.devpost.com/), using Gemini 3.5 Flash through the Google GenAI SDK and production services on Google Cloud. The recommended submission category is **Taskmaster**: one bounded investigation can classify a goal, query deterministic city analytics, resolve current places, compute a bicycle route, and return a traceable visual result.

- [Read the build story](docs/blog/building-cityscope.md)
- [Review the Devpost submission draft](docs/devpost-submission.md)
- [Follow the four-minute demo plan](docs/hackathon-demo.md)

## Architecture

[Open the editable system architecture and investigation flow in FigJam](https://www.figma.com/board/qfv9Yo1Z88fcn7FBArJeTG)

```mermaid
flowchart LR
    user["Browser"] --> web["Next.js web app"]
    web -->|"HTTPS + JSON"| api["FastAPI API"]
    web -.->|"Google sign-in"| auth["Firebase Authentication"]

    api -->|"Bounded MCP tools"| mcp["City Data MCP"]
    mcp -->|"DuckDB queries"| data[("Versioned Parquet + metadata")]
    api -->|"User-owned records"| firestore[("Firestore")]
    api -.->|"Verify ID token"| auth
    api -.->|"ADK Runner + root LlmAgent"| gemini["Gemini 3.5 Flash"]
    api -.->|"Place context"| maps["Maps Grounding Lite"]
    api -.->|"Bicycle route"| routes["Google Routes API"]
    gemma["Optional Gemma 4 scorer"] -.-> api

    sources["TfL + Citi Bike + Divvy + Capital Bikeshare"] --> pipeline["Validation + H3 pipeline"]
    pipeline --> data
    gbfs["Fixed official live feeds (NYC + US + Paris)"] --> live["City Live Data MCP"]
    live --> api
```

The FastAPI service is the trust boundary. Browser Firestore access is denied; authenticated history operations pass a Firebase ID token to the API, which verifies ownership before reading or writing Firestore. The City Data MCP remains deterministic and private behind the API.

## Data Flow

```text
Official trip snapshots -> validate and normalize -> H3 aggregation -> Parquet -> DuckDB
                                                               |
question -> ADK root planner -> City Data MCP -------------------+
                          \-> Maps and Routes -> evidence-grounded result
Optional live feeds -> City Live Data MCP -> validated, labelled station context
```

Generated artifacts retain checksums, per-reason reconciliation counts, local observation period, source attribution, and snapshot metadata. The production build accepts official CSV or ZIP archives in bounded chunks. Large raw, generated, and quarantine datasets are intentionally excluded from Git.

> A clean checkout uses clearly labelled deterministic fixtures until the official May 2026 source files are built with `pipelines.multicity.build_production`. The verified cohort build accepts 653,075 Chicago trips, 588,599 Washington, DC trips, and 4,680,767 New York trips; London contributes 854,872 accepted TfL trips. Fixture comparisons remain visibly labelled and must not be treated as findings.

After building or promoting all four production city artifacts, generate the fingerprint-bound comparison matrix:

```bash
.venv/bin/python -m pipelines.multicity.build_comparison
```

The API uses this small artifact for low-latency comparison reads only while its snapshot IDs, artifact names, and source checksums match the selected cohort. Missing or stale matrices fall back to deterministic Parquet calculations.

## Quick Start

Prerequisites: Python 3.11+, Node.js 20+, and npm.

Install dependencies and build the deterministic fixture:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pipelines.london_cycling.build_fixture
python -m pipelines.multicity.build_fixture

cd apps/web
npm install
cd ../..
```

Create `.env.local` from [`.env.example`](.env.example) and add only the providers you intend to use. Browser configuration belongs in `apps/web/.env.local`; never place server credentials in a `NEXT_PUBLIC_*` variable.

Start the complete local stack from the repository root:

```bash
python scripts/dev.py
```

The supervisor stops the whole stack if any service exits, preventing a web-only partial startup. It forwards only `NEXT_PUBLIC_*` values from the root `.env.local` to Next.js; server credentials are not passed to the web process. To run services independently, use three terminals:

```bash
# Terminal 1: deterministic City Data MCP
.venv/bin/uvicorn services.city_data_mcp.server:app --reload --port 8001

# Terminal 2: optional live station MCP
.venv/bin/uvicorn services.city_live_data_mcp.server:app --reload --port 8002

# Terminal 3: public API
.venv/bin/uvicorn apps.api.app.main:app --reload --port 8000

# Terminal 4: web app
cd apps/web
npm run dev
```

Open the URL printed by Next.js. Check API configuration at `http://localhost:8000/health` and dataset readiness at `http://localhost:8000/ready`.

### Configuration

Server-side configuration includes:

- `GEMINI_API_KEY` for structured investigation planning;
- `GOOGLE_MAPS_GROUNDING_API_KEY` for place search and endpoint resolution;
- `GOOGLE_ROUTES_API_KEY` for bicycle routing;
- `FIREBASE_PROJECT_ID` for token verification and saved investigations;
- `CITYSCOPE_CITY_DATA_MCP_URL` for the private MCP endpoint.
- `CITYSCOPE_CITY_LIVE_DATA_MCP_URL` for the private live-data MCP endpoint.
- `CITYSCOPE_PARIS_ARCHIVE_BUCKET` for the hourly private GBFS archive job.

The live MCP joins fixed official feeds for Citi Bike, Divvy, Capital Bikeshare, and Vélib'. London remains historical-only because Santander supply is not representative of the wider cycling market. Paris remains the archive pilot: its deployed collector stores full validated snapshots hourly in a private regional bucket, and the UI exposes no trend claim until the archive is sufficiently mature.

The web app uses separately restricted public configuration:

- `NEXT_PUBLIC_CITYSCOPE_API_URL`;
- `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`;
- `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, and `NEXT_PUBLIC_FIREBASE_APP_ID`.

The browser Places explorer uses the same referrer-restricted browser key. In Google Cloud, enable Maps JavaScript API, Places UI Kit, and Places API (New) for that key. Places UI Kit results are current Google Places context and are intentionally separate from historical bike-share evidence.

Without a browser Maps key, CityScope keeps the ranked textual experience available and displays a labelled map placeholder. Missing server providers produce bounded degraded or partial states rather than ungrounded answers.

## Repository Map

| Path | Responsibility |
| --- | --- |
| `apps/web` | Next.js investigation workspace, map, Firebase client auth |
| `apps/api` | FastAPI routes, policy boundary, agent orchestration, saved history |
| `services/city_data_mcp` | Stateless MCP tools over deterministic city analytics |
| `pipelines` | Source adapters, validation, H3 transforms, artifact builds |
| `evals` | Deterministic agent regression cases and runner |
| `docs` | Architecture decisions, deployment, data provenance, privacy |

## Verification

```bash
pytest -q
python -m evals.agent.runner --json-output /tmp/cityscope-eval-report.json

cd apps/web
npm test
npm run test:e2e
npm run build
```

CI also runs Python and npm dependency audits and whitespace checks. Live Gemini, Maps, and Routes smoke tests are deliberately opt-in so routine test runs do not consume provider quota.

The scheduled `cohort-source-monitor` validates monthly that the pinned production manifests still describe one matched snapshot and that every official source remains reachable. It does not silently replace the evidence window; promoting a new common month requires the same ingestion, reconciliation, checksum, and review gates as May 2026.

## Documentation

- [Investigation model and guardrails](docs/investigations.md)
- [Data foundation and provenance](docs/data-foundation.md)
- [Cloud Run deployment runbook](docs/deployment.md)
- [Hackathon demo flow](docs/hackathon-demo.md)
- [Privacy and saved-investigation handling](docs/privacy.md)
- [Architecture decisions](docs/decisions)
