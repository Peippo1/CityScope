import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const maps = vi.hoisted(() => {
  let polygonClick: (() => void) | undefined;
  let rejectLoad = false;
  const Polygon = vi.fn(function Polygon(this: { addListener: (event: string, callback: () => void) => void; setMap: () => void }) {
    this.addListener = (event, callback) => { if (event === "click") polygonClick = callback; };
    this.setMap = vi.fn();
  });
  const Marker = vi.fn(function Marker(this: { addListener: () => void; setMap: () => void }) { this.addListener = vi.fn(); this.setMap = vi.fn(); });
  const Polyline = vi.fn(function Polyline(this: { setMap: () => void }) { this.setMap = vi.fn(); });
  const InfoWindow = vi.fn(function InfoWindow(this: { setContent: () => void; open: () => void; close: () => void }) { this.setContent = vi.fn(); this.open = vi.fn(); this.close = vi.fn(); });
  const panTo = vi.fn();
  const setZoom = vi.fn();
  const Map = vi.fn(function Map(this: { panTo: typeof panTo; setZoom: typeof setZoom }) { this.panTo = panTo; this.setZoom = setZoom; });
  const google = { maps: { Map, Polygon, Marker, Polyline, InfoWindow, Animation: { DROP: 1 }, SymbolPath: { CIRCLE: 0 }, geometry: { encoding: { decodePath: vi.fn(() => []) } } } };
  return { google, Polygon, Marker, panTo, setZoom, getPolygonClick: () => polygonClick, shouldReject: () => rejectLoad, setRejectLoad: (value: boolean) => { rejectLoad = value; } };
});

vi.mock("@googlemaps/js-api-loader", () => ({ Loader: class { load() { return maps.shouldReject() ? Promise.reject(new Error("Maps unavailable")) : Promise.resolve(maps.google); } } }));

import { CityMap } from "../components/map/CityMap";

describe("CityMap", () => {
  afterEach(() => { delete process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY; maps.setRejectLoad(false); vi.clearAllMocks(); });

  it("lets a user select the same H3 area shown in the ranked list", async () => {
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = "browser-test-key";
    const onSelect = vi.fn();
    render(<CityMap cells={[{ h3_cell: "89194ad3353ffff", total_journeys: 42 }]} selectedH3Cell={null} onSelectH3Cell={onSelect} />);

    await waitFor(() => expect(maps.Polygon).toHaveBeenCalled());
    maps.getPolygonClick()?.();

    expect(onSelect).toHaveBeenCalledWith("89194ad3353ffff");
  });

  it("keeps the textual experience available when Google Maps fails to load", async () => {
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = "browser-test-key";
    maps.setRejectLoad(true);
    render(<CityMap cells={[{ h3_cell: "89194ad3353ffff", total_journeys: 42 }]} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("The activity ranking and investigation evidence remain available in text.");
  });

  it("focuses the map when a user selects a current Google place", async () => {
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = "browser-test-key";
    render(<CityMap cells={[]} focusedPlace={{ place_id: "place-1", name: "Rest stop", latitude: 51.51, longitude: -0.12 }} />);

    await waitFor(() => expect(maps.panTo).toHaveBeenCalledWith({ lat: 51.51, lng: -0.12 }));
    expect(maps.setZoom).toHaveBeenCalledWith(15);
    expect(maps.Marker).toHaveBeenCalledWith(expect.objectContaining({ title: "Rest stop" }));
  });

  it("renders live station markers with an explicit map label", async () => {
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = "browser-test-key";
    render(<CityMap cells={[]} places={[{ place_id: "station-1", name: "Station 1 · 5 bikes · 8 docks", latitude: 40.75, longitude: -73.98 }]} cityName="New York City" bounds={[40.49, -74.30, 40.92, -73.68]} ariaLabel="New York City live bike-share station map" />);

    expect(await screen.findByLabelText("New York City live bike-share station map")).toBeVisible();
    await waitFor(() => expect(maps.Marker).toHaveBeenCalledWith(expect.objectContaining({ title: "Station 1 · 5 bikes · 8 docks" })));
  });
});
