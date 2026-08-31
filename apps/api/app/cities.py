from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from math import hypot


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

# Human-readable anchors used to explain H3 cells in the UI. These are labels
# for orientation, not claims that a cell follows an administrative boundary.
AREA_ANCHORS: dict[CityId, tuple[tuple[str, float, float], ...]] = {
    "london": (("Westminster",51.50,-0.13),("City of London",51.51,-0.09),("King's Cross",51.53,-0.12),("South Bank",51.50,-0.11),("Canary Wharf",51.50,-0.02),("Richmond",51.46,-0.30)),
    "new_york": (("Midtown Manhattan",40.75,-73.99),("Central Park",40.78,-73.97),("Lower Manhattan",40.71,-74.01),("Brooklyn",40.68,-73.98),("Long Island City",40.75,-73.94)),
    "chicago": (("The Loop",41.88,-87.63),("Lincoln Park",41.92,-87.64),("Hyde Park",41.79,-87.59),("Wicker Park",41.91,-87.68),("South Loop",41.86,-87.63)),
    "washington_dc": (("National Mall",38.89,-77.03),("Georgetown",38.91,-77.07),("Capitol Hill",38.89,-77.00),("Dupont Circle",38.91,-77.04),("Navy Yard",38.88,-76.99)),
    "paris": (("Louvre",48.86,2.34),("Eiffel Tower",48.86,2.29),("Bastille",48.85,2.37),("Montmartre",48.89,2.34),("Bois de Vincennes",48.83,2.43)),
    "copenhagen": (("City Centre",55.68,12.57),("Nørrebro",55.70,12.55),("Nyhavn",55.68,12.59),("Amager",55.65,12.61),("Østerbro",55.70,12.58)),
    "barcelona": (("Eixample",41.39,2.16),("Barceloneta",41.38,2.19),("Gràcia",41.40,2.15),("Montjuïc",41.36,2.15),("Poblenou",41.40,2.20)),
    "madrid": (("Centro",40.42,-3.70),("Retiro",40.42,-3.68),("Arganzuela",40.40,-3.70),("Casa de Campo",40.42,-3.75),("Salamanca",40.43,-3.68)),
}


def nearest_area_name(city: str, latitude: float, longitude: float) -> str:
    """Return the nearest curated orientation label for a cell centroid."""
    anchors = AREA_ANCHORS.get(city, ())
    if not anchors:
        return "Mapped area"
    # Longitude is scaled by latitude only for a stable local ordering.
    return min(anchors, key=lambda item: hypot((latitude - item[1]), (longitude - item[2]) * 0.65))[0]


def get_city(city: str) -> CityDefinition:
    try:
        return CITIES[city]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"Unsupported city: {city}") from exc


def historical_city_ids() -> tuple[HistoricalCityId, ...]:
    return ("london", "new_york", "chicago", "washington_dc")
