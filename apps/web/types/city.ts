export type ActivityCell = {
  h3_cell: string;
  total_journeys: number;
  origin_journeys: number;
  destination_journeys: number;
};

export type ActivityResponse = {
  city: string;
  observation_period: string;
  h3_resolution: number;
  cells: ActivityCell[];
};
