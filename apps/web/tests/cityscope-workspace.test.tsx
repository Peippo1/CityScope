import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CityScopeWorkspace } from "../components/investigation/CityScopeWorkspace";
import type { ActivityResponse } from "../types/city";
import type { InvestigationResult } from "../types/investigation";

const activity: ActivityResponse = {
  city: "london",
  dataset_name: "TfL Cycling",
  observation_period: "2026-05-01/2026-05-31",
  attribution_text: "TfL",
  historical_snapshot: true,
  h3_resolution: 9,
  cells: [{ h3_cell: "89194ad3353ffff", total_journeys: 42, origin_journeys: 20, destination_journeys: 22 }],
};

const investigation: InvestigationResult = {
  investigation_id: "test",
  status: "answered",
  answer: "Area 1 had the highest historical cycling activity.",
  evidence: [], places: [], amenity_analysis: [], city_insights: [], map_layers: [], limitations: [], trace: [], follow_up_suggestions: [],
};

const comparison = {
  metric: "trips_per_active_station_day", calculation_basis: "trips divided by active stations and days", observation_period: "2026-05-01/2026-05-31",
  cities: [{ city: "london", city_name: "London", value: 1.2, rank: 1, snapshot_id: "2026-05", is_fixture: false }, { city: "new_york", city_name: "New York City", value: 0.9, rank: 2, snapshot_id: "2026-05", is_fixture: false }], limitations: ["Normalized only"],
};

const parisLive = {
  city: "paris" as const, provider: "Vélib' Métropole GBFS", fetched_at: "2026-08-26T12:00:00Z", freshness: "fresh" as const, attribution_text: "Live station status provided by Vélib' Métropole.", source_url: "https://example.test/velib", limitations: ["Live only"],
  stations: [{ station_id: "1", name: "Paris station", latitude: 48.85, longitude: 2.35, bikes_available: 4, docks_available: 7 }],
};

const newYorkLive = {
  ...parisLive,
  city: "new_york" as const,
  provider: "Citi Bike GBFS",
  attribution_text: "Live station status provided by Citi Bike.",
  stations: [{ station_id: "nyc-1", name: "Broadway & W 25 St", latitude: 40.744, longitude: -73.989, bikes_available: 9, docks_available: 5 }],
};

const registry = {
  cities: [
    { id: "london" as const, name: "London", historical: true, routes: true, live_network: false, timezone: "Europe/London", bounds: [51.28, -0.52, 51.72, 0.34] as [number, number, number, number] },
    { id: "new_york" as const, name: "New York City", historical: true, routes: true, live_network: true, timezone: "America/New_York", bounds: [40.49, -74.30, 40.92, -73.68] as [number, number, number, number] },
  ],
};

