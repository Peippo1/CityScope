"use client";

import { useMemo, useState } from "react";
import type { LiveNetwork } from "../../types/city";
import { CityMap, type FocusedMapPlace } from "../map/CityMap";

type SortMode = "name" | "bikes" | "docks" | "nearest";

function distanceKm(latitude: number, longitude: number, origin: { latitude: number; longitude: number } | null) {
  if (!origin) return null;
  const radians = Math.PI / 180;
  const latitudeDelta = (latitude - origin.latitude) * radians;
  const longitudeDelta = (longitude - origin.longitude) * radians;
  const a = Math.sin(latitudeDelta / 2) ** 2 + Math.cos(origin.latitude * radians) * Math.cos(latitude * radians) * Math.sin(longitudeDelta / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function LiveNetworkPanel({ cityName, bounds, network }: { cityName: string; bounds: [number, number, number, number]; network: LiveNetwork }) {
  const [query, setQuery] = useState("");
  const [availability, setAvailability] = useState<"all" | "bikes" | "docks">("all");
  const [sort, setSort] = useState<SortMode>("bikes");
  const [location, setLocation] = useState<{ latitude: number; longitude: number } | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [selected, setSelected] = useState<FocusedMapPlace | null>(null);

  const stations = useMemo(() => network.stations
    .filter((station) => station.name?.toLowerCase().includes(query.trim().toLowerCase()) ?? !query.trim())
    .filter((station) => availability === "all" || (availability === "bikes" ? station.bikes_available > 0 : station.docks_available > 0))
    .sort((left, right) => {
      if (sort === "name") return (left.name ?? left.station_id).localeCompare(right.name ?? right.station_id);
      if (sort === "nearest") return (distanceKm(left.latitude, left.longitude, location) ?? Infinity) - (distanceKm(right.latitude, right.longitude, location) ?? Infinity);
      return sort === "bikes" ? right.bikes_available - left.bikes_available : right.docks_available - left.docks_available;
    }), [availability, location, network.stations, query, sort]);

  const mapStations = stations.map((station) => ({
    place_id: station.station_id,
    name: `${station.name ?? `Station ${station.station_id}`} · ${station.bikes_available} bikes · ${station.docks_available} docks`,
    latitude: station.latitude,
    longitude: station.longitude,
  }));

  function useLocation() {
    if (!navigator.geolocation) {
      setLocationError("Location is unavailable in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => { setLocation({ latitude: position.coords.latitude, longitude: position.coords.longitude }); setLocationError(null); setSort("nearest"); },
      () => setLocationError("Location permission was not granted. Stations remain sortable by availability."),
      { enableHighAccuracy: false, timeout: 8_000, maximumAge: 300_000 },
    );
  }

  return <section className="live-network-panel" aria-labelledby="live-network-heading">
    <div className="section-heading compact"><p className="eyebrow">Live network context</p><h2 id="live-network-heading">{cityName} {network.provider} availability</h2><p><span className={`freshness freshness--${network.freshness}`}>{network.freshness}</span> {new Date(network.fetched_at).toLocaleString()}</p></div>
    <p className="live-disclosure">Current station availability is operational context. It is not comparable to the historical trip cohort.</p>
    <div className="live-controls" aria-label="Live station filters">
      <label>Find a station<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search station name" /></label>
      <label>Availability<select value={availability} onChange={(event) => setAvailability(event.target.value as typeof availability)}><option value="all">All stations</option><option value="bikes">Bikes available</option><option value="docks">Docks available</option></select></label>
      <label>Sort by<select value={sort} onChange={(event) => setSort(event.target.value as SortMode)}><option value="bikes">Most bikes</option><option value="docks">Most docks</option><option value="name">Station name</option><option value="nearest" disabled={!location}>Nearest to me</option></select></label>
      <button type="button" className="secondary-button" onClick={useLocation}>Use my location</button>
    </div>
    {locationError && <p className="inline-error" role="status">{locationError}</p>}
    <div className="live-network-layout">
      <div className="live-network-map"><CityMap cells={[]} places={mapStations} focusedPlace={selected} onSelectPlace={setSelected} cityName={cityName} bounds={bounds} ariaLabel={`${cityName} live bike-share station map`} /></div>
      <div><p className="live-station-summary" aria-live="polite">{stations.length} matching stations</p><ul className="live-station-list">{stations.slice(0, 50).map((station) => {
        const stationPlace = { place_id: station.station_id, name: station.name ?? `Station ${station.station_id}`, latitude: station.latitude, longitude: station.longitude };
        const distance = distanceKm(station.latitude, station.longitude, location);
        return <li key={station.station_id}><button type="button" className={selected?.place_id === station.station_id ? "live-station is-selected" : "live-station"} onClick={() => setSelected(stationPlace)} aria-pressed={selected?.place_id === station.station_id}><span>{stationPlace.name}</span><strong>{station.bikes_available} bikes</strong><small>{station.docks_available} docks{distance !== null ? ` · ${distance.toFixed(1)} km away` : ""}</small></button></li>;
      })}</ul>{selected && <p className="live-selection" role="status">Map focused on {selected.name}.</p>}<a className="source-link" href={network.source_url} target="_blank" rel="noreferrer">{network.attribution_text}</a></div>
    </div>
  </section>;
}

export const ParisLivePanel = LiveNetworkPanel;
