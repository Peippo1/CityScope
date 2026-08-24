import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { H3ActivityLayer } from "../components/map/H3ActivityLayer";

describe("H3ActivityLayer", () => {
  it("lets a user select a ranked area without exposing raw H3 detail", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<H3ActivityLayer cells={[{ h3_cell: "89194ad3353ffff", total_journeys: 42, origin_journeys: 20, destination_journeys: 22 }]} selectedH3Cell={null} onSelectH3Cell={onSelect} />);

    await user.click(screen.getByRole("button", { name: /Area 1/ }));

    expect(onSelect).toHaveBeenCalledWith("89194ad3353ffff");
    expect(screen.queryByText("89194ad3353ffff")).not.toBeInTheDocument();
  });
});
