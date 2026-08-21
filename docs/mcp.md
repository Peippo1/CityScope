# City Data MCP

CityScope exposes four deterministic analytics tools through a small MCP server:

- `describe_dataset`
- `get_area_metrics`
- `find_hotspots`
- `compare_areas`

The server is a thin protocol adapter. It validates typed inputs, delegates to `MobilityAnalytics`, and returns a structured envelope containing dataset metadata, evidence, map layers, and limitations. It does not contain SQL, table names, source-specific rules, Places calls, or agent behavior.

## Local server

```bash
uvicorn services.city_data_mcp.server:app --port 8001
```

The Streamable HTTP endpoint is `http://localhost:8001/mcp/`. The official Python SDK is used for both the server and the local client harness. Streamable HTTP is used because it is the current deployable MCP transport; persistent MCP sessions are not required.

## Example request

```json
{
  "city": "london",
  "metric": "total_activity",
  "limit": 5,
  "time_filter": {
    "weekend": true,
    "hour_start": 9,
    "hour_end": 12
  }
}
```

Every analytical response has this shape:

```json
{
  "dataset": {"city": "london", "historical": true},
  "results": [],
  "evidence": [],
  "map_layers": [],
  "limitations": []
}
```

The contract is model-provider-neutral. Any MCP-compatible client can discover and call the same tools; no agent framework is required.
