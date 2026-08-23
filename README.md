# CityScope

CityScope is an agentic geospatial intelligence application for investigating historical London cycling activity. This repository contains a deterministic H3/DuckDB data slice plus a bounded natural-language investigation layer that consumes the City Data MCP over Streamable HTTP.

## First vertical slice

```text
fixture CSV -> validation/transform -> H3 -> Parquet -> DuckDB -> FastAPI -> Next.js -> map layer
```

The investigation slice deliberately does not include Google Places, Maps Grounding MCP, SSE, follow-ups, ranking, or authentication.

## Run the data pipeline

```bash
python3 -m pip install -e '.[dev]'
python3 -m pipelines.london_cycling.build_fixture
# With the ignored TfL raw snapshot acquired:
python3 -m pipelines.build_production
```

The production build reads the pinned May 2026 TfL snapshot from `data/raw/tfl/may-2026/`, writes versioned Parquet artifacts under `data/generated/`, writes unmatched/invalid rows under `data/quarantine/`, and records checksums and reconciliation counts in `data/metadata/london-cycling-production.json`.

## Run the API

```bash
uvicorn apps.api.app.main:app --reload --port 8000
```

The API loads the repository-root `.env.local` automatically, regardless of the directory from which `uvicorn` is launched. Keep that file local and use `GOOGLE_MAPS_GROUNDING_API_KEY` for the server-side Maps Grounding key; `GOOGLE_MAPS_API_KEY` remains supported as a backwards-compatible fallback.

Run the City Data MCP in a second process before using `/investigate`:

```bash
uvicorn services.city_data_mcp.server:app --reload --port 8001
```

Configure `GEMINI_API_KEY` for the Gemini structured-output planner. Grounding MCP remains the place-search adapter; bicycle routes use the private Routes API adapter and are never exposed as a Gemini tool. See [docs/investigations.md](docs/investigations.md) and [ADR-004](docs/decisions/ADR-004-cityscope-google-routes-api.md).

## Run the web app

```bash
cd apps/web
npm install
npm run dev
```

Set `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` for a live Google Map. Without it, the page shows a clearly labelled map placeholder while still rendering the activity list.

## Test

```bash
pytest
```

The small fixture remains useful for fast tests. The production/demo dataset is the authoritative TfL May 2026 snapshot documented in [docs/data-foundation.md](docs/data-foundation.md). Large raw and generated artifacts are intentionally excluded from Git.
