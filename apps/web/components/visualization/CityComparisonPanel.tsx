import type { CityComparison } from "../../types/city";

const labels: Record<string, string> = {
  trips_per_active_station_day: "Trips per active station per day",
  median_trip_duration_minutes: "Median trip duration",
  peak_hour_share: "Peak-hour share",
  weekend_share: "Weekend share",
  hotspot_concentration: "Hotspot concentration",
};

const shareMetrics = new Set(["peak_hour_share", "weekend_share", "hotspot_concentration"]);

function formatValue(metric: string, value: number) {
  if (shareMetrics.has(metric)) return `${(value * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function CityComparisonPanel({ comparison, metric, onMetricChange, onSelectCity }: { comparison: CityComparison; metric: string; onMetricChange: (metric: string) => void; onSelectCity: (city: string) => void }) {
  const max = Math.max(...comparison.cities.map((city) => city.value), 1);
  const leader = comparison.cities[0];
  const last = comparison.cities.at(-1);
  const closest = comparison.cities.length > 1
    ? comparison.cities.slice(0, -1).map((city, index) => ({ first: city, second: comparison.cities[index + 1], gap: Math.abs(city.value - comparison.cities[index + 1].value) })).sort((a, b) => a.gap - b.gap)[0]
    : null;
  return <section className="comparison-panel" aria-labelledby="comparison-heading">
    <div className="section-heading compact"><p className="eyebrow">Matched historical cohort</p><h2 id="comparison-heading">Four-city comparison</h2><p>May 2026 only. Rankings use normalized metrics, never raw journey totals.</p></div>
    <label className="metric-control">Metric<select value={metric} onChange={(event) => onMetricChange(event.target.value)}>{Object.entries(labels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
    {comparison.limitations.some((item) => item.startsWith("Development fixture")) && <p className="fixture-notice">{comparison.limitations.find((item) => item.startsWith("Development fixture"))}</p>}
    {leader && last && <dl className="comparison-findings" aria-label="Deterministic comparison findings">
      <div><dt>Highest value</dt><dd>{leader.city_name}</dd><small>{formatValue(metric, leader.value)}</small></div>
      <div><dt>Cohort range</dt><dd>{formatValue(metric, leader.value - last.value)}</dd><small>Highest to lowest</small></div>
      {closest && <div><dt>Closest pair</dt><dd>{closest.first.city_name} &amp; {closest.second.city_name}</dd><small>{formatValue(metric, closest.gap)} apart</small></div>}
    </dl>}
    <ol className="comparison-list">{comparison.cities.map((city) => <li key={city.city}><button type="button" className="comparison-city" aria-label={`Open ${city.city_name} activity`} onClick={() => onSelectCity(city.city)}><span className="rank">{city.rank}</span><span className="comparison-city-value"><strong>{city.city_name}</strong><small>{city.is_fixture ? "Development fixture" : `Verified production artifact · ${city.snapshot_id}`}</small><span className="comparison-bar"><i style={{ width: `${Math.max(4, city.value / max * 100)}%` }} /></span></span><output>{formatValue(metric, city.value)}</output></button></li>)}</ol>
    <p className="list-footnote">{comparison.calculation_basis}.</p>
  </section>;
}
