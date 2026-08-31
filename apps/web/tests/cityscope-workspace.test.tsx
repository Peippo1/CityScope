import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CityScopeWorkspace } from "../components/investigation/CityScopeWorkspace";

const routeResult = {
  investigation_id: "route", status: "answered" as const, answer: "A lovely route with places to pause.", evidence: [], amenity_analysis: [], city_insights: [], map_layers: [], limitations: [], trace: [], follow_up_suggestions: [],
  places: [{ place_id: "cafe", name: "Example Cafe", latitude: 51.5, longitude: -0.1, category: "cafe", h3_cell: "cell" }],
  route: { travel_mode: "bicycle" as const, distance_m: 4000, duration_seconds: 1200, polyline: "route", source: "google_routes_api" as const, warning: "Check conditions locally.", origin: { name: "Fulham", latitude: 51.47, longitude: -0.2 }, destination: { name: "Richmond Park", latitude: 51.44, longitude: -0.27 }, waypoints: [] },
};

describe("CityScopeWorkspace", () => {
  it("renders the route-first workspace without legacy evidence panels or activity requests", async () => {
    const investigate = vi.fn();
    render(<CityScopeWorkspace services={{ investigate }} />);
    expect(screen.getByRole("heading", { name: "Find a route worth remembering." })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Where will you explore?" })).toBeVisible();
    expect(screen.queryByText("Highest activity areas")).not.toBeInTheDocument();
    expect(screen.queryByText("Request flow")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Compare" })).not.toBeInTheDocument();
  });

  it("submits a city-aware running prompt and renders the concise route result", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(routeResult);
    render(<CityScopeWorkspace services={{ investigate }} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "City" }), "new_york");
    await user.click(screen.getByRole("button", { name: /Running/ }));
    await user.type(screen.getByRole("textbox", { name: "Question" }), "A 10K around Brooklyn with coffee");
    await user.click(screen.getByRole("button", { name: "Create route" }));
    expect(investigate).toHaveBeenCalledWith(expect.objectContaining({ city: "new_york", question: "A 10K around Brooklyn with coffee" }));
    expect(await screen.findByText("A lovely route with places to pause.")).toBeVisible();
    expect(screen.getByText("Good places to pause")).toBeVisible();
  });

  it("resets the previous result when switching cities", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(routeResult);
    render(<CityScopeWorkspace services={{ investigate }} />);
    await user.type(screen.getByRole("textbox", { name: "Question" }), "Fulham to Richmond Park");
    await user.click(screen.getByRole("button", { name: "Create route" }));
    expect(await screen.findByText("A lovely route with places to pause.")).toBeVisible();
    await user.selectOptions(screen.getByRole("combobox", { name: "City" }), "paris");
    expect(screen.queryByText("A lovely route with places to pause.")).not.toBeInTheDocument();
  });
});
