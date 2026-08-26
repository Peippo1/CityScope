import type { LiveNetwork } from "../../types/city";

export function ParisLivePanel({ network }: { network: LiveNetwork }) {
  return <section className="paris-live-panel" aria-labelledby="paris-live-heading">
    <div className="section-heading compact"><p className="eyebrow">Live network context</p><h2 id="paris-live-heading">Paris Vélib' availability</h2><p><span className={`freshness freshness--${network.freshness}`}>{network.freshness}</span> {new Date(network.fetched_at).toLocaleString()}</p></div>
    <p className="live-disclosure">Current station availability is operational context. It is not comparable to the historical trip cohort.</p>
    <ul className="live-station-list">{network.stations.slice(0, 8).map((station) => <li key={station.station_id}><span>{station.name ?? `Station ${station.station_id}`}</span><strong>{station.bikes_available} bikes</strong><small>{station.docks_available} docks</small></li>)}</ul>
    <a className="source-link" href={network.source_url} target="_blank" rel="noreferrer">{network.attribution_text}</a>
  </section>;
}
