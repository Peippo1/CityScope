import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataFlowPanel } from "../components/visualization/DataFlowPanel";
import type { InvestigationResult } from "../types/investigation";

const result: InvestigationResult = {
  investigation_id: "flow-test",
  status: "answered",
  answer: "A grounded answer.",
  evidence: [],
  places: [],
  amenity_analysis: [],
  city_insights: [],
  map_layers: [],
  limitations: [],
  trace: [{ kind: "tool_call", label: "Called City Data MCP", status: "completed", latency_ms: 42 }],
  follow_up_suggestions: [],
};

describe("DataFlowPanel", () => {
  it("shows completed request stages from the investigation trace", () => {
    render(<DataFlowPanel activityLoading={false} investigating={false} result={result} />);

    expect(screen.getByRole("heading", { name: "Request flow" })).toBeVisible();
    expect(screen.getByText("City Data MCP").closest("li")).toHaveTextContent("42 ms");
    expect(screen.getByText("Visual answer").closest("li")).toHaveTextContent("Ready");
  });
});