describe("CityScopeWorkspace", () => {
  it("lets a user retry activity loading without turning it into an investigation error", async () => {
    const user = userEvent.setup();
    const getActivity = vi.fn().mockRejectedValueOnce(new Error("Activity unavailable")).mockResolvedValueOnce(activity);
    render(<CityScopeWorkspace services={{ getActivity, investigate: vi.fn() }} />);

    expect(await screen.findByText("Activity unavailable")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry London activity" }));

    expect(await screen.findByRole("heading", { name: "Highest activity areas" })).toBeVisible();
    expect(screen.queryByText("Activity unavailable")).not.toBeInTheDocument();
  });

  it("submits a selected example question and renders the answer", async () => {
    const user = userEvent.setup();
    render(<CityScopeWorkspace services={{ getActivity: vi.fn().mockResolvedValue(activity), investigate: vi.fn().mockResolvedValue(investigation) }} />);

    await user.click(screen.getByRole("button", { name: "Find Saturday cycling hotspots" }));
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    expect(await screen.findByText(investigation.answer)).toBeVisible();
    expect(screen.getByText("Answered")).toBeVisible();
  });

  it("includes a selected activity area in the investigation context", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(investigation);
    render(<CityScopeWorkspace services={{ getActivity: vi.fn().mockResolvedValue(activity), investigate }} />);

    await user.click(await screen.findByRole("button", { name: /Area 1/ }));
    await user.type(screen.getByRole("textbox", { name: "Question" }), "What is nearby?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    expect(investigate).toHaveBeenCalledWith(expect.objectContaining({
      context: expect.objectContaining({ selected_h3_cells: ["89194ad3353ffff"] }),
    }));
  });

  it("keeps an investigation failure local and lets the user retry it", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockRejectedValueOnce(new Error("Investigation unavailable")).mockResolvedValueOnce(investigation);
    render(<CityScopeWorkspace services={{ getActivity: vi.fn().mockResolvedValue(activity), investigate }} />);

    await user.type(screen.getByRole("textbox", { name: "Question" }), "Where are the hotspots?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));
    expect(await screen.findByText("Investigation unavailable")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Highest activity areas" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Retry investigation" }));
    expect(await screen.findByText(investigation.answer)).toBeVisible();
    expect(screen.queryByText("Investigation unavailable")).not.toBeInTheDocument();
  });

  it("shows a normalized four-city comparison without leaving the workspace", async () => {
    const user = userEvent.setup();
    render(<CityScopeWorkspace services={{ getActivity: vi.fn().mockResolvedValue(activity), investigate: vi.fn(), getComparison: vi.fn().mockResolvedValue(comparison) }} />);

    await user.click(screen.getByRole("button", { name: "Compare" }));

    expect(await screen.findByRole("heading", { name: "Four-city comparison" })).toBeVisible();
    expect(screen.getAllByText("New York City")).toHaveLength(2);
    expect(screen.getByText(/never raw journey totals/i)).toBeVisible();
    expect(screen.getAllByText("Verified production artifact · 2026-05")).toHaveLength(2);
  });

  it("loads the city registry from the API and drills from comparison into city activity", async () => {
    const user = userEvent.setup();
    const getActivity = vi.fn().mockImplementation(async (city) => ({ ...activity, city, dataset_name: city === "new_york" ? "Citi Bike Trips" : "TfL Cycling" }));
    render(<CityScopeWorkspace services={{ getCities: vi.fn().mockResolvedValue(registry), getActivity, investigate: vi.fn(), getComparison: vi.fn().mockResolvedValue(comparison) }} />);

    expect(await screen.findByRole("option", { name: "New York City" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Compare" }));
    await user.click(await screen.findByRole("button", { name: "Open New York City activity" }));

    expect(screen.getByRole("combobox", { name: "City workspace" })).toHaveValue("new_york");
    expect(await screen.findByRole("heading", { name: "New York City activity" })).toBeVisible();
    expect(getActivity).toHaveBeenCalledWith("new_york");
  });

  it("shows Paris as separate live network context", async () => {
    const user = userEvent.setup();
    const getActivity = vi.fn().mockResolvedValue(activity);
    render(<CityScopeWorkspace services={{ getActivity, investigate: vi.fn(), getLive: vi.fn().mockResolvedValue(parisLive) }} />);

    await user.selectOptions(screen.getByRole("combobox", { name: "City workspace" }), "paris");

    expect(await screen.findByRole("heading", { name: "Paris Vélib' Métropole GBFS availability" })).toBeVisible();
    expect(screen.getByText(/not comparable to the historical trip cohort/i)).toBeVisible();
    expect(getActivity).not.toHaveBeenCalledWith("paris");
  });

  it("switches a historical cohort city into its own live station map", async () => {
    const user = userEvent.setup();
    const getLive = vi.fn().mockResolvedValue(newYorkLive);
    render(<CityScopeWorkspace services={{ getCities: vi.fn().mockResolvedValue(registry), getActivity: vi.fn().mockResolvedValue(activity), investigate: vi.fn(), getLive }} />);

    await user.selectOptions(await screen.findByRole("combobox", { name: "City workspace" }), "new_york");
    await user.click(screen.getByRole("button", { name: "Live network" }));

    expect(await screen.findByRole("heading", { name: "New York City Citi Bike GBFS availability" })).toBeVisible();
    expect(screen.getByText("Broadway & W 25 St")).toBeVisible();
    expect(getLive).toHaveBeenCalledWith("new_york");
  });
});
