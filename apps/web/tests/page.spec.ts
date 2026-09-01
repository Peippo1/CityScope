import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const route = {
  investigation_id: "route", status: "answered", answer: "A route worth remembering.", evidence: [], places: [{ place_id: "cafe", name: "Example Cafe", latitude: 51.5, longitude: -0.1, maps_uri: "https://maps.google.com/example", category: "cafe", h3_cell: "cell" }], amenity_analysis: [], city_insights: [], map_layers: [], limitations: [], trace: [], follow_up_suggestions: [],
  route: { travel_mode: "bicycle", distance_m: 2400, duration_seconds: 900, polyline: "encoded-route", source: "google_routes_api", attribution_title: "Google Routes API", attribution_url: "https://developers.google.com/maps/documentation/routes", warning: "Verify bicycle conditions locally.", origin: { name: "King's Cross", latitude: 51.53, longitude: -0.12 }, destination: { name: "Borough", latitude: 51.50, longitude: -0.11 }, waypoints: [] },
};

test("renders a concise route result with stops and no legacy panels", async ({ page }) => {
  await page.route("**/investigate", (request) => request.fulfill({ json: route }));
  await page.goto("/");
  await page.getByRole("textbox", { name: "Describe your route" }).fill("Cycle from King's Cross to Borough with coffee");
  await page.getByRole("button", { name: "Plan my route" }).click();
  await expect(page.getByRole("heading", { name: "Your ride" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "King's Cross → Borough" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Good places to pause" })).toBeVisible();
  await expect(page.getByText("Coffee stop")).toBeVisible();
  await expect(page.getByText("Request flow")).not.toBeVisible();
  await expect(page.getByText("Historical mobility evidence")).not.toBeVisible();
});

test("switches city and running mode without loading activity data", async ({ page }) => {
  await page.goto("/");
  await page.selectOption("select", "new_york");
  await page.getByRole("button", { name: /Running/ }).click();
  await expect(page.getByRole("heading", { name: "Plan a New York City journey" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Brooklyn 10K run" })).toBeVisible();
});

test("has no serious accessibility violations or mobile overflow", async ({ page }, testInfo) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""))).toEqual([]);
  if (testInfo.project.name.includes("mobile")) expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
});
