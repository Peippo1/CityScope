import type { InvestigationResult } from "../types/investigation";

const FOOD_CATEGORIES = new Set(["cafe", "coffee_shop", "restaurant"]);

export function selectItineraryPlaces(places: InvestigationResult["places"]) {
  const unique = Array.from(new Map(places.map((place) => [place.place_id, place])).values());
  const foodStop = unique.find((place) => FOOD_CATEGORIES.has(place.category));
  const routeStops = unique.filter((place) => !FOOD_CATEGORIES.has(place.category)).slice(0, 3);
  return [...routeStops, ...(foodStop ? [foodStop] : [])].slice(0, 4);
}
