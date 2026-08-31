import { useEffect, useState, type FormEvent } from "react";

type SpeechRecognition = {
  lang: string;
  interimResults: boolean;
  onresult: (event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void;
  onerror: () => void;
  onend: () => void;
  start: () => void;
};

const EXAMPLE_QUESTIONS = [
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
] as const;

type QuestionComposerProps = {
  cityName: string;
  datasetName?: string | null;
  value: string;
  isSubmitting: boolean;
  error?: string | null;
  isAuthenticated?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function QuestionComposer({ cityName, datasetName, value, isSubmitting, error, isAuthenticated = true, onChange, onSubmit }: QuestionComposerProps) {
  const [voiceAvailable, setVoiceAvailable] = useState(false);
  const [listening, setListening] = useState(false);
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
        <p>Give us a named start point and destination, then describe the route, stops, and places you want to discover.</p>
      </div>
      <div className="prompt-list" aria-label="Example questions">
        {EXAMPLE_QUESTIONS.map((example) => (
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
            placeholder="e.g. a scenic loop from Fulham to Richmond Park with coffee and lunch"
            maxLength={500}
            aria-describedby={error ? "investigation-error" : "question-help"}
          />
          {voiceAvailable && <button type="button" className="secondary-button" onClick={toggleVoice} aria-label={listening ? "Listening" : "Use voice input"}>{listening ? "Listening…" : "🎙 Voice"}</button>}
          <button type="submit" disabled={isSubmitting || !value.trim()}>
            {isSubmitting ? "Investigating…" : "Investigate"}
          </button>
        </div>
        <p id="question-help" className="helper-text">Include a named start area such as Fulham or Greenwich · {cityName} journey planner · Google Maps, Routes, and grounded May 2026 evidence{!isAuthenticated ? " · sign in with Google to use agents" : ""}</p>
        {error && <p id="investigation-error" className="inline-error" role="alert">{error}</p>}
      </form>
    </section>
  );
}
