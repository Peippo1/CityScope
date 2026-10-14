import { useState } from "react";
import type { InvestigationResult } from "../../types/investigation";
import { selectItineraryPlaces } from "../../lib/itinerary";
import { useLocale } from "../../lib/i18n";

function safeText(value: string) {
  return value.replace(/AIza[0-9A-Za-z_-]{20,}/g, "[redacted]").replace(/((?:api[_ -]?key|authorization|bearer|token|secret|password)\s*[:=]\s*)([^\s,;]+)/gi, "$1[redacted]");
}
function stopLabel(category: string, copy: ReturnType<typeof useLocale>["copy"]) {
  const labels: Record<string, string> = { cafe: copy.coffeeStop, restaurant: copy.foodStop, public_bathroom: copy.bathroom, bicycle_repair_shop: copy.usefulStop, shop: copy.usefulStop, point_of_interest: copy.usefulStop };
  return labels[category] ?? category.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function placeName(place: InvestigationResult["places"][number], copy: ReturnType<typeof useLocale>["copy"]) {
  return place.name ?? place.attribution_title?.replace(/\s+-\s+Google Maps$/i, "") ?? stopLabel(place.category, copy);
}
function formatDistance(distanceM: number | null | undefined) {
  return typeof distanceM === "number" && Number.isFinite(distanceM) ? `${(distanceM / 1000).toFixed(1)} km` : "Unavailable";
}
function formatDuration(durationSeconds: number | null | undefined) {
  return typeof durationSeconds === "number" && Number.isFinite(durationSeconds) ? `${Math.round(durationSeconds / 60)} min` : "Unavailable";
}
function directionsUrl(result: InvestigationResult) {
  if (!result.route) return undefined;
  const params = new URLSearchParams({
    api: "1",
    origin: result.route.origin.name,
    destination: result.route.destination.name,
    travelmode: result.route.travel_mode === "walking" ? "walking" : "bicycling",
  });
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
async function shareRoute(result: InvestigationResult, onMessage: (message: string) => void) {
  if (!result.route || typeof navigator === "undefined") return;
  const text = `${result.route.origin.name} → ${result.route.destination.name} · ${formatDistance(result.route.distance_m)}`;
  const url = directionsUrl(result);
  const nav = navigator as Navigator & { share?: (data: { title: string; text: string; url?: string }) => Promise<void> };
  if (typeof nav.share === "function") { try { await nav.share({ title: "CityScope route", text, url }); onMessage("Route shared."); } catch { /* cancelled */ } }
  else if (navigator.clipboard) { await navigator.clipboard.writeText(url ? `${text}\n${url}` : text); onMessage("Route copied — send it to your phone."); }
}

export function InvestigationResultPanel({ result, onSuggestion, onSelectPlace }: { result: InvestigationResult; onSuggestion: (question: string) => void; onSelectPlace?: (place: InvestigationResult["places"][number]) => void }) {
  const { copy } = useLocale();
  const [shareMessage, setShareMessage] = useState<string | null>(null);
  const plannedStops = result.planned_stops ?? result.journey_plan?.selected_stops ?? [];
  const places = selectItineraryPlaces(result.facilities ?? result.places);
  const mapDirections = directionsUrl(result);
  const statusLabels = { answered: copy.readyToGo, partial: copy.routeReady, unsupported: copy.couldNotAnswer, failed: copy.couldNotAnswer };
  return <article className={`result-panel result-panel--${result.status}`} aria-live="polite">
    <header className="result-header"><span className={`status-badge status-badge--${result.status}`}>{statusLabels[result.status]}</span><h2>{result.route ? `Your ${result.route.travel_mode === "walking" ? "run" : "ride"}` : "Your route"}</h2><p className="answer">{result.route ? safeText(result.answer) : "CityScope couldn't complete this plan just now. Try a more specific starting point or a shorter journey."}</p></header>
    {result.route && <section aria-labelledby="route-heading" className="insight-card route-card"><div className="card-heading"><div><span className="source-badge source-badge--route">{result.route.travel_mode === "walking" ? copy.running : copy.cycling}</span><h3 id="route-heading">{result.route.origin.name} → {result.route.destination.name}</h3></div></div><dl className="route-metrics">{typeof result.requested_distance_km === "number" && <div><dt>{copy.requestedDistance}</dt><dd>{result.requested_distance_km.toFixed(1)} km</dd></div>}<div><dt>{copy.calculatedDistance}</dt><dd>{formatDistance(result.route.distance_m)}</dd></div><div><dt>{copy.estimatedTime}</dt><dd>{formatDuration(result.route.duration_seconds)}</dd></div></dl>{result.route.warning && <p className="warning"><strong>{copy.routeNote}</strong> {safeText(result.route.warning)}</p>}<div className="route-actions">{mapDirections && <a className="primary-link-button" href={mapDirections} target="_blank" rel="noreferrer">{copy.openMaps}</a>}<button type="button" className="secondary-button" onClick={() => void shareRoute(result, setShareMessage)}>{copy.share}</button>{shareMessage && <span className="share-message" role="status">{shareMessage}</span>}</div>{result.route.attribution_url && <a className="source-link" href={result.route.attribution_url} target="_blank" rel="noreferrer">Google Routes</a>}</section>}
    {result.journey_plan?.segments && result.journey_plan.segments.length > 1 && <section className="journey-segment-summary"><h3>Loop return</h3><p>{result.journey_plan.segments[1].route.origin.name} → {result.journey_plan.segments[1].route.destination.name} · {formatDistance(result.journey_plan.segments[1].route.distance_m)}</p></section>}
    {plannedStops.length > 0 && <section className="insight-card stops-card" aria-labelledby="planned-stops-heading"><h3 id="planned-stops-heading">{copy.plannedStops}</h3><ol className="place-list">{plannedStops.map((place) => <li key={place.place_id}><button type="button" className="place-card-button" onClick={() => onSelectPlace?.(place)}><strong>{placeName(place, copy)}</strong><span>{stopLabel(place.category, copy)}</span></button>{place.maps_uri && <a href={place.maps_uri} target="_blank" rel="noreferrer">Open map</a>}</li>)}</ol><p className="places-disclosure">{copy.plannedDisclosure}</p></section>}
    {places.length > 0 && <section className="insight-card stops-card" aria-labelledby="facilities-heading"><h3 id="facilities-heading">{copy.nearbyFacilities}</h3><ol className="place-list">{places.map((place) => <li key={place.place_id}><button type="button" className="place-card-button" onClick={() => onSelectPlace?.(place)}><strong>{placeName(place, copy)}</strong><span>{stopLabel(place.category, copy)}</span></button>{place.maps_uri && <a href={place.maps_uri} target="_blank" rel="noreferrer">Open map</a>}</li>)}</ol><p className="places-disclosure">{copy.nearbyDisclosure}</p></section>}
    {result.limitations.length > 0 && <p className="route-limitations">{safeText(result.limitations[0])}</p>}
    {result.follow_up_suggestions.length > 0 && <div className="follow-ups"><div className="prompt-list">{result.follow_up_suggestions.map((suggestion) => <button type="button" className="prompt-chip" key={suggestion} onClick={() => onSuggestion(suggestion)}>{suggestion}</button>)}</div></div>}
  </article>;
}
