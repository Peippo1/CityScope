"use client";

import { useEffect, useState } from "react";
import { CityMap } from "../components/map/CityMap";
import { H3ActivityLayer } from "../components/map/H3ActivityLayer";
import { getLondonActivity } from "../lib/api";
import type { ActivityResponse } from "../types/city";

export default function HomePage() {
  const [activity, setActivity] = useState<ActivityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLondonActivity().then(setActivity).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Activity data could not be loaded");
    });
  }, []);

  return <main>
    <header className="header">
      <h1>CityScope</h1>
      <p>Explore London through historical cycling activity.</p>
    </header>
    {activity && <div className="notice">{activity.dataset_name ?? "CityScope mobility dataset"} · historical snapshot: {activity.observation_period}. This data does not represent current live cycling behaviour. {activity.attribution_text}</div>}
    {error && <p className="error" role="alert">{error}</p>}
    {!activity && !error && <p aria-live="polite">Loading London activity…</p>}
    {activity && <section className="layout">
      <div className="map-card"><CityMap cells={activity.cells} /></div>
      <aside className="list-card"><h2>Highest activity cells</h2><H3ActivityLayer cells={activity.cells} /></aside>
    </section>}
  </main>;
}
