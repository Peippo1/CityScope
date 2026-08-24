import { expect, test } from "@playwright/test";

const activity = {
  city: "london", dataset_name: "TfL Cycling", observation_period: "2026-05-01/2026-05-31", attribution_text: "TfL", historical_snapshot: true, h3_resolution: 9,
  cells: [{ h3_cell: "89194ad3353ffff", metric: "total_journeys", total_journeys: 42, rank: 1 }],
};

const baseInvestigation = {
  investigation_id: "test-investigation", status: "answered", answer: "The route connects two London locations.", dataset: { dataset_name: "TfL Cycling", observation_start: "2026-05-01", observation_end: "2026-05-31", historical: true, attribution_text: "TfL" }, evidence: [], places: [], amenity_analysis: [], city_insights: [], map_layers: [], limitations: [], trace: [], follow_up_suggestions: [],
};

test.beforeEach(async ({ page }) => {
  await page.route("**/cities/london/activity", (route) => route.fulfill({ json: activity }));
});

test("renders mocked route, warning, source, and waypoint explanation", async ({ page }) => {
  await page.route("**/investigate", (route) => route.fulfill({ json: { ...baseInvestigation, route: { travel_mode: "bicycle", distance_m: 2400, duration_seconds: 900, polyline: "encoded-route", source: "google_routes_api", attribution_title: "Google Routes API", attribution_url: "https://developers.google.com/maps/documentation/routes", warning: "Verify bicycle conditions locally.", origin: { name: "King's Cross", latitude: 51.53, longitude: -0.12 }, destination: { name: "Borough", latitude: 51.50, longitude: -0.11 }, waypoints: [{ h3_cell: "89194ad3353ffff", latitude: 51.51, longitude: -0.115, mobility_value: 42, score: 0.8, reason: "Historical activity 42 in the May 2026 snapshot." }] } } }));
  await page.goto("/");
  await page.getByLabel("Question").fill("How can I cycle from King's Cross to Borough?");
  await page.getByRole("button", { name: "Investigate" }).click();
  await expect(page.getByRole("heading", { name: "Bicycle route" })).toBeVisible();
  await expect(page.getByText("King's Cross")).toBeVisible();
  await expect(page.getByText("Verify bicycle conditions locally.")).toBeVisible();
  await expect(page.getByText(/Historical activity 42/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Google Routes API" })).toHaveAttribute("href", /developers\.google\.com/);
});

test("keeps historical evidence and current amenity context separate", async ({ page }) => {
  await page.route("**/investigate", (route) => route.fulfill({ json: { ...baseInvestigation, answer: "Historical activity and current cafes are shown separately.", evidence: [{ source: "city_data", metric: "starts", value: 42, unit: "journeys", source_aggregate: "find_hotspots", h3_cells: ["89194ad3353ffff"] }, { source: "google_maps", metric: "place_count", value: 1, unit: "places", source_aggregate: "maps.search_places", h3_cells: ["89194ad3353ffff"], category: "cafe" }], places: [{ place_id: "place-cafe", name: "Example Cafe", latitude: 51.51, longitude: -0.115, maps_uri: "https://maps.google.com/example", category: "cafe", h3_cell: "89194ad3353ffff" }], amenity_analysis: [{ h3_cell: "89194ad3353ffff", category: "cafe", place_count: 1, mobility_value: 42, scarcity_rank: 1 }] } }));
  await page.goto("/");
  await page.getByLabel("Question").fill("Which busy areas have few cafes nearby?");
  await page.getByRole("button", { name: "Investigate" }).click();
  await expect(page.getByRole("heading", { name: "Historical TfL evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Current Google Maps context" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Example Cafe" })).toHaveAttribute("href", /maps\.google\.com/);
  await expect(page.getByRole("heading", { name: "Deterministic amenity comparison" })).toBeVisible();
});

test("shows accessible API failure state", async ({ page }) => {
  await page.unroute("**/cities/london/activity");
  await page.route("**/cities/london/activity", (route) => route.fulfill({ status: 503, body: "unavailable" }));
  await page.goto("/");
  await expect(page.locator("p.error")).toHaveText("CityScope activity data could not be loaded");
});
