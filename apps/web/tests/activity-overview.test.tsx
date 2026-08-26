import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActivityOverview } from "../components/visualization/ActivityOverview";

const cells = [
  { h3_cell: "cell-a", total_journeys: 120, origin_journeys: 70, destination_journeys: 50 },
  { h3_cell: "cell-b", total_journeys: 80, origin_journeys: 30, destination_journeys: 50 },
];

describe("ActivityOverview", () => {
  it("summarises activity and lets users select a chart bar", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ActivityOverview cells={cells} selectedH3Cell={null} onSelectH3Cell={onSelect} />);

    expect(screen.getByText("200")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Select area 2 with 80 journeys" }));

    expect(onSelect).toHaveBeenCalledWith("cell-b");
  });
});
