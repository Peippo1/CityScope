import type { ActivityCell } from "../../types/city";

type ActivityOverviewProps = {
  cells: ActivityCell[];
  selectedH3Cell: string | null;
  onSelectH3Cell: (h3Cell: string) => void;
};

export function ActivityOverview({ cells, selectedH3Cell, onSelectH3Cell }: ActivityOverviewProps) {
  const chartCells = cells.slice(0, 10);
  const peak = Math.max(...chartCells.map((cell) => cell.total_journeys), 1);
  const total = cells.reduce((sum, cell) => sum + cell.total_journeys, 0);

  return (
    <section className="activity-overview" aria-labelledby="activity-pulse-heading">
      <header className="panel-heading">
        <div><p className="eyebrow">Activity pulse</p><h2 id="activity-pulse-heading">London at a glance</h2></div>
        <span className="live-label"><i aria-hidden="true" />Snapshot</span>
      </header>
      <dl className="activity-summary">
        <div><dt>Mapped journeys</dt><dd>{total.toLocaleString()}</dd></div>
        <div><dt>Peak area</dt><dd>{peak.toLocaleString()}</dd></div>
        <div><dt>H3 areas</dt><dd>{cells.length}</dd></div>
      </dl>
      <div className="bar-chart" role="group" aria-label="Top ten London cycling activity areas">
        {chartCells.map((cell, index) => (
          <button
            type="button"
            className={`chart-bar chart-bar--${index % 4}${cell.h3_cell === selectedH3Cell ? " is-selected" : ""}`}
            key={cell.h3_cell}
            onClick={() => onSelectH3Cell(cell.h3_cell)}
            aria-label={`Select area ${index + 1} with ${cell.total_journeys.toLocaleString()} journeys`}
            aria-pressed={cell.h3_cell === selectedH3Cell}
          >
            <span className="chart-value">{cell.total_journeys.toLocaleString()}</span>
            <span className="chart-column" style={{ height: `${Math.max(12, (cell.total_journeys / peak) * 100)}%` }} />
            <span className="chart-label">{index + 1}</span>
          </button>
        ))}
      </div>
      <p className="chart-caption">Select a bar to focus its H3 area and include it in your next investigation.</p>
    </section>
  );
}
