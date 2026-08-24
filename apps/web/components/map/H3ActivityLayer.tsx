import type { ActivityCell } from "../../types/city";

export function H3ActivityLayer({ cells, selectedH3Cell, onSelectH3Cell }: { cells: ActivityCell[]; selectedH3Cell?: string | null; onSelectH3Cell?: (h3Cell: string) => void }) {
  return <ol className="activity-list" aria-label="Highest activity H3 cells">
    {cells.map((cell, index) => <li key={cell.h3_cell}><button type="button" className={selectedH3Cell === cell.h3_cell ? "activity-row is-selected" : "activity-row"} aria-pressed={selectedH3Cell === cell.h3_cell} onClick={() => onSelectH3Cell?.(cell.h3_cell)}><span className="rank">#{index + 1}</span><span className="activity-copy"><strong>Area {index + 1}</strong><small>{cell.origin_journeys} starts · {cell.destination_journeys} arrivals</small></span><span className="journey-value">{cell.total_journeys}<small>journeys</small></span></button></li>)}
  </ol>;
}
