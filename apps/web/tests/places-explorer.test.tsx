import { fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const maps = vi.hoisted(() => {
  const searches: Array<HTMLElement & { places: unknown[] }> = [];
  const PlaceSearchElement = vi.fn(function PlaceSearchElement() {
    const element = document.createElement("gmp-place-search") as HTMLElement & { places: unknown[] };
    element.places = [];
    searches.push(element);
    return element;
  });
  const google = { maps: { importLibrary: vi.fn(), places: { PlaceSearchElement } } };
  return { google, searches };
});

vi.mock("@googlemaps/js-api-loader", () => ({
  Loader: class { load() { return Promise.resolve(maps.google); } },
}));

import { PlacesExplorer } from "../components/visualization/PlacesExplorer";

describe("PlacesExplorer", () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    maps.searches.length = 0;
    vi.clearAllMocks();
  });

  it("sends loaded and selected UI Kit places to the map", async () => {
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = "browser-test-key";
    const onPlacesChange = vi.fn();
    const onSelectPlace = vi.fn();
    render(<PlacesExplorer cityName="London" bounds={[51.28, -0.52, 51.72, 0.34]} onPlacesChange={onPlacesChange} onSelectPlace={onSelectPlace} />);

    await waitFor(() => expect(maps.searches).toHaveLength(1));
    const content = maps.searches[0].querySelector("gmp-place-content-config");
    expect(content).not.toBeNull();
    expect(content?.querySelector("gmp-place-address")).not.toBeNull();
    expect(content?.querySelector("gmp-place-rating")).not.toBeNull();
    expect(maps.searches[0].querySelector("gmp-place-all-content")).toBeNull();
    const place = {
      id: "place-1",
      displayName: "City Cafe",
      formattedAddress: "1 High Street",
      googleMapsURI: "https://maps.google.com/?cid=1",
      location: { lat: () => 51.51, lng: () => -0.12 },
      rating: 4.6,
    };
    const search = maps.searches[0];
    search.places = [place];
    fireEvent(search, new Event("gmp-load"));

    expect(onPlacesChange).toHaveBeenCalledWith([{
      place_id: "place-1",
      name: "City Cafe",
      latitude: 51.51,
      longitude: -0.12,
      maps_uri: "https://maps.google.com/?cid=1",
    }]);

    const selectEvent = new Event("gmp-select");
    Object.defineProperty(selectEvent, "place", { value: place });
    fireEvent(search, selectEvent);
    expect(onSelectPlace).toHaveBeenCalledWith(expect.objectContaining({ place_id: "place-1", name: "City Cafe" }));
  });
});
