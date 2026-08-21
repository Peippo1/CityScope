# Bounded investigations

`POST /investigate` accepts a London question and bounded client-carried context. The FastAPI agent connects to `CITYSCOPE_CITY_DATA_MCP_URL` (default `http://localhost:8001/mcp/`) using the official MCP Python client. It never imports the analytics implementation directly.

The default model adapter is Gemini through `google-genai`, configured with `GEMINI_API_KEY` and optional `CITYSCOPE_GEMINI_MODEL`. The adapter returns a typed decision: call one of `describe_dataset`, `get_area_metrics`, `find_hotspots`, or `compare_areas`; answer; or reject the question as unsupported. The orchestration loop validates tool arguments, limits execution to three rounds, and returns the MCP dataset metadata, evidence, map layers, limitations, and a concise trace.

V1 supports historical London mobility questions only. It does not answer live weather or traffic, amenity discovery, routing, demographics, revenue, forecasts, unnamed-area questions, or other cities. No investigation state is stored server-side.

The 20 deterministic scope cases are in `evals/agent/cases.json`; service tests use a fake model and fake MCP client so they do not need credentials or a running MCP server.
