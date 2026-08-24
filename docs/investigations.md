# Bounded investigations

```text
question -> Gemini planner -> City Data MCP -> trusted H3 candidates
                           \-> Maps Grounding Lite MCP -> current places
                                -> deterministic counts/ranks -> answer + map
```

`POST /investigate` accepts a London question and bounded client-carried context. The FastAPI agent connects to `CITYSCOPE_CITY_DATA_MCP_URL` (default `http://localhost:8001/mcp/`) using the official MCP Python client. It never imports the analytics implementation directly.

The default model adapter is Gemini through `google-genai`, using stable `gemini-3.5-flash` unless overridden by `CITYSCOPE_GEMINI_MODEL`. The API loads the repository-root `.env.local` at startup. The adapter returns a typed decision: call one of the four City Data tools, call the internal `maps.search_places` boundary, answer, or reject the question as unsupported. The orchestration loop validates tool arguments, limits the decision sequence to City Data → Maps → synthesis, and returns dataset metadata, source-tagged evidence, map layers, current places, limitations, and a concise trace.

V1 supports historical London mobility questions, bounded amenity enrichment around trusted H3 cells, and named-endpoint bicycle routes. Route intent is model-classified, but endpoint resolution, waypoint selection, and the private Google Routes API request remain deterministic backend operations. It does not answer live weather or traffic, demographics, revenue, forecasts, unnamed-area questions, or other cities. No investigation state is stored server-side.

The versioned golden dataset is in `evals/agent/cases.json`. Run it without credentials or provider traffic:

```bash
python -m evals.agent.runner --json-output /tmp/cityscope-eval-report.json
```

The evaluator uses fake Gemini, City Data, Maps, and Routes adapters, exits non-zero on regression, and is the authoritative CI evaluation gate. Live and LLM-as-judge evaluations are opt-in only.

## Guardrails and telemetry

One deterministic policy boundary runs before planning, after model decisions, before provider calls, and before response delivery. Public errors remain generic; trace events expose stable policy codes and bounded call metadata without raw provider payloads.

`CITYSCOPE_TELEMETRY=local` writes sanitized JSON metadata by default. Use `off` to disable it. Optional LangSmith export requires installing `.[observability]`, setting `CITYSCOPE_TELEMETRY=langsmith`, a server-only `LANGSMITH_API_KEY`, and a non-zero `LANGSMITH_SAMPLE_RATE`. A sample rate of `0.0` exports nothing. Prompts, questions, headers, credentials, place payloads, and route geometry are outside the telemetry schema, and export failures never fail investigations. LangChain is not used.

With `GEMINI_API_KEY`, `GOOGLE_MAPS_GROUNDING_API_KEY`, and both MCP endpoints configured, run the opt-in smoke test with `python3 scripts/smoke_grounding.py`. It is intentionally excluded from automated CI.

Google Cloud setup requires billing and the Maps Grounding Lite API enabled. Restrict the backend key to the required API and server deployment; never place `GOOGLE_MAPS_GROUNDING_API_KEY` in frontend configuration. The browser `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` is a separate, referrer-restricted key for map rendering. Google source links and attribution returned by `search_places` are preserved on each place result.
