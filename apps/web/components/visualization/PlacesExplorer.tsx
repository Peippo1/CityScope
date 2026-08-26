"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Loader } from "@googlemaps/js-api-loader";

type PlacesExplorerProps = { cityName: string; bounds: [number, number, number, number] };

export function PlacesExplorer({ cityName, bounds }: PlacesExplorerProps) {
  const host = useRef<HTMLDivElement>(null);
  const searchRequest = useRef<google.maps.places.PlaceTextSearchRequestElement | null>(null);
  const [query, setQuery] = useState("cafes");
  const [selectedPlace, setSelectedPlace] = useState<google.maps.places.Place | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    if (!host.current || !key) return;
    let cancelled = false;
    const loader = new Loader({ apiKey: key, version: "weekly", libraries: ["places"] });

    loader.load().then(async (google) => {
      if (!host.current || cancelled) return;
      await google.maps.importLibrary("places");
      const search = new google.maps.places.PlaceSearchElement({ selectable: true });
      const request = document.createElement("gmp-place-text-search-request") as google.maps.places.PlaceTextSearchRequestElement;
      request.maxResultCount = 8;
      request.textQuery = `${query}, ${cityName}`;
      request.locationRestriction = {
        north: bounds[2], south: bounds[0], east: bounds[3], west: bounds[1],
      };
      search.append(request);
      search.append(document.createElement("gmp-place-all-content"));
      search.addEventListener("gmp-select", ((event: google.maps.places.PlaceSelectEvent) => {
        setSelectedPlace(event.place);
      }) as EventListener);
      searchRequest.current = request;
      host.current.replaceChildren(search);
    }).catch(() => { if (!cancelled) setLoadError(true); });

    return () => { cancelled = true; host.current?.replaceChildren(); searchRequest.current = null; };
  }, [cityName, bounds]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed && searchRequest.current) searchRequest.current.textQuery = `${trimmed}, ${cityName}`;
  }

  if (!process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) return null;

  return (
    <section className="places-explorer" aria-labelledby="places-explorer-heading">
      <header className="panel-heading">
        <div><p className="eyebrow">Current places</p><h2 id="places-explorer-heading">Explore {cityName}</h2></div>
        <span className="flow-state">Google Places</span>
      </header>
      <p className="places-disclosure">Current Google Places results are separate from historical bike-share evidence.</p>
      <form className="places-search" onSubmit={submit}>
        <label htmlFor="places-query">Search this city</label>
        <div><input id="places-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cafes, restaurants, shops..." /><button type="submit">Search</button></div>
      </form>
      {loadError ? <p className="inline-error" role="alert">Google Places could not be loaded. Check Places UI Kit, Places API (New), Maps JavaScript API, billing, and browser-key restrictions.</p> : <div ref={host} className="places-kit" aria-live="polite" />}
      {selectedPlace && <aside className="place-selection" aria-label="Selected place">
        <strong>{selectedPlace.displayName ?? "Selected place"}</strong>
        {selectedPlace.formattedAddress && <span>{selectedPlace.formattedAddress}</span>}
        {selectedPlace.rating != null && <span>Rating {selectedPlace.rating.toFixed(1)}</span>}
        {selectedPlace.googleMapsURI && <a href={selectedPlace.googleMapsURI} target="_blank" rel="noreferrer">Open in Google Maps</a>}
      </aside>}
    </section>
  );
}
