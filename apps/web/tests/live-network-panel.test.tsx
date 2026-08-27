import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("../components/map/CityMap", () => ({ CityMap: ({ focusedPlace }: { focusedPlace?: { name: string } | null }) => <div aria-label="Live map">{focusedPlace ? `Focused ${focusedPlace.name}` : "Map"}</div> }));

import { LiveNetworkPanel } from "../components/visualization/ParisLivePanel";

const network = {
  city: "paris" as const,
  provider: "Velib",
  fetched_at: "2026-08-27T12:00:00Z",
  freshness: "fresh" as const,
  attribution_text: "Velib source",
  source_url: "https://example.test/velib",
  stations: [
    { station_id: "a", name: "Alpha", latitude: 48.85, longitude: 2.34, bikes_available: 1, docks_available: 8 },
    { station_id: "b", name: "Bravo", latitude: 48.86, longitude: 2.35, bikes_available: 9, docks_available: 0 },
  ],
  limitations: [],
};

describe("LiveNetworkPanel", () => {
  it("filters stations and synchronizes a selected station with the map", async () => {
    const user = userEvent.setup();
    render(<LiveNetworkPanel cityName="Paris" bounds={[48.75, 2.20, 48.95, 2.52]} network={network} />);

    await user.type(screen.getByRole("searchbox", { name: "Find a station" }), "bravo");
    expect(screen.getByRole("button", { name: /bravo/i })).toBeVisible();
    expect(screen.queryByRole("button", { name: /alpha/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /bravo/i }));
    expect(screen.getByText("Map focused on Bravo.")).toBeVisible();
    expect(screen.getByLabelText("Live map")).toHaveTextContent("Focused Bravo");
  });

  it("filters out stations without bikes", async () => {
    const user = userEvent.setup();
    render(<LiveNetworkPanel cityName="Paris" bounds={[48.75, 2.20, 48.95, 2.52]} network={network} />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Availability" }), "docks");

    expect(screen.getByRole("button", { name: /alpha/i })).toBeVisible();
    expect(screen.queryByRole("button", { name: /bravo/i })).not.toBeInTheDocument();
  });
});
