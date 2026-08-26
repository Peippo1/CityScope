import type { ActivityResponse } from "../types/city";
import type { InvestigationRequest, InvestigationResult } from "../types/investigation";

const API_URL = process.env.NEXT_PUBLIC_CITYSCOPE_API_URL ?? "http://localhost:8000";

async function apiRequest<T>(path: string, init: RequestInit | undefined, failureMessage: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error("CityScope API is unreachable. Check the API service and try again.");
  }
  if (!response.ok) throw new Error(`${failureMessage} (${response.status})`);
  return response.json() as Promise<T>;
}

export async function getLondonActivity(): Promise<ActivityResponse> {
  return apiRequest("/cities/london/activity", { cache: "no-store" }, "CityScope activity data could not be loaded");
}

export async function investigate(request: InvestigationRequest): Promise<InvestigationResult> {
  return apiRequest("/investigate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  }, "CityScope investigation could not be completed");
}

export type SavedInvestigation = {
  id: string;
  question: string;
  selected_h3_cells: string[];
  status: InvestigationResult["status"];
  summary: string;
  dataset_snapshot_id?: string | null;
  dataset_name?: string | null;
  historical_evidence: InvestigationResult["evidence"];
  created_at: string;
};

export async function saveInvestigation(request: InvestigationRequest, result: InvestigationResult, idToken: string): Promise<SavedInvestigation> {
  return apiRequest("/me/investigations", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${idToken}` },
    body: JSON.stringify({ request, result }),
  }, "CityScope could not save this investigation");
}
