export type InvestigationRequest = {
  city: "london";
  question: string;
  context: { selected_h3_cells: string[]; previous_turns: { role: "user" | "assistant"; content: string }[]; evidence_summary?: string };
};

export type InvestigationResult = {
  investigation_id: string;
  status: "answered" | "unsupported" | "failed";
  answer: string;
  dataset?: { dataset_name: string; observation_start: string; observation_end: string; historical: boolean; attribution_text?: string };
  evidence: { metric: string; value: number; unit: string; source_aggregate: string; h3_cells: string[] }[];
  map_layers: { h3_cell: string; metric: string; value: number; rank?: number }[];
  limitations: string[];
  trace: { kind: string; label: string; status: string; tool?: string; result_count?: number }[];
  follow_up_suggestions: string[];
};
