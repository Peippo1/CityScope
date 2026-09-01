"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getCities, investigate } from "../../lib/api";
import type { CitiesResponse, CityCapability } from "../../types/city";
import type { InvestigationRequest, InvestigationResult } from "../../types/investigation";
import { CityMap, type FocusedMapPlace } from "../map/CityMap";
import { InvestigationResultPanel } from "./InvestigationResultPanel";
import { QuestionComposer } from "./QuestionComposer";

type WorkspaceServices = {
  investigate: (request: InvestigationRequest) => Promise<InvestigationResult>;
  getCities?: () => Promise<CitiesResponse>;
};

const defaultServices: WorkspaceServices = { getCities, investigate };
const fallbackCities: CityCapability[] = [
  { id: "london", name: "London", historical: true, routes: true, live_network: false, timezone: "Europe/London", bounds: [51.28, -0.52, 51.72, 0.34] },
  { id: "new_york", name: "New York City", historical: true, routes: true, live_network: true, timezone: "America/New_York", bounds: [40.49, -74.30, 40.92, -73.68] },
  { id: "chicago", name: "Chicago", historical: true, routes: true, live_network: true, timezone: "America/Chicago", bounds: [41.64, -87.95, 42.08, -87.52] },
  { id: "washington_dc", name: "Washington, DC", historical: true, routes: true, live_network: true, timezone: "America/New_York", bounds: [38.76, -77.25, 39.02, -76.85] },
  { id: "paris", name: "Paris", historical: false, routes: true, live_network: true, timezone: "Europe/Paris", bounds: [48.75, 2.20, 48.95, 2.52] },
  { id: "copenhagen", name: "Copenhagen", historical: false, routes: true, live_network: false, timezone: "Europe/Copenhagen", bounds: [55.55, 12.40, 55.82, 12.75] },
  { id: "barcelona", name: "Barcelona", historical: false, routes: true, live_network: false, timezone: "Europe/Madrid", bounds: [41.30, 2.02, 41.50, 2.30] },
  { id: "madrid", name: "Madrid", historical: false, routes: true, live_network: false, timezone: "Europe/Madrid", bounds: [40.30, -3.85, 40.55, -3.55] },
];

export function CityScopeWorkspace({ services = defaultServices }: { services?: WorkspaceServices }) {
  const [cities, setCities] = useState<CityCapability[]>(fallbackCities);
  const [question, setQuestion] = useState("");
  const [journeyMode, setJourneyMode] = useState<"bicycle" | "running">("bicycle");
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [investigating, setInvestigating] = useState(false);
  const [selectedH3Cell, setSelectedH3Cell] = useState<string | null>(null);
  const [selectedCity, setSelectedCity] = useState<CityCapability>(fallbackCities[0]);
  const [focusedPlace, setFocusedPlace] = useState<FocusedMapPlace | null>(null);

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

  const submitQuestion = useCallback(async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || investigating) return;
    setInvestigating(true);
    setInvestigationError(null);
    try {
      const request = {
        city: selectedCity.id,
        question: `Plan this as a ${journeyMode === "running" ? "running" : "cycling"} route: ${trimmedQuestion}`,
        context: { selected_h3_cells: selectedH3Cell ? [selectedH3Cell] : [], previous_turns: [], evidence_summary: undefined },
      } satisfies InvestigationRequest;
      const result = await services.investigate(request);
      setInvestigation(result);
      setSelectedH3Cell(result.map_layers[0]?.h3_cell ?? null);
    } catch {
      setInvestigationError("CityScope couldn't complete this plan just now. Try again.");
    } finally {
      setInvestigating(false);
    }
  }, [investigating, journeyMode, question, selectedCity.id, selectedH3Cell, services]);

  const selectCity = useCallback((cityId: string) => {
    const city = cities.find((item) => item.id === cityId);
    if (!city) return;
    setSelectedCity(city);
    // Clear the previous city's snapshot immediately so its attribution cannot
    // remain visible while the newly selected city's activity is loading.
    setFocusedPlace(null);
    setInvestigation(null);
    setSelectedH3Cell(null);
    setJourneyMode("bicycle");
  }, [cities]);

  const investigationCells = useMemo(() => investigation?.map_layers.map((layer) => ({
    h3_cell: layer.h3_cell,
    total_journeys: Number(layer.value),
  })) ?? [], [investigation]);
  const mapPlaces = useMemo(() => investigation?.places ?? [], [investigation?.places]);

  return (
    <main id="main-content" className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main-content" aria-label="CityScope home"><span className="brand-mark" aria-hidden="true"><i className="brand-mark__cell brand-mark__cell--ink" /><i className="brand-mark__cell brand-mark__cell--teal" /><i className="brand-mark__cell brand-mark__cell--teal" /><i className="brand-mark__cell brand-mark__cell--ink" /></span><span>CityScope</span></a>
        <a className="build-story-link" href="/blog/cityscope">Build story</a>
      </header>
      <section className="dashboard-intro" aria-labelledby="page-title"><div><p className="eyebrow">CityScope</p><h1 id="page-title">Explore a city your way</h1></div><p>Tell CityScope where you are and how you want to explore. It will build a run or ride through interesting places, with a good stop along the way.</p></section>
      <label className="city-switcher">City<select value={selectedCity.id} onChange={(event) => selectCity(event.target.value)}>{cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}</select></label>
      <section id="explore" className="command-surface" aria-label={`${selectedCity.name} route planner`}>
        <QuestionComposer cityName={selectedCity.name} value={question} mode={journeyMode} onModeChange={setJourneyMode} isSubmitting={investigating} error={investigationError} onChange={setQuestion} onSubmit={() => void submitQuestion()} />
        {investigationError && <button type="button" className="secondary-button retry-investigation" onClick={() => void submitQuestion()}>Try again</button>}
      </section>
      <section className="route-workspace" aria-label={`${selectedCity.name} route results`}>
        <section className="map-card" aria-labelledby="map-heading"><div className="map-card-heading"><div><p className="eyebrow">Your route</p><h2 id="map-heading">{selectedCity.name}</h2></div><MapLegend hasPlaces={mapPlaces.length > 0} hasRoute={Boolean(investigation?.route)} /></div><CityMap cells={investigationCells} places={mapPlaces} focusedPlace={focusedPlace} route={investigation?.route} onSelectPlace={setFocusedPlace} cityName={selectedCity.name} bounds={selectedCity.bounds} ariaLabel={`${selectedCity.name} route map`} /></section>
        <div className="route-result-column">{investigation ? <InvestigationResultPanel result={investigation} onSuggestion={setQuestion} onSelectPlace={(place) => setFocusedPlace({ place_id: place.place_id, name: place.name ?? place.attribution_title?.replace(/\s+-\s+Google Maps$/i, "") ?? "Google Maps place", latitude: place.latitude, longitude: place.longitude, maps_uri: place.maps_uri })} /> : <div className="route-empty"><p className="eyebrow">Ready when you are</p><h2>Where will you explore?</h2><p>Pick a city, choose a ride or run, and tell us what would make the route special.</p></div>}</div>
      </section>
    </main>
  );
}

function MapLegend({ hasPlaces, hasRoute }: { hasPlaces: boolean; hasRoute: boolean }) {
  return <div className="map-legend" role="group" aria-label="Map legend">{hasPlaces && <span><i className="legend-swatch legend-swatch--place" />Stops</span>}{hasRoute && <><span><i className="legend-swatch legend-swatch--route" />Route</span><span><i className="legend-swatch legend-swatch--endpoint" />Start / finish</span></>}</div>;
}
