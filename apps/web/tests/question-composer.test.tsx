import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { QuestionComposer } from "../components/investigation/QuestionComposer";

describe("QuestionComposer", () => {
  it("lets a user choose an example question before submitting", async () => {
    const user = userEvent.setup();
    function ComposerHarness() {
      const [value, setValue] = useState("");
      return <QuestionComposer cityName="Chicago" datasetName="Divvy Trips" value={value} isSubmitting={false} onChange={setValue} onSubmit={vi.fn()} />;
    }
    render(<ComposerHarness />);

    await user.click(screen.getByRole("button", { name: "Lakefront scenic ride" }));

    expect(screen.getByLabelText("Describe your route")).toHaveValue(
      "I'm in Lincoln Park and want a scenic ride along the Lakefront Trail with coffee and bathrooms.",
    );
  });

  it("prevents blank and in-flight submissions", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(<QuestionComposer cityName="London" value="" isSubmitting={false} onChange={vi.fn()} onSubmit={onSubmit} />);
    expect(screen.getByRole("button", { name: "Plan my route" })).toBeDisabled();

    rerender(<QuestionComposer cityName="London" value="Where are the hotspots?" isSubmitting={true} onChange={vi.fn()} onSubmit={onSubmit} />);
    expect(screen.getByRole("button", { name: "Planning route…" })).toBeDisabled();
    expect(screen.getByRole("status")).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("updates route examples and start-point guidance for the selected city", () => {
    const { rerender } = render(<QuestionComposer cityName="London" value="" isSubmitting={false} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByPlaceholderText(/Fulham or Greenwich to Richmond Park or a riverside route/)).toBeVisible();
    expect(screen.getByText(/for example Fulham or Greenwich/)).toBeVisible();

    rerender(<QuestionComposer cityName="Barcelona" value="" isSubmitting={false} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Waterfront scenic ride" })).toBeVisible();
    expect(screen.getByPlaceholderText(/Barceloneta or Eixample to Port Olímpic or Montjuïc/)).toBeVisible();
    expect(screen.getByText(/for example Barceloneta or Eixample/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Fulham scenic loop" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /hotspots/i })).not.toBeInTheDocument();
  });
});
