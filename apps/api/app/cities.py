from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


HistoricalCityId = Literal["london", "new_york", "chicago", "washington_dc"]
CityId = Literal["london", "new_york", "chicago", "washington_dc", "paris", "copenhagen", "barcelona", "madrid"]


@dataclass(frozen=True)
class CityDefinition:
    id: CityId
    name: str
    timezone: str
    bounds: tuple[float, float, float, float]
    historical: bool
    routes: bool
    live_network: bool
    maps_location: str
    region_code: str
    source_url: str
    licence_reference: str


CITIES: dict[CityId, CityDefinition] = {
    "london": CityDefinition("london", "London", "Europe/London", (51.28, -0.52, 51.72, 0.34), True, True, False, "London, UK", "GB", "https://cycling.data.tfl.gov.uk/", "TfL Open Data"),
    "new_york": CityDefinition("new_york", "New York City", "America/New_York", (40.49, -74.30, 40.92, -73.68), True, True, True, "New York City, USA", "US", "https://citibikenyc.com/system-data", "NYCBS Data Use Policy"),
    "chicago": CityDefinition("chicago", "Chicago", "America/Chicago", (41.64, -87.95, 42.08, -87.52), True, True, True, "Chicago, Illinois, USA", "US", "https://data.cityofchicago.org/d/fg6s-gzvg", "City of Chicago Data Portal terms"),
    "washington_dc": CityDefinition("washington_dc", "Washington, DC", "America/New_York", (38.76, -77.25, 39.02, -76.85), True, True, True, "Washington, DC, USA", "US", "https://capitalbikeshare.com/system-data", "Capital Bikeshare Data License Agreement"),
    "paris": CityDefinition("paris", "Paris", "Europe/Paris", (48.75, 2.20, 48.95, 2.52), False, True, True, "Paris, France", "FR", "https://www.velib-metropole.fr/donnees-open-data-gbfs-du-service-velib-metropole", "Licence Ouverte / Open Licence"),
    "copenhagen": CityDefinition("copenhagen", "Copenhagen", "Europe/Copenhagen", (55.55, 12.40, 55.82, 12.75), False, True, False, "Copenhagen, Denmark", "DK", "https://www.visitcopenhagen.com/copenhagen/planning/cycling-copenhagen", "VisitCopenhagen public guidance"),
    "barcelona": CityDefinition("barcelona", "Barcelona", "Europe/Madrid", (41.30, 2.02, 41.50, 2.30), False, True, False, "Barcelona, Spain", "ES", "https://www.barcelona.cat/en/what-to-do-in-bcn/sport/cycling", "Barcelona public guidance"),
    "madrid": CityDefinition("madrid", "Madrid", "Europe/Madrid", (40.30, -3.85, 40.55, -3.55), False, True, False, "Madrid, Spain", "ES", "https://www.esmadrid.com/en/madrid-cycling", "Madrid public guidance"),
}


def get_city(city: str) -> CityDefinition:
    try:
        return CITIES[city]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"Unsupported city: {city}") from exc


def historical_city_ids() -> tuple[HistoricalCityId, ...]:
    return ("london", "new_york", "chicago", "washington_dc")
