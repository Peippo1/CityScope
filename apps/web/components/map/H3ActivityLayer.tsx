import type { ActivityCell } from "../../types/city";

export function H3ActivityLayer({ cells }: { cells: ActivityCell[] }) {
  return <ol aria-label="Highest activity H3 cells">
    {cells.map((cell) => <li key={cell.h3_cell}><code>{cell.h3_cell}</code>: {cell.total_journeys} journeys ({cell.origin_journeys} starts, {cell.destination_journeys} ends)</li>)}
  </ol>;
}
