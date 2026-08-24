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
      return <QuestionComposer value={value} isSubmitting={false} onChange={setValue} onSubmit={vi.fn()} />;
    }
    render(<ComposerHarness />);

    await user.click(screen.getByRole("button", { name: "Find Saturday cycling hotspots" }));

    expect(screen.getByLabelText("Question")).toHaveValue(
      "Where was cycling activity highest on Saturday mornings?",
    );
  });

  it("prevents blank and in-flight submissions", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(<QuestionComposer value="" isSubmitting={false} onChange={vi.fn()} onSubmit={onSubmit} />);
    expect(screen.getByRole("button", { name: "Investigate" })).toBeDisabled();

    rerender(<QuestionComposer value="Where are the hotspots?" isSubmitting={true} onChange={vi.fn()} onSubmit={onSubmit} />);
    expect(screen.getByRole("button", { name: "Investigating…" })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
