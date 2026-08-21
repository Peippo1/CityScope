# Bounded investigations

```text
question -> Gemini planner -> City Data MCP -> trusted H3 candidates
                           \-> Maps Grounding Lite MCP -> current places
                                -> deterministic counts/ranks -> answer + map
```

`POST /investigate` accepts a London question and bounded client-carried context. The FastAPI agent connects to `CITYSCOPE_CITY_DATA_MCP_URL` (default `http://localhost:8001/mcp/`) using the official MCP Python client. It never imports the analytics implementation directly.

The default model adapter is Gemini through `google-genai`, configured with `GEMINI_API_KEY` and optional `CITYSCOPE_GEMINI_MODEL`. The adapter returns a typed decision: call one of the four City Data tools, call the internal `maps.search_places` boundary, answer, or reject the question as unsupported. The orchestration loop validates tool arguments, limits the decision sequence to City Data → Maps → synthesis, and returns dataset metadata, source-tagged evidence, map layers, current places, limitations, and a concise trace.

V1 supports historical London mobility questions and bounded amenity-enriched exploration around trusted H3 cells. It does not answer live weather or traffic, routing, demographics, revenue, forecasts, unnamed-area questions, or other cities. No investigation state is stored server-side. Historical evidence is labelled separately from current Google Maps context; returned place counts are not exhaustive amenity censuses.

The 20 deterministic scope cases are in `evals/agent/cases.json`; service tests use a fake model and fake MCP client so they do not need credentials or a running MCP server.

With `GEMINI_API_KEY`, `GOOGLE_MAPS_GROUNDING_API_KEY`, and both MCP endpoints configured, run the opt-in smoke test with `python3 scripts/smoke_grounding.py`. It is intentionally excluded from automated CI.

Google Cloud setup requires billing and the Maps Grounding Lite API enabled. Restrict the backend key to the required API and server deployment; never place `GOOGLE_MAPS_GROUNDING_API_KEY` in frontend configuration. The browser `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` is a separate, referrer-restricted key for map rendering. Google source links and attribution returned by `search_places` are preserved on each place result.
