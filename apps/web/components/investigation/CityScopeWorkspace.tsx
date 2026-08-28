"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getCities, getCityActivity, getCityComparison, getCityLiveNetwork, investigate } from "../../lib/api";
import type { ActivityResponse, CitiesResponse, CityCapability, CityComparison, LiveNetwork } from "../../types/city";
import type { InvestigationRequest, InvestigationResult } from "../../types/investigation";
import { CityMap, type FocusedMapPlace } from "../map/CityMap";
import { H3ActivityLayer } from "../map/H3ActivityLayer";
import { ActivityOverview } from "../visualization/ActivityOverview";
import { DataFlowPanel } from "../visualization/DataFlowPanel";
import { CityComparisonPanel } from "../visualization/CityComparisonPanel";
import { LiveNetworkPanel } from "../visualization/ParisLivePanel";
import { PlacesExplorer } from "../visualization/PlacesExplorer";
import { AccountActions } from "./AccountActions";
import { ComparisonQuestionComposer } from "./ComparisonQuestionComposer";
import { InvestigationResultPanel } from "./InvestigationResultPanel";
import { QuestionComposer } from "./QuestionComposer";
import { useFirebaseUser } from "../../lib/firebase";

type WorkspaceServices = {
  getActivity: (city?: string) => Promise<ActivityResponse>;
  investigate: (request: InvestigationRequest) => Promise<InvestigationResult>;
  getCities?: () => Promise<CitiesResponse>;
  getComparison?: (metric?: string) => Promise<CityComparison>;
  getLive?: (city: string) => Promise<LiveNetwork>;
};

const defaultServices: WorkspaceServices = { getCities, getActivity: getCityActivity, investigate, getComparison: getCityComparison, getLive: getCityLiveNetwork };
const comparisonMetrics = new Set([
  "trips_per_active_station_day",
  "median_trip_duration_minutes",
  "peak_hour_share",
  "weekend_share",
  "hotspot_concentration",
]);
const fallbackCities: CityCapability[] = [
  { id: "london", name: "London", historical: true, routes: true, live_network: false, timezone: "Europe/London", bounds: [51.28, -0.52, 51.72, 0.34] },
  { id: "new_york", name: "New York City", historical: true, routes: true, live_network: true, timezone: "America/New_York", bounds: [40.49, -74.30, 40.92, -73.68] },
  { id: "chicago", name: "Chicago", historical: true, routes: true, live_network: true, timezone: "America/Chicago", bounds: [41.64, -87.95, 42.08, -87.52] },
  { id: "washington_dc", name: "Washington, DC", historical: true, routes: true, live_network: true, timezone: "America/New_York", bounds: [38.76, -77.25, 39.02, -76.85] },
  { id: "paris", name: "Paris", historical: false, routes: false, live_network: true, timezone: "Europe/Paris", bounds: [48.75, 2.20, 48.95, 2.52] },
];

function messageFrom(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}

