import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CityScopeWorkspace } from "../components/investigation/CityScopeWorkspace";
import type { ActivityResponse } from "../types/city";
import type { InvestigationResult } from "../types/investigation";

const activity: ActivityResponse = {
  city: "london",
  dataset_name: "TfL Cycling",
  observation_period: "2026-05-01/2026-05-31",
  attribution_text: "TfL",
  historical_snapshot: true,
  h3_resolution: 9,
  cells: [{ h3_cell: "89194ad3353ffff", total_journeys: 42, origin_journeys: 20, destination_journeys: 22 }],
};

const investigation: InvestigationResult = {
  investigation_id: "test",
  status: "answered",
  answer: "Area 1 had the highest historical cycling activity.",
  evidence: [], places: [], amenity_analysis: [], city_insights: [], map_layers: [], limitations: [], trace: [], follow_up_suggestions: [],
};

describe("CityScopeWorkspace", () => {
  it("lets a user retry activity loading without turning it into an investigation error", async () => {
    const user = userEvent.setup();
    const getActivity = vi.fn().mockRejectedValueOnce(new Error("Activity unavailable")).mockResolvedValueOnce(activity);
    render(<CityScopeWorkspace services={{ getActivity, investigate: vi.fn() }} />);

    expect(await screen.findByText("Activity unavailable")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry London activity" }));

    expect(await screen.findByRole("heading", { name: "Highest activity areas" })).toBeVisible();
    expect(screen.queryByText("Activity unavailable")).not.toBeInTheDocument();
  });

  it("submits a selected example question and renders the answer", async () => {
    const user = userEvent.setup();
    render(<CityScopeWorkspace services={{ getActivity: vi.fn().mockResolvedValue(activity), investigate: vi.fn().mockResolvedValue(investigation) }} />);

    await user.click(screen.getByRole("button", { name: "Find Saturday cycling hotspots" }));
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    expect(await screen.findByText(investigation.answer)).toBeVisible();
    expect(screen.getByText("Answered")).toBeVisible();
  });

  it("includes a selected activity area in the investigation context", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockResolvedValue(investigation);
    render(<CityScopeWorkspace services={{ getActivity: vi.fn().mockResolvedValue(activity), investigate }} />);

    await user.click(await screen.findByRole("button", { name: /Area 1/ }));
    await user.type(screen.getByRole("textbox", { name: "Question" }), "What is nearby?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));

    expect(investigate).toHaveBeenCalledWith(expect.objectContaining({
      context: expect.objectContaining({ selected_h3_cells: ["89194ad3353ffff"] }),
    }));
  });

  it("keeps an investigation failure local and lets the user retry it", async () => {
    const user = userEvent.setup();
    const investigate = vi.fn().mockRejectedValueOnce(new Error("Investigation unavailable")).mockResolvedValueOnce(investigation);
    render(<CityScopeWorkspace services={{ getActivity: vi.fn().mockResolvedValue(activity), investigate }} />);

    await user.type(screen.getByRole("textbox", { name: "Question" }), "Where are the hotspots?");
    await user.click(screen.getByRole("button", { name: "Investigate" }));
    expect(await screen.findByText("Investigation unavailable")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Highest activity areas" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Retry investigation" }));
    expect(await screen.findByText(investigation.answer)).toBeVisible();
    expect(screen.queryByText("Investigation unavailable")).not.toBeInTheDocument();
  });
});
