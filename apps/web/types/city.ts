export type ActivityCell = {
  h3_cell: string;
  total_journeys: number;
  origin_journeys: number;
  destination_journeys: number;
};

export type ActivityResponse = {
  city: string;
  dataset_name?: string | null;
  observation_period: string;
  attribution_text?: string | null;
  historical_snapshot: boolean;
  h3_resolution: number;
  cells: ActivityCell[];
};

export type CityCapability = {
  id: "london" | "new_york" | "chicago" | "washington_dc" | "paris";
  name: string;
  historical: boolean;
  routes: boolean;
  live_network: boolean;
  timezone: string;
  bounds: [number, number, number, number];
};

export type CitiesResponse = { cities: CityCapability[] };

export type CityComparison = {
  metric: string;
  calculation_basis: string;
  observation_period: string;
  cities: { city: string; city_name: string; value: number; rank: number; snapshot_id: string; is_fixture: boolean }[];
  limitations: string[];
};

export type LiveNetwork = {
  city: "paris";
  provider: string;
  provider_timestamp?: number | null;
  fetched_at: string;
  freshness: "fresh" | "delayed" | "stale" | "unknown";
  attribution_text: string;
  source_url: string;
  stations: { station_id: string; name?: string | null; latitude: number; longitude: number; bikes_available: number; docks_available: number; last_reported?: number | null }[];
  limitations: string[];
};
