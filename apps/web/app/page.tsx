"use client";
import { FormEvent, useEffect, useState } from "react";
import { CityMap } from "../components/map/CityMap";
import { H3ActivityLayer } from "../components/map/H3ActivityLayer";
import { getLondonActivity, investigate } from "../lib/api";
import type { ActivityResponse } from "../types/city";
import type { InvestigationResult } from "../types/investigation";

export default function HomePage() {
  const [activity, setActivity] = useState<ActivityResponse | null>(null), [error, setError] = useState<string | null>(null), [question, setQuestion] = useState(""), [investigation, setInvestigation] = useState<InvestigationResult | null>(null), [investigating, setInvestigating] = useState(false);
  useEffect(() => { getLondonActivity().then(setActivity).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Activity data could not be loaded")); }, []);
  async function submitQuestion(event: FormEvent) { event.preventDefault(); if (!question.trim()) return; setInvestigating(true); setError(null); try { setInvestigation(await investigate({ city: "london", question: question.trim(), context: { selected_h3_cells: [], previous_turns: [], evidence_summary: undefined } })); } catch (reason: unknown) { setError(reason instanceof Error ? reason.message : "Investigation could not be loaded"); } finally { setInvestigating(false); } }
  const investigationCells = investigation?.map_layers.map((layer) => ({ h3_cell: layer.h3_cell, total_journeys: Number(layer.value) })) ?? [];
  return <main><header className="header"><h1>CityScope</h1><p>Explore London through historical cycling activity.</p></header>
    {activity && <div className="notice">{activity.dataset_name ?? "CityScope mobility dataset"} · historical snapshot: {activity.observation_period}. This data does not represent current live cycling behaviour. {activity.attribution_text}</div>}
    {error && <p className="error" role="alert">{error}</p>}{!activity && !error && <p aria-live="polite">Loading London activity…</p>}
    <section className="investigation-card" aria-labelledby="investigate-heading"><h2 id="investigate-heading">Ask about London mobility</h2><form onSubmit={submitQuestion}><label htmlFor="investigation-question">Question</label><div className="question-row"><input id="investigation-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Which areas are cycling hotspots?" maxLength={500} /><button type="submit" disabled={investigating}>{investigating ? "Investigating…" : "Investigate"}</button></div></form>
      {investigation && <div className="investigation-result" aria-live="polite"><p>{investigation.answer}</p>{investigation.route && <><h3>Bicycle route</h3><p>{(investigation.route.distance_m / 1000).toFixed(1)} km · about {Math.round(investigation.route.duration_seconds / 60)} minutes · Google Routes API{investigation.route.attribution_url && <> · <a href={investigation.route.attribution_url} target="_blank" rel="noreferrer">source</a></>}</p><p className="notice">{investigation.route.warning}</p></>}{investigation.status === "unsupported" && <p className="notice">This question is outside the supported V1 investigation scope.</p>}{investigation.limitations.length > 0 && <p className="notice">Limitations: {investigation.limitations.join(" ")}</p>}<details><summary>Trace</summary><ol>{investigation.trace.map((event, index) => <li key={`${event.label}-${index}`}>{event.label}</li>)}</ol></details></div>}
    </section>{activity && <section className="layout"><div className="map-card"><CityMap cells={investigationCells.length > 0 ? investigationCells : activity.cells} places={investigation?.places} route={investigation?.route} /></div><aside className="list-card"><h2>Highest activity cells</h2><H3ActivityLayer cells={activity.cells} /></aside></section>}
  </main>;
}
