"use client";

import { FormEvent, useEffect, useState } from "react";
import { CityMap } from "../components/map/CityMap";
import { H3ActivityLayer } from "../components/map/H3ActivityLayer";
import { getLondonActivity, investigate } from "../lib/api";
import type { ActivityResponse } from "../types/city";
import type { InvestigationResult } from "../types/investigation";

export default function HomePage() {
  const [activity, setActivity] = useState<ActivityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [investigating, setInvestigating] = useState(false);

  useEffect(() => {
    getLondonActivity().then(setActivity).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Activity data could not be loaded");
    });
  }, []);

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setInvestigating(true);
    setError(null);
    try {
      setInvestigation(await investigate({ city: "london", question: question.trim(), context: { selected_h3_cells: [], previous_turns: [], evidence_summary: undefined } }));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Investigation could not be loaded");
    } finally {
      setInvestigating(false);
    }
  }

  const investigationCells = investigation?.map_layers.map((layer) => ({ h3_cell: layer.h3_cell, total_journeys: Number(layer.value) })) ?? [];

  return <main>
    <header className="header">
      <h1>CityScope</h1>
      <p>Explore London through historical cycling activity.</p>
    </header>
    {activity && <div className="notice">{activity.dataset_name ?? "CityScope mobility dataset"} · historical snapshot: {activity.observation_period}. This data does not represent current live cycling behaviour. {activity.attribution_text}</div>}
    {error && <p className="error" role="alert">{error}</p>}
    {!activity && !error && <p aria-live="polite">Loading London activity…</p>}
    <section className="investigation-card" aria-labelledby="investigate-heading">
      <h2 id="investigate-heading">Ask about London mobility</h2>
      <form onSubmit={submitQuestion}>
        <label htmlFor="investigation-question">Question</label>
        <div className="question-row"><input id="investigation-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Which areas are cycling hotspots?" maxLength={500} /><button type="submit" disabled={investigating}>{investigating ? "Investigating…" : "Investigate"}</button></div>
      </form>
      {investigation && <div className="investigation-result" aria-live="polite"><p>{investigation.answer}</p>{investigation.status === "unsupported" && <p className="notice">This question is outside the supported V1 investigation scope.</p>}{investigation.evidence.length > 0 && <><h3>Evidence</h3><ul>{investigation.evidence.slice(0, 8).map((item, index) => <li key={`${item.metric}-${index}`}><strong>{item.source === "google_maps" ? "Current Google Maps" : "Historical CityScope"}:</strong> {item.metric}: {item.value} {item.unit} · H3 {item.h3_cells.join(", ")}</li>)}</ul></>}{investigation.amenity_analysis.length > 0 && <><h3>Deterministic amenity comparison</h3><ul>{investigation.amenity_analysis.slice(0, 10).map((row) => <li key={`${row.category}-${row.h3_cell}`}>{row.category}: {row.place_count} returned places around H3 {row.h3_cell} · historical activity {row.mobility_value}</li>)}</ul></>}{investigation.places.length > 0 && <><h3>Current Google Maps places</h3><ul>{investigation.places.slice(0, 12).map((place) => <li key={place.place_id}>{place.maps_uri ? <a href={place.maps_uri} target="_blank" rel="noreferrer">{place.name ?? place.place_id}</a> : (place.name ?? place.place_id)} · {place.category} · H3 {place.h3_cell}{place.attribution_url && <> · <a href={place.attribution_url} target="_blank" rel="noreferrer">Google Maps source</a></>}</li>)}</ul></>}{investigation.limitations.length > 0 && <p className="notice">Limitations: {investigation.limitations.join(" ")}</p>}<details><summary>Trace</summary><ol>{investigation.trace.map((event, index) => <li key={`${event.label}-${index}`}>{event.label}{event.latency_ms ? ` · ${event.latency_ms} ms` : ""}</li>)}</ol></details></div>}
    </section>
    {activity && <section className="layout">
      <div className="map-card"><CityMap cells={investigationCells.length > 0 ? investigationCells : activity.cells} places={investigation?.places} /></div>
      <aside className="list-card"><h2>Highest activity cells</h2><H3ActivityLayer cells={activity.cells} /></aside>
    </section>}
  </main>;
}