export function CityScopeWorkspace({ services = defaultServices }: { services?: WorkspaceServices }) {
  const [cities, setCities] = useState<CityCapability[]>(fallbackCities);
  const [activity, setActivity] = useState<ActivityResponse | null>(null);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityLoading, setActivityLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [investigating, setInvestigating] = useState(false);
  const [selectedH3Cell, setSelectedH3Cell] = useState<string | null>(null);
  const [submittedRequest, setSubmittedRequest] = useState<InvestigationRequest | null>(null);
  const [selectedCity, setSelectedCity] = useState<CityCapability>(fallbackCities[0]);
  const [view, setView] = useState<"explore" | "compare" | "live">("explore");
  const [comparison, setComparison] = useState<CityComparison | null>(null);
  const [comparisonMetric, setComparisonMetric] = useState("trips_per_active_station_day");
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonQuestion, setComparisonQuestion] = useState("");
  const [comparisonInvestigation, setComparisonInvestigation] = useState<InvestigationResult | null>(null);
  const [comparisonInvestigationError, setComparisonInvestigationError] = useState<string | null>(null);
  const [comparisonInvestigating, setComparisonInvestigating] = useState(false);
  const [liveNetwork, setLiveNetwork] = useState<LiveNetwork | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [currentPlaces, setCurrentPlaces] = useState<FocusedMapPlace[]>([]);
  const [focusedPlace, setFocusedPlace] = useState<FocusedMapPlace | null>(null);
  const { auth, user } = useFirebaseUser();

  useEffect(() => {
    if (!services.getCities) return;
    let cancelled = false;
    void services.getCities().then(({ cities: registryCities }) => {
      if (cancelled || registryCities.length === 0) return;
      setCities(registryCities);
      setSelectedCity((current) => registryCities.find((city) => city.id === current.id) ?? registryCities[0]);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [services]);

  const loadActivity = useCallback(async () => {
    if (!selectedCity.historical) {
      setActivity(null);
      setActivityError(null);
      setActivityLoading(false);
      return;
    }
    setActivityLoading(true);
    setActivityError(null);
    try {
      setActivity(await services.getActivity(selectedCity.id));
    } catch (reason: unknown) {
      setActivityError(messageFrom(reason, "Activity data could not be loaded"));
    } finally {
      setActivityLoading(false);
    }
  }, [services, selectedCity.historical, selectedCity.id]);

  useEffect(() => { void loadActivity(); }, [loadActivity]);

  const submitQuestion = useCallback(async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || investigating) return;
    if (auth && !user) {
      setInvestigationError("Sign in with Google to use CityScope agents. Browsing and comparisons remain available without sign-in.");
      return;
    }
    setInvestigating(true);
    setInvestigationError(null);
    try {
      const request = {
        city: selectedCity.id,
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
  }, [auth, investigating, question, selectedCity.id, selectedH3Cell, services, user]);

  const loadComparison = useCallback(async (metric = comparisonMetric) => {
    if (!services.getComparison) return;
    setComparisonError(null);
    setComparisonLoading(true);
    try { setComparison(await services.getComparison(metric)); } catch (reason) { setComparisonError(messageFrom(reason, "Comparison could not be loaded")); } finally { setComparisonLoading(false); }
  }, [comparisonMetric, services]);

  const submitComparisonQuestion = useCallback(async () => {
    const trimmedQuestion = comparisonQuestion.trim();
    if (!trimmedQuestion || comparisonInvestigating) return;
    setComparisonInvestigating(true);
    setComparisonInvestigationError(null);
    try {
      const request = {
        city: "london",
        question: trimmedQuestion,
        context: { selected_h3_cells: [], previous_turns: [], evidence_summary: "Cross-city comparison mode; normalized metrics only." },
      } satisfies InvestigationRequest;
      const result = await services.investigate(request);
      const selectedMetric = result.evidence.find((item) => item.source === "city_data")?.metric;
      if (selectedMetric && comparisonMetrics.has(selectedMetric) && selectedMetric !== comparisonMetric) {
        setComparisonMetric(selectedMetric);
        void loadComparison(selectedMetric);
      }
      setSubmittedRequest(request);
      setComparisonInvestigation(result);
    } catch (reason: unknown) {
      setComparisonInvestigationError(messageFrom(reason, "Cross-city investigation could not be completed"));
    } finally {
      setComparisonInvestigating(false);
    }
  }, [comparisonInvestigating, comparisonMetric, comparisonQuestion, loadComparison, services]);

  const loadLive = useCallback(async () => {
    if (!services.getLive || !selectedCity.live_network) return;
    setLiveError(null);
    setLiveLoading(true);
    try { setLiveNetwork(await services.getLive(selectedCity.id)); } catch (reason) { setLiveError(messageFrom(reason, `${selectedCity.name} live network is unavailable`)); } finally { setLiveLoading(false); }
  }, [selectedCity.id, selectedCity.live_network, selectedCity.name, services]);

  const changeView = useCallback((next: "explore" | "compare" | "live") => {
    setView(next);
    if (next === "compare" && !comparison) void loadComparison();
    if (next === "live" && (liveNetwork?.city !== selectedCity.id)) void loadLive();
  }, [comparison, liveNetwork?.city, loadComparison, loadLive, selectedCity.id]);

  const selectCity = useCallback((cityId: string) => {
    const city = cities.find((item) => item.id === cityId);
    if (!city) return;
    setSelectedCity(city);
    // Clear the previous city's snapshot immediately so its attribution cannot
    // remain visible while the newly selected city's activity is loading.
    setActivity(null);
    setActivityError(null);
    setCurrentPlaces([]);
    setFocusedPlace(null);
    setInvestigation(null);
    setSubmittedRequest(null);
    setSelectedH3Cell(null);
    setLiveNetwork(null);
    setLiveError(null);
    if (city.live_network && !city.historical) setView("live");
    else setView("explore");
  }, [cities]);

  useEffect(() => {
    if (view === "live" && selectedCity.live_network && liveNetwork?.city !== selectedCity.id) void loadLive();
  }, [liveNetwork?.city, loadLive, selectedCity.id, selectedCity.live_network, view]);

  const investigationCells = useMemo(() => investigation?.map_layers.map((layer) => ({
    h3_cell: layer.h3_cell,
    total_journeys: Number(layer.value),
  })) ?? [], [investigation]);
  const mapCells = investigationCells.length > 0 ? investigationCells : activity?.cells ?? [];

  return (
    <main id="main-content" className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main-content" aria-label="CityScope home">
          <span className="brand-mark" aria-hidden="true">
            <i className="brand-mark__cell brand-mark__cell--ink" />
            <i className="brand-mark__cell brand-mark__cell--teal" />
            <i className="brand-mark__cell brand-mark__cell--teal" />
            <i className="brand-mark__cell brand-mark__cell--ink" />
          </span><span>CityScope</span>
        </a>
        <nav className="view-nav" aria-label="Workspace sections">
          <button type="button" onClick={() => changeView("explore")} aria-pressed={view === "explore"} disabled={!selectedCity.historical}>Explore</button><button type="button" onClick={() => changeView("compare")} aria-pressed={view === "compare"}>Compare</button><button type="button" onClick={() => changeView("live")} aria-pressed={view === "live"} disabled={!selectedCity.live_network}>Live network</button>
        </nav>
        <AccountActions request={view === "live" ? null : submittedRequest} result={view === "compare" ? comparisonInvestigation : investigation} />
      </header>

      <section className="dashboard-intro" aria-labelledby="page-title">
        <div><p className="eyebrow">Cross-city bike-share intelligence</p><h1 id="page-title">Compare movement. Find patterns. Plan better routes.</h1></div>
        <p>Explore matched historical bike-share activity across four cities, then inspect optional station context where a live provider is available.</p>
      </section>

      <label className="city-switcher">City workspace<select value={selectedCity.id} onChange={(event) => selectCity(event.target.value)}>{cities.map((city) => <option key={city.id} value={city.id}>{city.name}{city.live_network && !city.historical ? " (live only)" : ""}</option>)}</select></label>

      {view === "compare" && <section className={`standalone-workspace comparison-workspace${comparisonInvestigation ? " has-agent-result" : ""}`}>
        <ComparisonQuestionComposer value={comparisonQuestion} isSubmitting={comparisonInvestigating} error={comparisonInvestigationError} onChange={setComparisonQuestion} onSubmit={() => void submitComparisonQuestion()} />
        {comparisonLoading && <div className="inline-loading" aria-live="polite">Calculating normalized May 2026 comparison...</div>}
        {comparison && <CityComparisonPanel comparison={comparison} metric={comparisonMetric} onMetricChange={(metric) => { setComparisonMetric(metric); void loadComparison(metric); }} onSelectCity={selectCity} />}
        {comparisonError && <div className="empty-state" role="alert"><p>{comparisonError}</p><button type="button" className="secondary-button" onClick={() => void loadComparison()}>Retry comparison</button></div>}
        {comparisonInvestigation && <div className="comparison-agent-result"><InvestigationResultPanel result={comparisonInvestigation} onSuggestion={setComparisonQuestion} /></div>}
      </section>}
      {view === "live" && <section className="standalone-workspace">{liveLoading && <div className="inline-loading" aria-live="polite">Loading current {selectedCity.name} station availability...</div>}{liveNetwork?.city === selectedCity.id && <LiveNetworkPanel cityName={selectedCity.name} bounds={selectedCity.bounds} network={liveNetwork} />}{liveError && <div className="empty-state" role="alert"><p>{liveError}</p><button type="button" className="secondary-button" onClick={() => void loadLive()}>Retry {selectedCity.name} live network</button></div>}</section>}

      {view === "explore" && (activity || activityLoading) && <aside className={`snapshot-banner${activityLoading ? " snapshot-banner--loading" : ""}`} aria-label="Historical dataset notice">
        <span className="source-badge source-badge--historical">Historical snapshot</span>
        {activity ? <p><strong>{activity.dataset_name ?? "CityScope mobility dataset"}</strong><span>{activity.observation_period}</span><span>H3 resolution {activity.h3_resolution}</span><span>{activity.attribution_text}</span></p> : <p><strong>Loading {selectedCity.name} mobility dataset…</strong><span>Refreshing city snapshot</span></p>}
      </aside>}

      {view === "explore" && <><section id="explore" className="command-surface" aria-label={`${selectedCity.name} mobility investigation workspace`}>
        <QuestionComposer cityName={selectedCity.name} datasetName={activity?.dataset_name} value={question} isSubmitting={investigating} error={investigationError} isAuthenticated={Boolean(user) || !auth} onChange={setQuestion} onSubmit={() => void submitQuestion()} />
        {investigationError && <button type="button" className="secondary-button retry-investigation" onClick={() => void submitQuestion()}>Retry investigation</button>}
      </section>

      <section className="visual-workspace" aria-label={`Interactive ${selectedCity.name} mobility visualizations`}>
        <section className="map-card" aria-labelledby="map-heading">
          <div className="map-card-heading"><div><p className="eyebrow">Spatial view</p><h2 id="map-heading">{selectedCity.name} activity</h2></div><MapLegend hasPlaces={currentPlaces.length > 0 || Boolean(investigation?.places.length)} hasRoute={Boolean(investigation?.route)} /></div>
          {activityLoading && <div className="map-skeleton" aria-live="polite"><span>Loading {selectedCity.name} activity...</span></div>}
          {activityError && !activityLoading && <div className="empty-state" role="alert"><h3>{selectedCity.name} activity is unavailable</h3><p>{activityError}</p><button type="button" className="secondary-button" onClick={() => void loadActivity()}>Retry {selectedCity.name} activity</button></div>}
          {!activityLoading && !activityError && <CityMap cells={mapCells} places={[...(investigation?.places ?? []), ...currentPlaces]} focusedPlace={focusedPlace} route={investigation?.route} selectedH3Cell={selectedH3Cell} onSelectH3Cell={setSelectedH3Cell} cityName={selectedCity.name} bounds={selectedCity.bounds} />}
        </section>

        <div className="visual-sidebar">
          {activity && <ActivityOverview cells={activity.cells} selectedH3Cell={selectedH3Cell} onSelectH3Cell={setSelectedH3Cell} cityName={selectedCity.name} />}
          <div id="flow"><DataFlowPanel activityLoading={activityLoading} investigating={investigating} result={investigation} snapshotLabel={activity?.dataset_name ?? `${selectedCity.name} historical snapshot`} /></div>
          <PlacesExplorer cityName={selectedCity.name} bounds={selectedCity.bounds} onPlacesChange={setCurrentPlaces} onSelectPlace={setFocusedPlace} />
        </div>
      </section>

      <section id="evidence" className={`evidence-workspace${investigation ? " has-result" : ""}`}>
        {investigation && <InvestigationResultPanel result={investigation} onSuggestion={setQuestion} />}
        {activity && <aside className="list-card" aria-labelledby="ranked-heading"><div className="section-heading compact"><p className="eyebrow">Historical ranking</p><h2 id="ranked-heading">Highest activity areas</h2><p>May 2026 starts and arrivals combined.</p></div><H3ActivityLayer cells={activity.cells} selectedH3Cell={selectedH3Cell} onSelectH3Cell={setSelectedH3Cell} /></aside>}
      </section></>}
    </main>
  );
}

function MapLegend({ hasPlaces, hasRoute }: { hasPlaces: boolean; hasRoute: boolean }) {
  return <div className="map-legend" aria-label="Map legend"><span><i className="legend-swatch legend-swatch--activity" />Activity</span>{hasPlaces && <span><i className="legend-swatch legend-swatch--place" />Places</span>}{hasRoute && <><span><i className="legend-swatch legend-swatch--route" />Route</span><span><i className="legend-swatch legend-swatch--endpoint" />Endpoints</span></>}</div>;
}
