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
