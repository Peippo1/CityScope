export type InvestigationRequest = {
  city: "london";
  question: string;
  context: { selected_h3_cells: string[]; previous_turns: { role: "user" | "assistant"; content: string }[]; evidence_summary?: string };
};

export type InvestigationResult = {
  investigation_id: string;
  status: "answered" | "partial" | "unsupported" | "failed";
  answer: string;
  dataset?: { dataset_name: string; observation_start: string; observation_end: string; historical: boolean; attribution_text?: string };
  evidence: { source: "city_data" | "google_maps"; metric: string; value: number; unit: string; source_aggregate: string; h3_cells: string[]; category?: string; search_radius_m?: number }[];
  places: { place_id: string; resource_name?: string; name?: string; latitude: number; longitude: number; maps_uri?: string; attribution_title?: string; attribution_url?: string; category: string; h3_cell: string }[];
  amenity_analysis: { h3_cell: string; category: string; place_count: number; mobility_value: number; scarcity_rank: number }[];
  map_layers: { h3_cell: string; metric: string; value: number; rank?: number }[];
  limitations: string[];
  trace: { kind: string; label: string; status: string; tool?: string; result_count?: number; latency_ms?: number }[];
  follow_up_suggestions: string[];
};
