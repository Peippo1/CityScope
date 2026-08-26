import type { CityComparison } from "../../types/city";

const labels: Record<string, string> = {
  trips_per_active_station_day: "Trips per active station per day",
  median_trip_duration_minutes: "Median trip duration",
  peak_hour_share: "Peak-hour share",
  weekend_share: "Weekend share",
  hotspot_concentration: "Hotspot concentration",
};

export function CityComparisonPanel({ comparison, metric, onMetricChange }: { comparison: CityComparison; metric: string; onMetricChange: (metric: string) => void }) {
  const max = Math.max(...comparison.cities.map((city) => city.value), 1);
  return <section className="comparison-panel" aria-labelledby="comparison-heading">
    <div className="section-heading compact"><p className="eyebrow">Matched historical cohort</p><h2 id="comparison-heading">Four-city comparison</h2><p>May 2026 only. Rankings use normalized metrics, never raw journey totals.</p></div>
    <label className="metric-control">Metric<select value={metric} onChange={(event) => onMetricChange(event.target.value)}>{Object.entries(labels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
    {comparison.limitations.some((item) => item.startsWith("Development fixture")) && <p className="fixture-notice">{comparison.limitations.find((item) => item.startsWith("Development fixture"))}</p>}
    <ol className="comparison-list">{comparison.cities.map((city) => <li key={city.city}><span className="rank">{city.rank}</span><div><strong>{city.city_name}</strong><span className="comparison-bar"><i style={{ width: `${Math.max(4, city.value / max * 100)}%` }} /></span></div><output>{city.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}</output></li>)}</ol>
    <p className="list-footnote">{comparison.calculation_basis}.</p>
  </section>;
}
