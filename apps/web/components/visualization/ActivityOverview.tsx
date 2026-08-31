import type { ActivityCell } from "../../types/city";

type ActivityOverviewProps = {
  cells: ActivityCell[];
  selectedH3Cell: string | null;
  onSelectH3Cell: (h3Cell: string) => void;
  cityName?: string;
};

export function ActivityOverview({ cells, selectedH3Cell, onSelectH3Cell, cityName = "London" }: ActivityOverviewProps) {
  const highlightCells = cells.slice(0, 3);
  const peakCell = highlightCells[0];
  const total = cells.reduce((sum, cell) => sum + cell.total_journeys, 0);

  return (
    <section className="activity-overview" aria-labelledby="activity-pulse-heading">
      <header className="panel-heading">
        <div><p className="eyebrow">Mobility evidence</p><h2 id="activity-pulse-heading">Where people ride</h2></div>
        <span className="live-label"><i aria-hidden="true" />Snapshot</span>
      </header>
      <dl className="activity-summary">
        <div><dt>Observed journeys</dt><dd>{total.toLocaleString()}</dd></div>
        <div><dt>Busiest area</dt><dd>{peakCell?.area_name ?? "—"}</dd></div>
        <div><dt>Mapped areas</dt><dd>{cells.length}</dd></div>
      </dl>
      <p className="activity-intro">Historical cycling activity can help you choose a lively starting point. Select an area to see it on the map.</p>
      <ol className="activity-highlights" aria-label={`Busiest ${cityName} cycling areas`}>
        {highlightCells.map((cell, index) => (
          <button
            type="button"
            className={`activity-highlight${cell.h3_cell === selectedH3Cell ? " is-selected" : ""}`}
            key={cell.h3_cell}
            onClick={() => onSelectH3Cell(cell.h3_cell)}
            aria-label={`Select ${cell.area_name ?? `area ${index + 1}`} with ${cell.total_journeys.toLocaleString()} journeys`}
            aria-pressed={cell.h3_cell === selectedH3Cell}
          >
            <span className="activity-highlight-rank">{index + 1}</span>
            <span className="activity-highlight-copy"><strong>{cell.area_name ?? `Area ${index + 1}`}</strong><small>{cell.origin_journeys.toLocaleString()} starts · {cell.destination_journeys.toLocaleString()} arrivals</small></span>
            <span className="activity-highlight-value">{cell.total_journeys.toLocaleString()}<small>journeys</small></span>
          </button>
        ))}
      </ol>
      <p className="chart-caption">{cityName} historical snapshot · not a live popularity ranking.</p>
    </section>
  );
}
