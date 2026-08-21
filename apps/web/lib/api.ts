import type { ActivityResponse } from "../types/city";

const API_URL = process.env.NEXT_PUBLIC_CITYSCOPE_API_URL ?? "http://localhost:8000";

export async function getLondonActivity(): Promise<ActivityResponse> {
  const response = await fetch(`${API_URL}/cities/london/activity`, { cache: "no-store" });
  if (!response.ok) throw new Error("CityScope activity data could not be loaded");
  return response.json() as Promise<ActivityResponse>;
}
