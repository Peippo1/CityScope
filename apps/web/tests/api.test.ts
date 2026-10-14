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
      "A mapping or AI provider is temporarily unavailable. Try again shortly.",
    );
  });

  it("distinguishes rate limits and provider timeouts for investigations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(Response.json({ detail: "Too many requests" }, { status: 429 }))
        .mockResolvedValueOnce(Response.json({ detail: "Investigation timed out. Try a narrower question." }, { status: 504 })),
    );
    const payload = {
      city: "london" as const,
      question: "Plan a route from King's Cross to Camden.",
      context: { selected_h3_cells: [], previous_turns: [] },
    };

    await expect(investigate(payload)).rejects.toThrow(
      "CityScope is busy or the request limit was reached. Try again shortly.",
    );
    await expect(investigate(payload)).rejects.toThrow(
      "Investigation timed out. Try a narrower question.",
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
