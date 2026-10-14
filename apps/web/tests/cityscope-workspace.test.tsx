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
    expect(screen.getByRole("heading", { name: "Where will you explore today?" })).toBeVisible();
    expect(screen.getByText("Discover a new route, a great coffee stop, or somewhere unexpected.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Build story" })).toHaveAttribute(
      "href",
      "https://tfinch.dev/writing/building-cityscope",
    );
    expect(screen.queryByText(/Sign in with Google/)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Where will you explore?" })).toBeVisible();
    expect(screen.queryByText("Highest activity areas")).not.toBeInTheDocument();
    expect(screen.queryByText("Request flow")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Compare" })).not.toBeInTheDocument();
  });

  it("submits structured endpoints without requiring a free-text prompt", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(routeResult);
    render(<CityScopeWorkspace services={{ investigate }} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "City" }), "new_york");
    await user.click(screen.getByRole("button", { name: /Running/ }));
    await user.type(screen.getByLabelText("Starting point"), "Brooklyn");
    await user.type(screen.getByLabelText("Target distance (optional)"), "10");
    await user.type(screen.getByLabelText(/Destination/), "Prospect Park");
    await user.click(screen.getByRole("button", { name: "Plan my route" }));
    expect(investigate).toHaveBeenCalledWith(expect.objectContaining({ city: "new_york", question: "Plan this as a running route. Start at Brooklyn. Go to Prospect Park. Target 10 km.", context: expect.objectContaining({ start_location: "Brooklyn", destination: "Prospect Park", distance_km: 10 }) }));
    expect(await screen.findByText("A lovely route with places to pause.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Nearby optional facilities" })).toBeVisible();
    expect(investigate).toHaveBeenLastCalledWith(expect.objectContaining({ context: expect.objectContaining({ activity: "running", facility_categories: [] }) }));
  });

  it("requests current location without putting coordinates in the question", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(routeResult);
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition: vi.fn((success: (position: { coords: { latitude: number; longitude: number } }) => void) => success({ coords: { latitude: 51.53, longitude: -0.12 } })) } });
    render(<CityScopeWorkspace services={{ investigate }} />);
    await user.click(screen.getByRole("button", { name: "Use my current location" }));
    await user.type(screen.getByLabelText(/Destination/), "Camden");
    await user.click(screen.getByRole("button", { name: "Plan my route" }));
    expect(investigate).toHaveBeenCalledWith(expect.objectContaining({
      question: "Plan this as a cycling route. Start at Current location. Go to Camden.",
      context: expect.objectContaining({ origin_mode: "current_location", origin_latitude: 51.53, origin_longitude: -0.12, destination: "Camden" }),
    }));
  });

  it("generates a bounded A-to-B route immediately from Surprise me", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(routeResult);
    render(<CityScopeWorkspace services={{ investigate }} />);
    await user.type(screen.getByLabelText("Starting point"), "King's Cross");
    await user.click(screen.getByRole("button", { name: "Surprise me" }));
    expect(investigate).toHaveBeenCalledWith(expect.objectContaining({
      question: expect.stringContaining("Go to Camden Market."),
      context: expect.objectContaining({ start_location: "King's Cross", destination: "Camden Market", journey_type: "a_to_b" }),
    }));
  });

  it("resets the previous result when switching cities", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(routeResult);
    render(<CityScopeWorkspace services={{ investigate }} />);
    await user.type(screen.getByLabelText("Starting point"), "Fulham");
    await user.type(screen.getByLabelText(/Destination/), "Richmond Park");
    await user.click(screen.getByRole("button", { name: "Plan my route" }));
    expect(await screen.findByText("A lovely route with places to pause.")).toBeVisible();
    await user.selectOptions(screen.getByRole("combobox", { name: "City" }), "paris");
    expect(screen.queryByText("A lovely route with places to pause.")).not.toBeInTheDocument();
  });

  it("turns backend failures into a friendly retry state", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockRejectedValue(new Error("route.intent invalid (422)"));
    render(<CityScopeWorkspace services={{ investigate }} />);
    await user.type(screen.getByLabelText("Starting point"), "King's Cross");
    await user.type(screen.getByLabelText(/Destination/), "Camden");
    await user.click(screen.getByRole("button", { name: "Plan my route" }));
    expect(await screen.findByText("route.intent invalid (422)")).toBeVisible();
  });
});
