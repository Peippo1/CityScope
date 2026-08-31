import { useEffect, useState, type FormEvent } from "react";

type SpeechRecognition = {
  lang: string;
  interimResults: boolean;
  onresult: (event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void;
  onerror: () => void;
  onend: () => void;
  start: () => void;
};

const LONDON_EXAMPLES = [
  {
    label: "Find Saturday cycling hotspots",
    question: "Where was cycling activity highest on Saturday mornings?",
  },
  {
    label: "Fulham scenic loop",
    question: "I'm in Fulham and would like a scenic loop to Richmond Park with bathrooms, coffee, lunch, and interesting things to see.",
  },
  {
    label: "Coffee and bathroom stop",
    question: "Plan a quiet park route with a coffee shop and public bathroom stop.",
  },
  {
    label: "Lunch after a ride",
    question: "Suggest a good lunch stop after a scenic bicycle ride.",
  },
  {
    label: "Interesting quiet route",
    question: "Find interesting places along a quiet scenic route.",
  },
  {
    label: "Plan a running route",
    question: "I want a 10K running route with interesting sights and coffee at the finish.",
  },
] as const;

const CITY_EXAMPLES: Record<string, { start: string; destination: string; examples: readonly { label: string; question: string }[] }> = {
  "New York City": {
    start: "Chelsea or Central Park",
    destination: "Prospect Park or the Hudson River Greenway",
    examples: [
      { label: "Hudson scenic ride", question: "I'm in Chelsea and would like a scenic ride along the Hudson River Greenway with coffee and interesting stops." },
      { label: "Central Park loop", question: "Plan a quiet loop around Central Park with a bathroom and lunch stop." },
      { label: "Brooklyn waterfront", question: "Find a waterfront route from DUMBO to Brooklyn Bridge Park with cafes." },
      { label: "Brooklyn 10K run", question: "I've just got to New York, where can I run around Brooklyn, what should I see and where can I stop for coffee at the end of my 10K?" },
    ],
  },
  Chicago: {
    start: "Lincoln Park or The Loop",
    destination: "Hyde Park or the Lakefront Trail",
    examples: [
      { label: "Lakefront scenic ride", question: "I'm in Lincoln Park and want a scenic ride along the Lakefront Trail with coffee and bathrooms." },
      { label: "606 park route", question: "Plan a quiet ride from Wicker Park along the 606 with lunch nearby." },
      { label: "River architecture ride", question: "Find interesting architecture and restaurants along a Chicago River route." },
    ],
  },
  "Washington, DC": {
    start: "Georgetown or the National Mall",
    destination: "Bethesda or the Tidal Basin",
    examples: [
      { label: "Capital Crescent ride", question: "I'm in Georgetown and would like a quiet scenic ride to Bethesda with coffee and lunch." },
      { label: "Monuments loop", question: "Plan a scenic loop around the National Mall and Tidal Basin with bathrooms." },
      { label: "Mount Vernon route", question: "Find interesting places along a riverside ride toward Alexandria." },
    ],
  },
  Paris: {
    start: "the Louvre or Bastille",
    destination: "the Eiffel Tower or Bois de Vincennes",
    examples: [
      { label: "Seine scenic ride", question: "I'm near the Louvre and want a scenic ride along the Seine with cafes and interesting sites." },
      { label: "Canal route", question: "Plan a quiet ride along Canal Saint-Martin with a bathroom and lunch stop." },
      { label: "Park loop", question: "Find a green loop through Bois de Vincennes with coffee nearby." },
    ],
  },
  Copenhagen: {
    start: "Nyhavn or Nørrebro",
    destination: "Amager Strand or the harbour",
    examples: [
      { label: "Harbour scenic ride", question: "I'm in Nyhavn and would like a scenic ride to Amager Strand with coffee and interesting stops." },
      { label: "Quiet lakes loop", question: "Plan a quiet loop around the Copenhagen Lakes with a bathroom and lunch stop." },
      { label: "Coastal route", question: "Find a green coastal ride toward Klampenborg with cafes." },
    ],
  },
  Barcelona: {
    start: "Barceloneta or Eixample",
    destination: "Port Olímpic or Montjuïc",
    examples: [
      { label: "Waterfront scenic ride", question: "I'm in Barceloneta and want a scenic ride to Port Olímpic with coffee and interesting places." },
      { label: "Montjuïc route", question: "Plan a park route to Montjuïc with bathrooms and lunch." },
      { label: "Besòs greenway", question: "Find a quiet ride along the Besòs River with a cafe stop." },
    ],
  },
  Madrid: {
    start: "Centro or Retiro",
    destination: "Madrid Río or Casa de Campo",
    examples: [
      { label: "Madrid Río ride", question: "I'm in Centro and would like a scenic ride along Madrid Río with coffee and interesting stops." },
      { label: "Casa de Campo loop", question: "Plan a quiet loop through Casa de Campo with a bathroom and lunch stop." },
      { label: "Park-to-park route", question: "Find a green ride from Retiro to Casa de Campo with cafes." },
    ],
  },
};

function examplesForCity(cityName: string, mode: "bicycle" | "running") {
  const cityExamples = CITY_EXAMPLES[cityName]?.examples;
  // Keep the cross-city historical question available where data exists,
  // while making route-oriented suggestions city-specific.
  const historical = new Set(["London", "New York City", "Chicago", "Washington, DC"]);
  const examples = cityExamples ? [...(historical.has(cityName) ? [LONDON_EXAMPLES[0]] : []), ...cityExamples] : LONDON_EXAMPLES;
  return mode === "running" ? [LONDON_EXAMPLES[LONDON_EXAMPLES.length - 1], ...(cityName === "New York City" ? [{ label: "Brooklyn 10K run", question: "I've just got to New York, where can I run around Brooklyn, what should I see and where can I stop for coffee at the end of my 10K?" }] : [])] : examples;
}

function cityPromptContext(cityName: string) {
  const context = CITY_EXAMPLES[cityName];
  return context ?? { start: "Fulham or Greenwich", destination: "Richmond Park or a riverside route" };
}

type QuestionComposerProps = {
  cityName: string;
  datasetName?: string | null;
  value: string;
  isSubmitting: boolean;
  error?: string | null;
  isAuthenticated?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
  mode?: "bicycle" | "running";
  onModeChange?: (mode: "bicycle" | "running") => void;
};

export function QuestionComposer({ cityName, datasetName, value, isSubmitting, error, isAuthenticated = true, onChange, onSubmit, mode = "bicycle", onModeChange }: QuestionComposerProps) {
  const [voiceAvailable, setVoiceAvailable] = useState(false);
  const [listening, setListening] = useState(false);
  const examples = examplesForCity(cityName, mode);
  const promptContext = cityPromptContext(cityName);
  useEffect(() => { setVoiceAvailable(typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)); }, []);
  function toggleVoice() {
    if (!voiceAvailable || typeof window === "undefined") return;
    const Recognition = (window as Window & { SpeechRecognition?: new () => SpeechRecognition; webkitSpeechRecognition?: new () => SpeechRecognition }).SpeechRecognition ?? (window as Window & { webkitSpeechRecognition?: new () => SpeechRecognition }).webkitSpeechRecognition;
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = "en-GB";
    recognition.interimResults = false;
    recognition.onresult = (event) => { onChange(event.results[0][0].transcript); setListening(false); };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    setListening(true);
    recognition.start();
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (value.trim() && !isSubmitting) onSubmit();
  }

  return (
    <section className="composer" aria-labelledby="investigate-heading">
      <div className="section-heading">
        <p className="eyebrow">Ask CityScope</p>
        <h2 id="investigate-heading">Plan a {cityName} journey</h2>
        <p>Tell us where you want to go and what would make the {mode === "running" ? "run" : "ride"} memorable.</p>
      </div>
      <div className="activity-mode" role="group" aria-label="Journey type">
        <button type="button" className={mode === "bicycle" ? "is-selected" : ""} aria-pressed={mode === "bicycle"} onClick={() => onModeChange?.("bicycle")}>🚲 Cycling</button>
        <button type="button" className={mode === "running" ? "is-selected" : ""} aria-pressed={mode === "running"} onClick={() => onModeChange?.("running")}>🏃 Running</button>
      </div>
      <div className="prompt-list" aria-label="Example questions">
        {examples.map((example) => (
          <button key={example.label} type="button" className="prompt-chip" onClick={() => onChange(example.question)}>
            {example.label}
          </button>
        ))}
      </div>
      <form onSubmit={submit}>
        <label htmlFor="investigation-question">Question</label>
        <div className="question-row">
          <input
            id="investigation-question"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={`e.g. a scenic loop from ${promptContext.start} to ${promptContext.destination} with coffee and lunch`}
            maxLength={500}
            aria-describedby={error ? "investigation-error" : "question-help"}
          />
          {voiceAvailable && <button type="button" className="secondary-button" onClick={toggleVoice} aria-label={listening ? "Listening" : "Use voice input"}>{listening ? "Listening…" : "🎙 Voice"}</button>}
          <button type="submit" disabled={isSubmitting || !value.trim()}>
            {isSubmitting ? "Investigating…" : "Investigate"}
          </button>
        </div>
        <p id="question-help" className="helper-text">Include a named start area such as {promptContext.start} · {cityName} journey planner · Google Maps, Routes, and grounded city evidence{!isAuthenticated ? " · sign in with Google to use agents" : ""}</p>
        {error && <p id="investigation-error" className="inline-error" role="alert">{error}</p>}
      </form>
    </section>
  );
}
