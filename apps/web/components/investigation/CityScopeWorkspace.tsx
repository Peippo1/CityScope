"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getLondonActivity, investigate } from "../../lib/api";
import type { ActivityResponse } from "../../types/city";
import type { InvestigationRequest, InvestigationResult } from "../../types/investigation";
import { CityMap } from "../map/CityMap";
import { H3ActivityLayer } from "../map/H3ActivityLayer";
import { ActivityOverview } from "../visualization/ActivityOverview";
import { DataFlowPanel } from "../visualization/DataFlowPanel";
import { AccountActions } from "./AccountActions";
import { InvestigationResultPanel } from "./InvestigationResultPanel";
import { QuestionComposer } from "./QuestionComposer";

type WorkspaceServices = {
  getActivity: () => Promise<ActivityResponse>;
  investigate: (request: InvestigationRequest) => Promise<InvestigationResult>;
};

const defaultServices: WorkspaceServices = { getActivity: getLondonActivity, investigate };

function messageFrom(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}

export function CityScopeWorkspace({ services = defaultServices }: { services?: WorkspaceServices }) {
  const [activity, setActivity] = useState<ActivityResponse | null>(null);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityLoading, setActivityLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [investigating, setInvestigating] = useState(false);
  const [selectedH3Cell, setSelectedH3Cell] = useState<string | null>(null);
  const [submittedRequest, setSubmittedRequest] = useState<InvestigationRequest | null>(null);

  const loadActivity = useCallback(async () => {
    setActivityLoading(true);
    setActivityError(null);
    try {
      setActivity(await services.getActivity());
    } catch (reason: unknown) {
      setActivityError(messageFrom(reason, "Activity data could not be loaded"));
    } finally {
      setActivityLoading(false);
    }
  }, [services]);

  useEffect(() => { void loadActivity(); }, [loadActivity]);

  const submitQuestion = useCallback(async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || investigating) return;
    setInvestigating(true);
    setInvestigationError(null);
    try {
      const request = {
        city: "london",
        question: trimmedQuestion,
        context: { selected_h3_cells: selectedH3Cell ? [selectedH3Cell] : [], previous_turns: [], evidence_summary: undefined },
      } satisfies InvestigationRequest;
      const result = await services.investigate(request);
      setSubmittedRequest(request);
      setInvestigation(result);
      setSelectedH3Cell(result.map_layers[0]?.h3_cell ?? null);
    } catch (reason: unknown) {
      setInvestigationError(messageFrom(reason, "Investigation could not be completed"));
    } finally {
      setInvestigating(false);
    }
  }, [investigating, question, selectedH3Cell, services]);

  const investigationCells = useMemo(() => investigation?.map_layers.map((layer) => ({
    h3_cell: layer.h3_cell,
    total_journeys: Number(layer.value),
  })) ?? [], [investigation]);
  const mapCells = investigationCells.length > 0 ? investigationCells : activity?.cells ?? [];

  return (
    <main id="main-content" className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main-content" aria-label="CityScope home">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /><i /></span><span>CityScope</span>
        </a>
        <nav className="view-nav" aria-label="Workspace sections">
          <a href="#explore" aria-current="page">Explore</a><a href="#flow">Data flow</a><a href="#evidence">Evidence</a>
        </nav>
        <AccountActions request={submittedRequest} result={investigation} />
      </header>

      <section className="dashboard-intro" aria-labelledby="page-title">
        <div><p className="eyebrow">London mobility intelligence</p><h1 id="page-title">See movement. Find patterns. Plan better routes.</h1></div>
        <p>Explore historical cycling activity, current place context, and grounded bicycle routes in one visual workspace.</p>
      </section>

      {activity && <aside className="snapshot-banner" aria-label="Historical dataset notice">
        <span className="source-badge source-badge--historical">Historical snapshot</span>
        <p><strong>{activity.dataset_name ?? "CityScope mobility dataset"}</strong><span>{activity.observation_period}</span><span>H3 resolution {activity.h3_resolution}</span><span>{activity.attribution_text}</span></p>
      </aside>}

      <section id="explore" className="command-surface" aria-label="London mobility investigation workspace">
        <QuestionComposer value={question} isSubmitting={investigating} error={investigationError} onChange={setQuestion} onSubmit={() => void submitQuestion()} />
        {investigationError && <button type="button" className="secondary-button retry-investigation" onClick={() => void submitQuestion()}>Retry investigation</button>}
      </section>

      <section className="visual-workspace" aria-label="Interactive London mobility visualizations">
        <section className="map-card" aria-labelledby="map-heading">
          <div className="map-card-heading"><div><p className="eyebrow">Spatial view</p><h2 id="map-heading">London activity</h2></div><MapLegend hasPlaces={Boolean(investigation?.places.length)} hasRoute={Boolean(investigation?.route)} /></div>
          {activityLoading && <div className="map-skeleton" aria-live="polite"><span>Loading London activity...</span></div>}
          {activityError && !activityLoading && <div className="empty-state" role="alert"><h3>London activity is unavailable</h3><p>{activityError}</p><button type="button" className="secondary-button" onClick={() => void loadActivity()}>Retry London activity</button></div>}
          {!activityLoading && !activityError && <CityMap cells={mapCells} places={investigation?.places} route={investigation?.route} selectedH3Cell={selectedH3Cell} onSelectH3Cell={setSelectedH3Cell} />}
        </section>

        <div className="visual-sidebar">
          {activity && <ActivityOverview cells={activity.cells} selectedH3Cell={selectedH3Cell} onSelectH3Cell={setSelectedH3Cell} />}
          <div id="flow"><DataFlowPanel activityLoading={activityLoading} investigating={investigating} result={investigation} /></div>
        </div>
      </section>

      <section id="evidence" className={`evidence-workspace${investigation ? " has-result" : ""}`}>
        {investigation && <InvestigationResultPanel result={investigation} onSuggestion={setQuestion} />}
        {activity && <aside className="list-card" aria-labelledby="ranked-heading"><div className="section-heading compact"><p className="eyebrow">Historical ranking</p><h2 id="ranked-heading">Highest activity areas</h2><p>May 2026 starts and arrivals combined.</p></div><H3ActivityLayer cells={activity.cells} selectedH3Cell={selectedH3Cell} onSelectH3Cell={setSelectedH3Cell} /></aside>}
      </section>
    </main>
  );
}

function MapLegend({ hasPlaces, hasRoute }: { hasPlaces: boolean; hasRoute: boolean }) {
  return <div className="map-legend" aria-label="Map legend"><span><i className="legend-swatch legend-swatch--activity" />Activity</span>{hasPlaces && <span><i className="legend-swatch legend-swatch--place" />Places</span>}{hasRoute && <><span><i className="legend-swatch legend-swatch--route" />Route</span><span><i className="legend-swatch legend-swatch--endpoint" />Endpoints</span></>}</div>;
}
