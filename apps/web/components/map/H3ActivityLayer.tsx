import type { ActivityCell } from "../../types/city";

export function H3ActivityLayer({ cells, selectedH3Cell, onSelectH3Cell }: { cells: ActivityCell[]; selectedH3Cell?: string | null; onSelectH3Cell?: (h3Cell: string) => void }) {
  const visibleCells = cells.slice(0, 12);
  return <><ol className="activity-list" aria-label="Highest activity H3 cells">
    {visibleCells.map((cell, index) => <li key={cell.h3_cell}><button type="button" className={selectedH3Cell === cell.h3_cell ? "activity-row is-selected" : "activity-row"} aria-label={`Select Area ${index + 1}${cell.area_name ? ` · ${cell.area_name}` : ""} with ${cell.total_journeys.toLocaleString()} journeys`} aria-pressed={selectedH3Cell === cell.h3_cell} onClick={() => onSelectH3Cell?.(cell.h3_cell)} title={`${cell.area_name ?? "Mapped area"} · H3 ${cell.h3_cell}`}><span className="rank">#{index + 1}</span><span className="activity-copy"><strong>{cell.area_name ?? `Mapped area ${index + 1}`}</strong><small>H3 {cell.h3_cell.slice(-6)} · {cell.origin_journeys.toLocaleString()} starts · {cell.destination_journeys.toLocaleString()} arrivals</small></span><span className="journey-value">{cell.total_journeys.toLocaleString()}<small>journeys</small></span></button></li>)}
  </ol>{cells.length > visibleCells.length && <p className="list-footnote">Showing the top {visibleCells.length} of {cells.length} mapped areas.</p>}</>;
}
