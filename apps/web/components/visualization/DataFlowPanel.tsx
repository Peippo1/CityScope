import type { InvestigationResult } from "../../types/investigation";

type DataFlowPanelProps = { activityLoading: boolean; investigating: boolean; result: InvestigationResult | null };
type FlowStatus = "waiting" | "active" | "complete" | "failed";

export function DataFlowPanel({ activityLoading, investigating, result }: DataFlowPanelProps) {
  const mcpTrace = result?.trace.find((event) => event.tool?.includes("city_data") || event.label.includes("City Data MCP"));
  const googleUsed = Boolean(result?.places.length || result?.route);
  const resultFailed = result?.status === "failed";
  const stages: { label: string; detail: string; status: FlowStatus }[] = [
    { label: "TfL snapshot", detail: activityLoading ? "Loading" : "Ready", status: activityLoading ? "active" : "complete" },
    { label: "CityScope API", detail: investigating ? "Reasoning" : result ? "Complete" : "Standing by", status: investigating ? "active" : result ? (resultFailed ? "failed" : "complete") : "waiting" },
    { label: "City Data MCP", detail: investigating ? "Querying" : mcpTrace?.latency_ms !== undefined ? `${mcpTrace.latency_ms} ms` : result ? "Not used" : "Waiting", status: investigating ? "active" : mcpTrace ? (mcpTrace.status === "failed" ? "failed" : "complete") : "waiting" },
    { label: "Google services", detail: investigating ? "On demand" : googleUsed ? (result?.route ? "Route ready" : `${result?.places.length ?? 0} places`) : "Not used", status: investigating ? "active" : googleUsed ? "complete" : "waiting" },
    { label: "Visual answer", detail: investigating ? "Building" : result ? (resultFailed ? "Needs attention" : "Ready") : "Waiting", status: investigating ? "active" : result ? (resultFailed ? "failed" : "complete") : "waiting" },
  ];

  return (
    <section className="flow-panel" aria-labelledby="request-flow-heading">
      <header className="panel-heading">
        <div><p className="eyebrow">System trace</p><h2 id="request-flow-heading">Request flow</h2></div>
        <span className={`flow-state ${investigating ? "is-active" : ""}`}>{investigating ? "Processing" : "On demand"}</span>
      </header>
      <ol className="flow-list">
        {stages.map((stage, index) => (
          <li className={`flow-step flow-step--${stage.status}`} key={stage.label}>
            <span className="flow-index" aria-hidden="true">{index + 1}</span>
            <span className="flow-copy"><strong>{stage.label}</strong><small>{stage.detail}</small></span>
          </li>
        ))}
      </ol>
    </section>
  );
}
