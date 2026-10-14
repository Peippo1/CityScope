import type { ActivityResponse, CitiesResponse, CityComparison, LiveNetwork } from "../types/city";
import type { InvestigationRequest, InvestigationResult } from "../types/investigation";

const API_URL = process.env.NEXT_PUBLIC_CITYSCOPE_API_URL ?? "http://localhost:8000";

async function getApiErrorMessage(response: Response, failureMessage: string): Promise<string> {
  let detail: unknown;
  try {
    const payload: unknown = await response.clone().json();
    if (payload && typeof payload === "object" && "detail" in payload) {
      detail = payload.detail;
    }
  } catch {
    // Keep the status-specific fallback when the provider returns no JSON body.
  }

  if (response.status === 400 || response.status === 422) {
    return typeof detail === "string"
      ? `Request needs attention: ${detail}`
      : "Request needs attention. Check the journey details and try again.";
  }
  if (response.status === 429) {
    return "CityScope is busy or the request limit was reached. Try again shortly.";
  }
  if (response.status === 502 || response.status === 503) {
    return "A mapping or AI provider is temporarily unavailable. Try again shortly.";
  }
  if (response.status === 504) {
    return typeof detail === "string"
      ? detail
      : "The route service timed out. Try a narrower request.";
  }
  return `${failureMessage} (${response.status})`;
}

async function apiRequest<T>(path: string, init: RequestInit | undefined, failureMessage: string): Promise<T> {
  let response: Response;
  const method = (init?.method ?? "GET").toUpperCase();
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      response = await fetch(`${API_URL}${path}`, init);
    } catch {
      if (method === "GET" && attempt === 0) {
        await new Promise((resolve) => setTimeout(resolve, 350));
        continue;
      }
      throw new Error("CityScope API is unreachable. Check the API service and try again.");
    }
    if (response.ok) return response.json() as Promise<T>;
    if (method === "GET" && attempt === 0 && [502, 503, 504].includes(response.status)) {
      await new Promise((resolve) => setTimeout(resolve, 350));
      continue;
    }
    throw new Error(await getApiErrorMessage(response, failureMessage));
  }
  throw new Error(`${failureMessage} (503)`);
}

export async function getCityActivity(city = "london"): Promise<ActivityResponse> {
  return apiRequest(`/cities/${city}/activity`, { cache: "no-store" }, "CityScope activity data could not be loaded");
}

export const getLondonActivity = () => getCityActivity("london");

export async function getCities(): Promise<CitiesResponse> {
  return apiRequest("/cities", { cache: "no-store" }, "CityScope cities could not be loaded");
}

export async function getCityComparison(metric = "trips_per_active_station_day"): Promise<CityComparison> {
  return apiRequest(`/cities/compare?metric=${encodeURIComponent(metric)}`, { cache: "no-store" }, "CityScope comparison could not be loaded");
}

export async function getCityLiveNetwork(city: string): Promise<LiveNetwork> {
  return apiRequest(`/cities/${city}/live-network?limit=100`, { cache: "no-store" }, "Live network data could not be loaded");
}

export const getParisLiveNetwork = () => getCityLiveNetwork("paris");

export async function investigate(request: InvestigationRequest): Promise<InvestigationResult> {
  return apiRequest("/investigate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  }, "CityScope investigation could not be completed");
}

export type SavedInvestigation = {
  id: string;
  record_type: "historical_investigation" | "historical_comparison";
  question: string;
  selected_h3_cells: string[];
  status: InvestigationResult["status"];
  summary: string;
  dataset_snapshot_id?: string | null;
  dataset_name?: string | null;
  historical_evidence: InvestigationResult["evidence"];
  comparison_metric?: string | null;
  comparison_cities: string[];
  created_at: string;
};

export async function saveInvestigation(request: InvestigationRequest, result: InvestigationResult, idToken: string): Promise<SavedInvestigation> {
  return apiRequest("/me/investigations", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${idToken}` },
    body: JSON.stringify({ request, result }),
  }, "CityScope could not save this investigation");
}
