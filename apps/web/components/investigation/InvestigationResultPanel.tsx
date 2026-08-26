import type { InvestigationResult } from "../../types/investigation";

function safeText(value: string) {
  return value
    .replace(/AIza[0-9A-Za-z_-]{20,}/g, "[redacted]")
    .replace(/((?:api[_ -]?key|authorization|bearer|token|secret|password)\s*[:=]\s*)([^\s,;]+)/gi, "$1[redacted]");
}

function placeLabel(category: string) {
  return category.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function SourceBadge({ kind }: { kind: "historical" | "current" | "route" }) {
  const labels = { historical: "Historical mobility evidence", current: "Current Google Maps context", route: "Google bicycle route" };
  return <span className={`source-badge source-badge--${kind}`}>{labels[kind]}</span>;
}

export function InvestigationResultPanel({ result, onSuggestion }: { result: InvestigationResult; onSuggestion: (question: string) => void }) {
  const historicalEvidence = result.evidence.filter((item) => item.source === "city_data");
  const currentEvidence = result.evidence.filter((item) => item.source === "google_maps");
  const places = Array.from(new Map(result.places.map((place) => [place.place_id, place])).values());
  const statusLabels = { answered: "Answered", partial: "Partial answer", unsupported: "Not supported", failed: "Could not answer" };

  return (
    <article className={`result-panel result-panel--${result.status}`} aria-live="polite">
      <header className="result-header">
        <span className={`status-badge status-badge--${result.status}`}>{statusLabels[result.status]}</span>
        <h2>CityScope answer</h2>
        <p className="answer">{safeText(result.answer)}</p>
      </header>

      {result.route && <section aria-labelledby="route-heading" className="insight-card route-card">
        <div className="card-heading"><div><SourceBadge kind="route" /><h3 id="route-heading">Bicycle route</h3></div></div>
        <p className="route-endpoints"><strong>{result.route.origin.name}</strong><span aria-hidden="true">→</span><strong>{result.route.destination.name}</strong></p>
        <dl className="route-metrics"><div><dt>Distance</dt><dd>{(result.route.distance_m / 1000).toFixed(1)} km</dd></div><div><dt>Estimated time</dt><dd>{Math.round(result.route.duration_seconds / 60)} min</dd></div></dl>
        {result.route.waypoints.length > 0 && <div className="waypoint-list"><h4>Why this route</h4><ul>{result.route.waypoints.map((point) => <li key={point.h3_cell}>{safeText(point.reason)}</li>)}</ul></div>}
        <p className="warning"><strong>Bicycle routing notice:</strong> {safeText(result.route.warning)}</p>
        {result.route.attribution_url && <a className="source-link" href={result.route.attribution_url} target="_blank" rel="noreferrer">{result.route.attribution_title ?? "Google Routes API"}</a>}
      </section>}

      {historicalEvidence.length > 0 && <section aria-labelledby="historical-heading" className="insight-card">
        <SourceBadge kind="historical" />
        <h3 id="historical-heading">Historical mobility evidence</h3>
        {result.dataset && <p className="observation-period">{result.dataset.dataset_name} · {result.dataset.observation_start} to {result.dataset.observation_end}</p>}
        <ul className="metric-list">{historicalEvidence.map((item, index) => <li key={`${item.metric}-${index}`}><strong>{item.value.toLocaleString()}</strong><span>{item.unit} · {item.metric.replaceAll("_", " ")}</span></li>)}</ul>
      </section>}

      {(currentEvidence.length > 0 || places.length > 0) && <section aria-labelledby="current-heading" className="insight-card">
        <SourceBadge kind="current" />
        <h3 id="current-heading">Current Google Maps context</h3>
        {currentEvidence.length > 0 && <ul className="metric-list">{currentEvidence.map((item, index) => <li key={`${item.metric}-${index}`}><strong>{item.value.toLocaleString()}</strong><span>{item.unit} · {item.category ?? item.metric.replaceAll("_", " ")}</span></li>)}</ul>}
        {places.length > 0 && <ul className="place-list">{places.map((place) => <li key={place.place_id}><div><strong>{place.name ?? placeLabel(place.category)}</strong><span>{placeLabel(place.category)} · Google Maps provider result</span></div><span className="place-actions">{place.maps_uri && <a href={place.maps_uri} target="_blank" rel="noreferrer">View on Google Maps</a>}{place.attribution_url && place.attribution_url !== place.maps_uri && <a href={place.attribution_url} target="_blank" rel="noreferrer">Google source</a>}</span></li>)}</ul>}
      </section>}

      {result.amenity_analysis.length > 0 && <section aria-labelledby="amenity-heading" className="insight-card">
        <h3 id="amenity-heading">Deterministic amenity comparison</h3>
        <ol className="ranked-list">{result.amenity_analysis.map((row) => <li key={`${row.category}-${row.h3_cell}`}><span className="rank">#{row.scarcity_rank}</span><span><strong>{row.place_count} {row.category}{row.place_count === 1 ? "" : "s"}</strong><small>{row.mobility_value} historical journeys</small></span></li>)}</ol>
      </section>}

      {result.limitations.length > 0 && <section className="limitations" aria-labelledby="limitations-heading"><h3 id="limitations-heading">Keep in mind</h3><ul>{result.limitations.map((item, index) => <li key={index}>{safeText(item)}</li>)}</ul></section>}

      {result.follow_up_suggestions.length > 0 && <section className="follow-ups" aria-labelledby="follow-up-heading"><h3 id="follow-up-heading">Explore next</h3><div className="prompt-list">{result.follow_up_suggestions.map((suggestion) => <button type="button" className="prompt-chip" key={suggestion} onClick={() => onSuggestion(suggestion)}>{suggestion}</button>)}</div></section>}

      <details className="evidence-details">
        <summary>Evidence &amp; methodology</summary>
        {result.evidence.length > 0 && <section><h3>Evidence records</h3><ul>{result.evidence.map((item, index) => <li key={`${item.source}-${item.metric}-${index}`}>{item.source}: {item.metric} = {item.value} {item.unit} · H3 {item.h3_cells.join(", ")}</li>)}</ul></section>}
        {result.route?.waypoints.length ? <section><h3>Route waypoint details</h3><ul>{result.route.waypoints.map((point) => <li key={point.h3_cell}>H3 {point.h3_cell} · selection score {point.score.toFixed(2)} · {safeText(point.reason)}</li>)}</ul></section> : null}
        {result.trace.length > 0 && <section><h3>Investigation trace</h3><ol>{result.trace.map((event, index) => <li key={`${event.label}-${index}`}>{safeText(event.label)}{event.policy_code ? ` · ${event.policy_code}` : ""}{event.latency_ms !== undefined ? ` · ${event.latency_ms} ms` : ""}</li>)}</ol></section>}
      </details>
    </article>
  );
}
