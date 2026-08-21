# CityScope

CityScope is an agentic geospatial intelligence application for investigating historical London cycling activity. This repository currently contains the first deterministic vertical slice: cycling fixture data is transformed into H3-indexed Parquet, queried with DuckDB, served by FastAPI, and rendered on a Google Map.

## First vertical slice

```text
fixture CSV -> validation/transform -> H3 -> Parquet -> DuckDB -> FastAPI -> Next.js -> map layer
```

The slice deliberately does not include MCP, an LLM, Google Places, SSE, follow-ups, ranking, or authentication.

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
