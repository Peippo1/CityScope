import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const activity = {
  city: "london", dataset_name: "TfL Cycling", observation_period: "2026-05-01/2026-05-31", attribution_text: "TfL", historical_snapshot: true, h3_resolution: 9,
  cells: [{ h3_cell: "89194ad3353ffff", total_journeys: 42, origin_journeys: 20, destination_journeys: 22 }],
};

const baseInvestigation = {
  investigation_id: "test-investigation", status: "answered", answer: "The route connects two London locations.", dataset: { dataset_name: "TfL Cycling", observation_start: "2026-05-01", observation_end: "2026-05-31", historical: true, attribution_text: "TfL" }, evidence: [], places: [], amenity_analysis: [], city_insights: [], map_layers: [], limitations: [], trace: [], follow_up_suggestions: [],
};

const comparison = {
  metric: "trips_per_active_station_day",
  calculation_basis: "completed trips divided by active origin/destination stations and 31 observation days",
  observation_period: "2026-05-01/2026-05-31",
  cities: [
    { city: "new_york", city_name: "New York City", value: 64.4166, rank: 1, snapshot_id: "2026-05", is_fixture: false },
    { city: "london", city_name: "London", value: 34.6874, rank: 2, snapshot_id: "2026-05", is_fixture: false },
    { city: "washington_dc", city_name: "Washington, DC", value: 25.6582, rank: 3, snapshot_id: "2026-05", is_fixture: false },
    { city: "chicago", city_name: "Chicago", value: 13.7692, rank: 4, snapshot_id: "2026-05", is_fixture: false },
  ],
  limitations: ["Raw trip totals are intentionally excluded from cross-city rankings."],
};

test.beforeEach(async ({ page }) => {
  await page.route("**/cities/london/activity", (route) => route.fulfill({ json: activity }));
});

test("renders mocked route, warning, source, and waypoint explanation", async ({ page }) => {
  await page.route("**/investigate", (route) => route.fulfill({ json: { ...baseInvestigation, route: { travel_mode: "bicycle", distance_m: 2400, duration_seconds: 900, polyline: "encoded-route", source: "google_routes_api", attribution_title: "Google Routes API", attribution_url: "https://developers.google.com/maps/documentation/routes", warning: "Verify bicycle conditions locally.", origin: { name: "King's Cross", latitude: 51.53, longitude: -0.12 }, destination: { name: "Borough", latitude: 51.50, longitude: -0.11 }, waypoints: [{ h3_cell: "89194ad3353ffff", latitude: 51.51, longitude: -0.115, mobility_value: 42, score: 0.8, reason: "Historical activity 42 in the May 2026 snapshot." }] } } }));
  await page.goto("/");
  await page.getByRole("textbox", { name: "Question" }).fill("How can I cycle from King's Cross to Borough?");
  await page.getByRole("button", { name: "Investigate" }).click();
  await expect(page.getByRole("heading", { name: "Bicycle route" })).toBeVisible();
  await expect(page.getByText("King's Cross")).toBeVisible();
  await expect(page.getByText("Verify bicycle conditions locally.")).toBeVisible();
  await expect(page.getByText("Historical activity 42 in the May 2026 snapshot.", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Google Routes API" })).toHaveAttribute("href", /developers\.google\.com/);
});

test("keeps historical evidence and current amenity context separate", async ({ page }) => {
  await page.route("**/investigate", (route) => route.fulfill({ json: { ...baseInvestigation, answer: "Historical activity and current cafes are shown separately.", evidence: [{ source: "city_data", metric: "starts", value: 42, unit: "journeys", source_aggregate: "find_hotspots", h3_cells: ["89194ad3353ffff"] }, { source: "google_maps", metric: "place_count", value: 1, unit: "places", source_aggregate: "maps.search_places", h3_cells: ["89194ad3353ffff"], category: "cafe" }], places: [{ place_id: "place-cafe", name: "Example Cafe", latitude: 51.51, longitude: -0.115, maps_uri: "https://maps.google.com/example", category: "cafe", h3_cell: "89194ad3353ffff" }], amenity_analysis: [{ h3_cell: "89194ad3353ffff", category: "cafe", place_count: 1, mobility_value: 42, scarcity_rank: 1 }] } }));
  await page.goto("/");
  await page.getByRole("textbox", { name: "Question" }).fill("Which busy areas have few cafes nearby?");
  await page.getByRole("button", { name: "Investigate" }).click();
  await expect(page.getByRole("heading", { name: "Historical mobility evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Current Google Maps context" })).toBeVisible();
  await expect(page.getByText("Example Cafe")).toBeVisible();
  await expect(page.getByRole("link", { name: "View on Google Maps" })).toHaveAttribute("href", /maps\.google\.com/);
  await expect(page.getByRole("heading", { name: "Deterministic amenity comparison" })).toBeVisible();
});

test("shows accessible API failure state", async ({ page }) => {
  await page.unroute("**/cities/london/activity");
  await page.route("**/cities/london/activity", (route) => route.fulfill({ status: 503, body: "unavailable" }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "London activity is unavailable" })).toBeVisible();
  await expect(page.getByText("CityScope activity data could not be loaded")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry London activity" })).toBeVisible();
});

test("submits a bounded cross-city agent question and shows its evidence trace", async ({ page }) => {
  await page.route("**/cities/compare?*", (route) => route.fulfill({ json: comparison }));
  await page.route("**/investigate", (route) => route.fulfill({ json: {
    ...baseInvestigation,
    answer: "New York City ranks first for trips per active station per day in the matched May 2026 cohort.",
    evidence: comparison.cities.map((city) => ({ source: "city_data", metric: comparison.metric, value: city.value, unit: "trips/station/day", source_aggregate: "cross_city_canonical_trips", h3_cells: [], category: city.city_name })),
    limitations: comparison.limitations,
    trace: [{ kind: "tool_call", label: "Called City Data MCP: compare_cities", status: "completed", tool: "city_data.compare_cities", latency_ms: 4 }],
  } }));

  await page.goto("/");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await page.getByRole("button", { name: "Compare demand intensity" }).click();
  await page.getByRole("button", { name: "Ask across cities" }).click();

  await expect(page.getByText(/New York City ranks first/)).toBeVisible();
  await page.getByText("Evidence & methodology").click();
  await expect(page.getByText(/Called City Data MCP: compare_cities/)).toBeVisible();
  await expect(page.getByText(/Raw trip totals are intentionally excluded/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
});

test("is usable without a browser Maps key and has no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Google Maps preview unavailable until a browser API key is configured")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Highest activity areas" })).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""))).toEqual([]);
});

test("keeps the mobile workspace within the viewport", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"), "Mobile-only layout assertion");
  await page.goto("/");
  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflows).toBe(false);
  await expect(page.getByRole("heading", { name: "Where should your next ride take you?" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "London activity" })).toBeVisible();
});
