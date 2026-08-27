import type { LiveNetwork } from "../../types/city";
import { CityMap } from "../map/CityMap";

export function LiveNetworkPanel({ cityName, bounds, network }: { cityName: string; bounds: [number, number, number, number]; network: LiveNetwork }) {
  const stations = network.stations.map((station) => ({
    place_id: station.station_id,
    name: `${station.name ?? `Station ${station.station_id}`} · ${station.bikes_available} bikes · ${station.docks_available} docks`,
    latitude: station.latitude,
    longitude: station.longitude,
  }));
  return <section className="live-network-panel" aria-labelledby="live-network-heading">
    <div className="section-heading compact"><p className="eyebrow">Live network context</p><h2 id="live-network-heading">{cityName} {network.provider} availability</h2><p><span className={`freshness freshness--${network.freshness}`}>{network.freshness}</span> {new Date(network.fetched_at).toLocaleString()}</p></div>
    <p className="live-disclosure">Current station availability is operational context. It is not comparable to the historical trip cohort.</p>
    <div className="live-network-layout">
      <div className="live-network-map"><CityMap cells={[]} places={stations} cityName={cityName} bounds={bounds} ariaLabel={`${cityName} live bike-share station map`} /></div>
      <div><ul className="live-station-list">{network.stations.slice(0, 12).map((station) => <li key={station.station_id}><span>{station.name ?? `Station ${station.station_id}`}</span><strong>{station.bikes_available} bikes</strong><small>{station.docks_available} docks</small></li>)}</ul><a className="source-link" href={network.source_url} target="_blank" rel="noreferrer">{network.attribution_text}</a></div>
    </div>
  </section>;
}

export const ParisLivePanel = LiveNetworkPanel;
