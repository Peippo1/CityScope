# Bounded investigations

```text
question -> Gemini planner -> City Data MCP -> trusted H3 candidates
                           \-> Maps Grounding Lite MCP -> current places
                                -> deterministic counts/ranks -> answer + map
```

`POST /investigate` accepts a registry-backed city and bounded client-carried context. The FastAPI agent connects to `CITYSCOPE_CITY_DATA_MCP_URL` (default `http://localhost:8001/mcp/`) using the official MCP Python client. It never imports the analytics implementation directly. Historical investigations support London, New York City, Chicago, and Washington, DC; current station availability uses a separately deployed live-data MCP for NYC, Chicago, Washington, DC, and Paris.

The default model adapter is Gemini through `google-genai`, using stable `gemini-3.5-flash` unless overridden by `CITYSCOPE_GEMINI_MODEL`. The API loads the repository-root `.env.local` at startup. The adapter returns a typed decision: call an approved City Data or live-data tool, call the internal `maps.search_places` boundary, answer, or reject the question as unsupported. Cross-city results are synthesized deterministically from the typed `compare_cities` response after Gemini selects the normalized metric; no second model call can alter the ranking. The orchestration loop validates tool arguments and returns dataset metadata, source-tagged evidence, map layers, current places, limitations, and a concise trace.

Historical mode supports single-city mobility questions, bounded amenity enrichment around trusted in-city H3 cells, named-endpoint bicycle routes, and normalized four-city comparisons. Live mode supports current station availability only. Route intent is model-classified, but endpoint resolution, waypoint selection, and the private Google Routes API request remain deterministic backend operations. It does not answer live weather or traffic, demographics, revenue, forecasts, cross-city raw-volume rankings, cross-city routes, or historical Paris demand. Saved investigations retain historical evidence only; current provider payloads and route geometry are excluded.

The versioned golden dataset is in `evals/agent/cases.json`. Run it without credentials or provider traffic:

```bash
python -m evals.agent.runner --json-output /tmp/cityscope-eval-report.json
```

The evaluator uses fake Gemini, City Data, Maps, and Routes adapters, exits non-zero on regression, and is the authoritative CI evaluation gate. Live and LLM-as-judge evaluations are opt-in only.

## Guardrails and telemetry

One deterministic policy boundary runs before planning, after model decisions, before provider calls, and before response delivery. Public errors remain generic; trace events expose stable policy codes and bounded call metadata without raw provider payloads.

`CITYSCOPE_TELEMETRY=local` writes sanitized JSON metadata by default. Use `off` to disable it. Optional LangSmith export requires installing `.[observability]`, setting `CITYSCOPE_TELEMETRY=langsmith`, a server-only `LANGSMITH_API_KEY`, and a non-zero `LANGSMITH_SAMPLE_RATE`. A sample rate of `0.0` exports nothing. Prompts, questions, headers, credentials, place payloads, and route geometry are outside the telemetry schema, and export failures never fail investigations. LangChain is not used.

With `GEMINI_API_KEY`, `GOOGLE_MAPS_GROUNDING_API_KEY`, and both MCP endpoints configured, run the opt-in smoke test with `python3 scripts/smoke_grounding.py`. It is intentionally excluded from automated CI. Run offline pytest and artifact-building checks before starting the reload-enabled local stack, then run live provider smoke tests serially; fixture builds modify generated artifacts and can otherwise trigger MCP reloads during an in-flight request.

Google Cloud setup requires billing and the Maps Grounding Lite API enabled. Restrict the backend key to the required API and server deployment; never place `GOOGLE_MAPS_GROUNDING_API_KEY` in frontend configuration. The browser `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` is a separate, referrer-restricted key for map rendering. Google source links and attribution returned by `search_places` are preserved on each place result.
