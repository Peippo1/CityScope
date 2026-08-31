import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { InvestigationResultPanel } from "../components/investigation/InvestigationResultPanel";
import type { InvestigationResult } from "../types/investigation";

const result: InvestigationResult = {
  investigation_id: "route", status: "answered", answer: "A route worth remembering.", evidence: [], amenity_analysis: [], city_insights: [], map_layers: [], limitations: ["Verify surfaces locally."], trace: [], follow_up_suggestions: [],
  places: [{ place_id: "cafe", name: "Example Cafe", latitude: 51.5, longitude: -0.1, maps_uri: "https://maps.google.com/example", category: "cafe", h3_cell: "cell" }, { place_id: "cafe", name: "Example Cafe", latitude: 51.5, longitude: -0.1, category: "cafe", h3_cell: "cell2" }],
  route: { travel_mode: "walking", distance_m: 10000, duration_seconds: 3600, polyline: "route", source: "google_routes_api", attribution_url: "https://developers.google.com/maps/documentation/routes", warning: "Verify surfaces locally.", origin: { name: "Brooklyn", latitude: 40.68, longitude: -73.97 }, destination: { name: "Prospect Park", latitude: 40.66, longitude: -73.97 }, waypoints: [] },
  journey_plan: { summary: "Brooklyn to Prospect Park", segments: [], selected_stops: [], warnings: [], provenance: [], template_tags: [], template_waypoint_hints: [] },
};

describe("InvestigationResultPanel", () => {
  it("renders only the concise route summary and human stop labels", () => {
    render(<InvestigationResultPanel result={result} onSuggestion={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Your run" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Brooklyn → Prospect Park" })).toBeVisible();
    expect(screen.getByText("10.0 km")).toBeVisible();
    expect(screen.getByText("Coffee stop")).toBeVisible();
    expect(screen.getAllByText("Example Cafe")).toHaveLength(1);
    expect(screen.queryByText("Historical mobility evidence")).not.toBeInTheDocument();
    expect(screen.queryByText("Investigation trace")).not.toBeInTheDocument();
  });

  it("focuses a place when its compact stop card is selected", async () => {
    const user = userEvent.setup();
    const onSelectPlace = vi.fn();
    render(<InvestigationResultPanel result={result} onSuggestion={vi.fn()} onSelectPlace={onSelectPlace} />);
    await user.click(screen.getByRole("button", { name: /Example Cafe/ }));
    expect(onSelectPlace).toHaveBeenCalledWith(expect.objectContaining({ place_id: "cafe" }));
  });

  it("keeps share and save-compatible route actions available", () => {
    render(<InvestigationResultPanel result={result} onSuggestion={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Share to my phone" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Google Routes" })).toHaveAttribute("href", "https://developers.google.com/maps/documentation/routes");
  });
});
