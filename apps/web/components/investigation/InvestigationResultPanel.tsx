import { useState } from "react";
import type { InvestigationResult } from "../../types/investigation";

function safeText(value: string) {
  return value.replace(/AIza[0-9A-Za-z_-]{20,}/g, "[redacted]").replace(/((?:api[_ -]?key|authorization|bearer|token|secret|password)\s*[:=]\s*)([^\s,;]+)/gi, "$1[redacted]");
}
function stopLabel(category: string) {
  const labels: Record<string, string> = { cafe: "Coffee stop", restaurant: "Food stop", public_bathroom: "Bathroom", bicycle_repair_shop: "Bike repair", shop: "Useful stop", point_of_interest: "Worth a look" };
  return labels[category] ?? category.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
async function shareRoute(result: InvestigationResult, onMessage: (message: string) => void) {
  if (!result.route || typeof navigator === "undefined") return;
  const text = `${result.route.origin.name} → ${result.route.destination.name} · ${(result.route.distance_m / 1000).toFixed(1)} km`;
  const nav = navigator as Navigator & { share?: (data: { title: string; text: string }) => Promise<void> };
  if (typeof nav.share === "function") { try { await nav.share({ title: "CityScope route", text }); onMessage("Route shared."); } catch { /* cancelled */ } }
  else if (navigator.clipboard) { await navigator.clipboard.writeText(text); onMessage("Route copied — send it to your phone."); }
}

export function InvestigationResultPanel({ result, onSuggestion, onSelectPlace }: { result: InvestigationResult; onSuggestion: (question: string) => void; onSelectPlace?: (place: InvestigationResult["places"][number]) => void }) {
  const [shareMessage, setShareMessage] = useState<string | null>(null);
  const places = Array.from(new Map(result.places.map((place) => [place.place_id, place])).values()).slice(0, 8);
  const statusLabels = { answered: "Ready to go", partial: "Route ready with a few gaps", unsupported: "Not supported", failed: "Could not answer" };
  return <article className={`result-panel result-panel--${result.status}`} aria-live="polite">
    <header className="result-header"><span className={`status-badge status-badge--${result.status}`}>{statusLabels[result.status]}</span><h2>Your {result.route?.travel_mode === "walking" ? "run" : "ride"}</h2><p className="answer">{safeText(result.answer)}</p></header>
    {result.route && <section aria-labelledby="route-heading" className="insight-card route-card"><div className="card-heading"><div><span className="source-badge source-badge--route">{result.route.travel_mode === "walking" ? "Running route" : "Cycling route"}</span><h3 id="route-heading">{result.route.origin.name} → {result.route.destination.name}</h3></div></div><dl className="route-metrics"><div><dt>Distance</dt><dd>{(result.route.distance_m / 1000).toFixed(1)} km</dd></div><div><dt>Estimated time</dt><dd>{Math.round(result.route.duration_seconds / 60)} min</dd></div></dl>{result.route.warning && <p className="warning"><strong>Route note:</strong> {safeText(result.route.warning)}</p>}<div className="route-actions"><button type="button" className="secondary-button" onClick={() => void shareRoute(result, setShareMessage)}>Share to my phone</button>{shareMessage && <span className="share-message" role="status">{shareMessage}</span>}</div>{result.route.attribution_url && <a className="source-link" href={result.route.attribution_url} target="_blank" rel="noreferrer">Google Routes</a>}</section>}
    {result.journey_plan?.segments && result.journey_plan.segments.length > 1 && <section className="journey-segment-summary"><h3>Loop return</h3><p>{result.journey_plan.segments[1].route.origin.name} → {result.journey_plan.segments[1].route.destination.name} · {(result.journey_plan.segments[1].route.distance_m / 1000).toFixed(1)} km</p></section>}
    {places.length > 0 && <section className="insight-card stops-card" aria-labelledby="stops-heading"><h3 id="stops-heading">Good places to pause</h3><ul className="place-list">{places.map((place) => <li key={place.place_id}><button type="button" className="place-card-button" onClick={() => onSelectPlace?.(place)}><strong>{place.name ?? stopLabel(place.category)}</strong><span>{stopLabel(place.category)}</span></button>{place.maps_uri && <a href={place.maps_uri} target="_blank" rel="noreferrer">Open map</a>}</li>)}</ul></section>}
    {result.limitations.length > 0 && <p className="route-limitations">{safeText(result.limitations[0])}</p>}
    {result.follow_up_suggestions.length > 0 && <div className="follow-ups"><div className="prompt-list">{result.follow_up_suggestions.map((suggestion) => <button type="button" className="prompt-chip" key={suggestion} onClick={() => onSuggestion(suggestion)}>{suggestion}</button>)}</div></div>}
  </article>;
}
