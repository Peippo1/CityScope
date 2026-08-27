import type { FormEvent } from "react";

const EXAMPLE_QUESTIONS = [
  {
    label: "Compare demand intensity",
    question: "Across London, New York City, Chicago, and Washington, DC, which city has the most trips per active station per day?",
  },
  {
    label: "Compare peak-hour patterns",
    question: "Across London, New York City, Chicago, and Washington, DC, how does peak-hour trip share compare?",
  },
  {
    label: "Compare hotspot concentration",
    question: "Across London, New York City, Chicago, and Washington, DC, where is bike-share activity most concentrated in the busiest H3 cells?",
  },
] as const;

type ComparisonQuestionComposerProps = {
  value: string;
  isSubmitting: boolean;
  error?: string | null;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ComparisonQuestionComposer({ value, isSubmitting, error, onChange, onSubmit }: ComparisonQuestionComposerProps) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (value.trim() && !isSubmitting) onSubmit();
  }

  return <section className="comparison-composer" aria-labelledby="comparison-question-heading">
    <div className="section-heading compact">
      <p className="eyebrow">Ask across cities</p>
      <h2 id="comparison-question-heading">Let the agent choose the evidence workflow</h2>
      <p>CityScope selects one approved normalized metric and calls the private City Data MCP. Raw-volume rankings and routes are rejected.</p>
    </div>
    <div className="prompt-list" aria-label="Cross-city example questions">
      {EXAMPLE_QUESTIONS.map((example) => <button key={example.label} type="button" className="prompt-chip" onClick={() => onChange(example.question)}>{example.label}</button>)}
    </div>
    <form onSubmit={submit}>
      <label htmlFor="comparison-question">Cross-city question</label>
      <div className="question-row">
        <input id="comparison-question" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Ask how demand, duration, timing, or concentration differs" maxLength={500} aria-describedby={error ? "comparison-question-error" : "comparison-question-help"} />
        <button type="submit" disabled={isSubmitting || !value.trim()}>{isSubmitting ? "Comparing…" : "Ask across cities"}</button>
      </div>
      <p id="comparison-question-help" className="helper-text">London · New York City · Chicago · Washington, DC · matched May 2026 evidence</p>
      {error && <p id="comparison-question-error" className="inline-error" role="alert">{error}</p>}
    </form>
  </section>;
}
