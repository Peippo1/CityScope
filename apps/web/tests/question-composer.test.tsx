import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { QuestionComposer } from "../components/investigation/QuestionComposer";

describe("QuestionComposer", () => {
  it("applies a structured example instead of only inserting prose", async () => {
    const user = userEvent.setup();
    const onApplyExample = vi.fn();
    render(<QuestionComposer cityName="Chicago" value="" isSubmitting={false} onChange={vi.fn()} onSubmit={vi.fn()} onApplyExample={onApplyExample} />);
    await user.click(screen.getByRole("button", { name: "Scenic park journey" }));
    expect(onApplyExample).toHaveBeenCalledWith(expect.objectContaining({ start: "Lincoln Park", destination: "Navy Pier" }));
  });

  it("requires endpoints for the primary action but allows Surprise me from an origin", () => {
    const { rerender } = render(<QuestionComposer cityName="London" value="" isSubmitting={false} canSubmit={false} canSurprise={false} onChange={vi.fn()} onSubmit={vi.fn()} onSurprise={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Plan my route" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Surprise me" })).toBeDisabled();
    rerender(<QuestionComposer cityName="London" value="" isSubmitting={true} canSubmit canSurprise onChange={vi.fn()} onSubmit={vi.fn()} onSurprise={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Planning route…" })).toBeDisabled();
    expect(screen.getByRole("status")).toBeVisible();
  });

  it("supports typed preferences in the expandable options", async () => {
    const user = userEvent.setup();
    function ComposerHarness() {
      const [value, setValue] = useState("");
      return <QuestionComposer cityName="London" value={value} isSubmitting={false} onChange={setValue} onSubmit={vi.fn()} canSubmit />;
    }
    render(<ComposerHarness />);
    await user.click(screen.getByText("Add preferences, stops and facilities"));
    await user.type(screen.getByLabelText("Natural-language preferences"), "quiet and green");
    expect(screen.getByLabelText("Natural-language preferences")).toHaveValue("quiet and green");
  });

  it("keeps planned stops, distance and facility controls available", async () => {
    const user = userEvent.setup();
    const onDistanceKmChange = vi.fn();
    const onFacilityCategoriesChange = vi.fn();
    render(<QuestionComposer cityName="London" value="" isSubmitting={false} onChange={vi.fn()} onSubmit={vi.fn()} onDistanceKmChange={onDistanceKmChange} onFacilityCategoriesChange={onFacilityCategoriesChange} />);
    await user.click(screen.getByText("Add preferences, stops and facilities"));
    await user.type(screen.getByLabelText(/Target distance/), "10");
    await user.click(screen.getByLabelText("Public toilets"));
    expect(onDistanceKmChange).toHaveBeenCalled();
    expect(onFacilityCategoriesChange).toHaveBeenCalledWith(["public_bathroom"]);
  });
});
