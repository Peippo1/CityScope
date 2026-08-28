import type { FormEvent } from "react";

const EXAMPLE_QUESTIONS = [
  {
    label: "Find Saturday cycling hotspots",
    question: "Where was cycling activity highest on Saturday mornings?",
  },
  {
    label: "Compare busy areas and cafés",
    question: "Which of the busiest cycling areas have relatively few cafés nearby?",
  },
  {
    label: "Find public bathrooms",
    question: "Which busy cycling areas have public bathrooms nearby?",
  },
  {
    label: "Plan a bicycle route",
    question: "Plan a bicycle route between two busy cycling areas.",
  },
  {
    label: "Find stops along my route",
    question: "My route is Home to Richmond Park. Where are good coffee shops or public bathrooms along the way?",
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
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (value.trim() && !isSubmitting) onSubmit();
  }

  return (
    <section className="composer" aria-labelledby="investigate-heading">
      <div className="section-heading">
        <p className="eyebrow">Ask CityScope</p>
        <h2 id="investigate-heading">Where should your next ride take you?</h2>
        <p>Explore a historical {cityName} cycling snapshot, nearby places, or a bicycle route.</p>
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
            placeholder="Ask about cycling activity, cafés, or a route"
            maxLength={500}
            aria-describedby={error ? "investigation-error" : "question-help"}
          />
          <button type="submit" disabled={isSubmitting || !value.trim()}>
            {isSubmitting ? "Investigating…" : "Investigate"}
          </button>
        </div>
        <p id="question-help" className="helper-text">{cityName} only · based on May 2026 {datasetName ?? "mobility"} evidence{!isAuthenticated ? " · sign in with Google to use agents" : ""}</p>
        {error && <p id="investigation-error" className="inline-error" role="alert">{error}</p>}
      </form>
    </section>
  );
}
