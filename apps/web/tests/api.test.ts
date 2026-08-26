import { afterEach, describe, expect, it, vi } from "vitest";
import { getLondonActivity, investigate } from "../lib/api";

describe("CityScope API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("turns a network failure into a useful service error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(getLondonActivity()).rejects.toThrow(
      "CityScope API is unreachable. Check the API service and try again.",
    );
  });

  it("includes the response status when activity loading fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));

    await expect(getLondonActivity()).rejects.toThrow(
      "CityScope activity data could not be loaded (503)",
    );
  });

  it("posts an investigation through the shared API request boundary", async () => {
    const response = { investigation_id: "test", status: "answered", answer: "Grounded result" };
    const fetchMock = vi.fn().mockResolvedValue(Response.json(response));
    vi.stubGlobal("fetch", fetchMock);
    const payload = {
      city: "london" as const,
      question: "Where are the hotspots?",
      context: { selected_h3_cells: [], previous_turns: [] },
    };

    await expect(investigate(payload)).resolves.toEqual(response);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/investigate",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) }),
    );
  });
});
