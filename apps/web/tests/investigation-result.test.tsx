import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { InvestigationResultPanel } from "../components/investigation/InvestigationResultPanel";
import type { InvestigationResult } from "../types/investigation";

const routeResult: InvestigationResult = {
  investigation_id: "route-test",
  status: "answered",
  answer: "A bicycle route connects the two selected London locations.",
  dataset: { dataset_name: "TfL Cycling", observation_start: "2026-05-01", observation_end: "2026-05-31", historical: true, attribution_text: "TfL" },
  evidence: [{ source: "city_data", metric: "total_journeys", value: 42, unit: "journeys", source_aggregate: "find_hotspots", h3_cells: ["89194ad3353ffff"] }],
  places: [], amenity_analysis: [], city_insights: [], map_layers: [], limitations: [], trace: [], follow_up_suggestions: [],
  route: {
    travel_mode: "bicycle", distance_m: 2400, duration_seconds: 900, polyline: "encoded-route", source: "google_routes_api",
    attribution_title: "Google Routes API", attribution_url: "https://developers.google.com/maps/documentation/routes",
    warning: "Verify bicycle conditions locally.",
    origin: { name: "King's Cross", latitude: 51.53, longitude: -0.12 },
    destination: { name: "Borough", latitude: 51.5, longitude: -0.11 },
    waypoints: [{ h3_cell: "89194ad3353ffff", latitude: 51.51, longitude: -0.115, mobility_value: 42, score: 0.8, reason: "Selected from historical activity." }],
  },
};

describe("InvestigationResultPanel", () => {
  it("presents a bicycle route with provenance, metrics, rationale, and warning", () => {
    render(<InvestigationResultPanel result={routeResult} onSuggestion={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Bicycle route" })).toBeVisible();
    expect(screen.getByText(/King's Cross/)).toBeVisible();
    expect(screen.getByText("2.4 km")).toBeVisible();
    expect(screen.getByText("15 min")).toBeVisible();
    expect(screen.getByText("Selected from historical activity.")).toBeVisible();
    expect(screen.getByText("Verify bicycle conditions locally.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Google Routes API" })).toHaveAttribute("href", routeResult.route?.attribution_url);
  });

  it("keeps current Google Maps places visibly separate from historical evidence", () => {
    render(<InvestigationResultPanel result={{
      ...routeResult,
      route: undefined,
      answer: "This busy area has one returned café.",
      evidence: [
        ...routeResult.evidence,
        { source: "google_maps", metric: "place_count", value: 1, unit: "places", source_aggregate: "maps.search_places", h3_cells: ["89194ad3353ffff"], category: "cafe" },
      ],
      places: [{ place_id: "place-cafe", name: "Example Café", latitude: 51.51, longitude: -0.115, maps_uri: "https://maps.google.com/example", category: "cafe", h3_cell: "89194ad3353ffff" }],
    }} onSuggestion={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Historical mobility evidence" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Current Google Maps context" })).toBeVisible();
    expect(screen.getByText((_, node) => node?.textContent === "Cafe · Google Maps provider result")).toBeVisible();
    expect(screen.getByRole("link", { name: "View on Google Maps" })).toHaveAttribute("href", "https://maps.google.com/example");
  });

  it("shows each Maps place once when provider results repeat a place identifier", () => {
    render(<InvestigationResultPanel result={{
      ...routeResult,
      route: undefined,
      evidence: [],
      places: [
        { place_id: "repeat-place", name: "Repeated Cafe", latitude: 51.51, longitude: -0.115, category: "cafe", h3_cell: "89194ad3353ffff" },
        { place_id: "repeat-place", name: "Repeated Cafe", latitude: 51.51, longitude: -0.115, category: "cafe", h3_cell: "89194ad3203ffff" },
      ],
    }} onSuggestion={vi.fn()} />);

    expect(screen.getAllByText("Repeated Cafe")).toHaveLength(1);
  });

  it("labels unsupported outcomes without rendering credential values", () => {
    render(<InvestigationResultPanel result={{
      ...routeResult,
      status: "unsupported",
      route: undefined,
      evidence: [],
      answer: "Weather is unsupported. API key: AIza123456789012345678901234567890",
      trace: [{ kind: "policy", label: "authorization=Bearer-secret-value", status: "reject", policy_code: "unsupported_weather" }],
    }} onSuggestion={vi.fn()} />);

    expect(screen.getByText("Not supported")).toBeVisible();
    expect(document.body).not.toHaveTextContent("AIza123456789012345678901234567890");
    expect(document.body).not.toHaveTextContent("Bearer-secret-value");
    expect(document.body).toHaveTextContent("[redacted]");
  });

  it("lets a user choose a follow-up without automatically submitting it", async () => {
    const user = userEvent.setup();
    const onSuggestion = vi.fn();
    render(<InvestigationResultPanel result={{ ...routeResult, follow_up_suggestions: ["Compare this with Saturday mornings"] }} onSuggestion={onSuggestion} />);

    await user.click(screen.getByRole("button", { name: "Compare this with Saturday mornings" }));

    expect(onSuggestion).toHaveBeenCalledWith("Compare this with Saturday mornings");
  });
});
