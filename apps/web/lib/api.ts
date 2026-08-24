import type { ActivityResponse } from "../types/city";
import type { InvestigationRequest, InvestigationResult } from "../types/investigation";

const API_URL = process.env.NEXT_PUBLIC_CITYSCOPE_API_URL ?? "http://localhost:8000";

export async function getLondonActivity(): Promise<ActivityResponse> {
  const response = await fetch(`${API_URL}/cities/london/activity`, { cache: "no-store" });
  if (!response.ok) throw new Error("CityScope activity data could not be loaded");
  return response.json() as Promise<ActivityResponse>;
}

export async function investigate(request: InvestigationRequest): Promise<InvestigationResult> {
  const response = await fetch(`${API_URL}/investigate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error("CityScope investigation could not be completed");
  return response.json() as Promise<InvestigationResult>;
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
  const response = await fetch(`${API_URL}/me/investigations`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${idToken}` },
    body: JSON.stringify({ request, result }),
  });
  if (!response.ok) throw new Error("CityScope could not save this investigation");
  return response.json() as Promise<SavedInvestigation>;
}
