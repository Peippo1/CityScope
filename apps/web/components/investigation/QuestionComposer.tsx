import { useEffect, useState, type FormEvent } from "react";
import { useLocale } from "../../lib/i18n";

type SpeechRecognition = {
  lang: string; interimResults: boolean;
  onresult: (event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void;
  onerror: () => void; onend: () => void; start: () => void;
};

export type ExamplePreset = { label: string; start: string; destination: string; question: string; facilities?: string[] };

const CITY_EXAMPLES: Record<string, ExamplePreset[]> = {
  London: [
    { label: "Scenic park journey", start: "King's Cross", destination: "Camden Market", question: "Keep the route scenic and near green space." },
    { label: "Coffee along the way", start: "King's Cross", destination: "Camden Market", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  Paris: [
    { label: "Seine park journey", start: "Place de la République", destination: "Bastille", question: "Keep the route pleasant and near green space." },
    { label: "Coffee along the way", start: "Place de la République", destination: "Bastille", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  Madrid: [
    { label: "Park journey", start: "Plaza de España", destination: "Madrid Río", question: "Keep the route pleasant and near green space." },
    { label: "Coffee along the way", start: "Plaza de España", destination: "Madrid Río", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  Rome: [
    { label: "Ancient park journey", start: "Colosseum", destination: "Circus Maximus", question: "Keep the route pleasant and near green space." },
    { label: "Coffee along the way", start: "Colosseum", destination: "Circus Maximus", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  "New York City": [
    { label: "Park journey", start: "Chelsea", destination: "Central Park", question: "Keep the route scenic and near green space." },
    { label: "Coffee along the way", start: "Chelsea", destination: "Brooklyn Bridge Park", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  Chicago: [
    { label: "Lakefront journey", start: "Lincoln Park", destination: "Navy Pier", question: "Keep the route scenic and near the lakefront." },
    { label: "Coffee along the way", start: "Lincoln Park", destination: "Millennium Park", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  "Washington, DC": [
    { label: "Monuments journey", start: "Georgetown Waterfront", destination: "National Mall", question: "Keep the route scenic and near the river." },
    { label: "Coffee along the way", start: "Georgetown", destination: "Tidal Basin", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  Copenhagen: [
    { label: "Harbour journey", start: "Nyhavn", destination: "Amager Strandpark", question: "Keep the route scenic and near the harbour." },
    { label: "Coffee along the way", start: "Nørrebro", destination: "The Lakes", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
  Barcelona: [
    { label: "Waterfront journey", start: "Barceloneta", destination: "Port Olímpic", question: "Keep the route scenic and near the water." },
    { label: "Coffee along the way", start: "Eixample", destination: "Parc de la Ciutadella", question: "Find coffee shops along the way.", facilities: ["cafe"] },
  ],
};
const DEFAULT_EXAMPLES: ExamplePreset[] = [
  { label: "Scenic park journey", start: "Fulham", destination: "Richmond Park", question: "Keep the route scenic and near green space." },
  { label: "Coffee along the way", start: "King's Cross", destination: "Camden Market", question: "Find coffee shops along the way.", facilities: ["cafe"] },
];

type QuestionComposerProps = {
  cityName: string; value: string; isSubmitting: boolean; error?: string | null;
  onChange: (value: string) => void; onSubmit: () => void; onSurprise?: () => void;
  onApplyExample?: (example: ExamplePreset) => void; canSubmit?: boolean; canSurprise?: boolean;
  mode?: "bicycle" | "running"; onModeChange?: (mode: "bicycle" | "running") => void;
  startLocation?: string; onStartLocationChange?: (value: string) => void;
  originMode?: "named" | "current_location"; onUseCurrentLocation?: () => void;
  locationError?: string | null; destination?: string; onDestinationChange?: (value: string) => void;
  distanceKm?: string; onDistanceKmChange?: (value: string) => void;
  facilityCategories?: string[]; onFacilityCategoriesChange?: (categories: string[]) => void;
  plannedStop?: string; onPlannedStopChange?: (value: string) => void;
};

export function QuestionComposer({ cityName, value, isSubmitting, error, onChange, onSubmit, onSurprise = () => undefined, onApplyExample = () => undefined, canSubmit = false, canSurprise = false, mode = "bicycle", onModeChange, startLocation = "", onStartLocationChange = () => undefined, originMode = "named", onUseCurrentLocation = () => undefined, locationError, destination = "", onDestinationChange = () => undefined, distanceKm = "", onDistanceKmChange = () => undefined, facilityCategories = [], onFacilityCategoriesChange = () => undefined, plannedStop = "", onPlannedStopChange = () => undefined }: QuestionComposerProps) {
  const { copy, locale } = useLocale();
  const [voiceAvailable, setVoiceAvailable] = useState(false);
  const [listening, setListening] = useState(false);
  const [generationStep, setGenerationStep] = useState(0);
  const examples = CITY_EXAMPLES[cityName] ?? DEFAULT_EXAMPLES;
  useEffect(() => { setVoiceAvailable(typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)); }, []);
  const generationMessages = ["Finding a good route…", "Checking the journey…", "Looking for useful stops…"];
  useEffect(() => {
    if (!isSubmitting) { setGenerationStep(0); return; }
    const timer = window.setInterval(() => setGenerationStep((step) => (step + 1) % generationMessages.length), 1200);
    return () => window.clearInterval(timer);
  }, [isSubmitting]);
  function toggleVoice() {
    if (!voiceAvailable || typeof window === "undefined") return;
    const Recognition = (window as Window & { SpeechRecognition?: new () => SpeechRecognition; webkitSpeechRecognition?: new () => SpeechRecognition }).SpeechRecognition ?? (window as Window & { webkitSpeechRecognition?: new () => SpeechRecognition }).webkitSpeechRecognition;
    if (!Recognition) return;
    const recognition = new Recognition(); recognition.lang = locale; recognition.interimResults = false;
    recognition.onresult = (event) => { onChange(event.results[0][0].transcript); setListening(false); };
    recognition.onerror = () => setListening(false); recognition.onend = () => setListening(false);
    setListening(true); recognition.start();
  }
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (canSubmit && !isSubmitting) onSubmit(); }

  return (
    <section className="composer" aria-labelledby="investigate-heading">
      <div className="section-heading">
        <p className="eyebrow">{copy.ask}</p><h2 id="investigate-heading">{copy.routePlanner}</h2>
        <p>{copy.journeyIntro}</p><p className="composer-note">{copy.surpriseIntro}</p>
      </div>
      <div className="planner-fields">
        <fieldset className="activity-field"><legend>{copy.travelMode}</legend><div className="activity-mode" role="group" aria-label={copy.travelMode}>
          <button type="button" className={mode === "bicycle" ? "is-selected" : ""} aria-pressed={mode === "bicycle"} onClick={() => onModeChange?.("bicycle")}>{copy.cycling}</button>
          <button type="button" className={mode === "running" ? "is-selected" : ""} aria-pressed={mode === "running"} onClick={() => onModeChange?.("running")}>{copy.running}</button>
        </div></fieldset>
        <div className="route-controls" aria-label={copy.routeConstraints}>
          <label>{copy.startingPoint}<input value={startLocation} onChange={(event) => onStartLocationChange(event.target.value)} placeholder={copy.chooseStartingPoint} maxLength={120} readOnly={originMode === "current_location"} /></label>
          <button type="button" className="location-button" onClick={originMode === "current_location" ? () => onStartLocationChange("") : onUseCurrentLocation}>{originMode === "current_location" ? copy.changeStartingPoint : copy.useCurrentLocation}</button>
          <label>{copy.destination} <span className="field-hint">({destination ? copy.required : copy.destinationOptional})</span><input value={destination} onChange={(event) => onDestinationChange(event.target.value)} placeholder={copy.destinationPlaceholder} maxLength={120} /></label>
        </div>
        {locationError && <p className="inline-error" role="alert">{locationError}</p>}
        <details className="advanced-route-controls">
          <summary>{copy.advancedOptions}</summary>
          <label>{copy.preferences}<input value={value} onChange={(event) => onChange(event.target.value)} placeholder={copy.preferencesPlaceholder} maxLength={500} /></label>
          <label>{copy.plannedStop}<input value={plannedStop} onChange={(event) => onPlannedStopChange(event.target.value)} placeholder={copy.plannedStopPlaceholder} maxLength={120} /></label>
          <label>{copy.targetDistance} ({copy.optional})<input type="number" min="0.5" max="100" step="0.5" value={distanceKm} onChange={(event) => onDistanceKmChange(event.target.value)} placeholder="10" /></label>
          <fieldset><legend>{copy.facilities}</legend>{[["cafe", copy.cafes], ["restaurant", copy.restaurants], ["public_bathroom", copy.publicToilets], ["shop", copy.usefulShops]].map(([category, label]) => <label key={category}><input type="checkbox" checked={facilityCategories.includes(category)} onChange={(event) => onFacilityCategoriesChange(event.target.checked ? [...facilityCategories, category] : facilityCategories.filter((item) => item !== category))} />{label}</label>)}</fieldset>
        </details>
      </div>
      <form onSubmit={submit}>
        <div className="question-row">
          {voiceAvailable && <button type="button" className="secondary-button" onClick={toggleVoice} aria-label={listening ? copy.listening : copy.voiceInput}>{listening ? `${copy.listening}…` : `🎙 ${copy.voiceInput}`}</button>}
          <button type="submit" className={isSubmitting ? "create-route-button is-generating" : "create-route-button"} disabled={isSubmitting || !canSubmit} aria-busy={isSubmitting}>{isSubmitting ? copy.planning : copy.planRoute}</button>
          <button type="button" className="secondary-button surprise-button" onClick={onSurprise} disabled={isSubmitting || !canSurprise}>{copy.surpriseMe}</button>
        </div>
        <p className="helper-text">{isSubmitting ? <span className="generation-status" role="status" aria-live="polite"><span className="generation-spinner" aria-hidden="true" />{generationMessages[generationStep]}</span> : copy.surpriseHint}</p>
        {error && <p id="investigation-error" className="inline-error" role="alert">{error}</p>}
      </form>
      <div className="prompt-list" aria-label={copy.exampleJourneys}>{examples.map((example, index) => <button key={example.label} type="button" className="prompt-chip" onClick={() => onApplyExample({ ...example, question: index === 0 ? copy.scenicPreference : copy.coffeePreference })}>{index === 0 ? copy.exampleScenic : copy.exampleCoffee}</button>)}</div>
    </section>
  );
}
