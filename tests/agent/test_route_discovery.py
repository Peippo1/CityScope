import pytest

from apps.api.app.agent.route_discovery import RouteDiscoveryAgent
from apps.api.app.agent.route_service import RouteDetails, RouteLocation
from apps.api.app.agent.schemas import PlaceResult


def encode_polyline(points: list[tuple[float, float]]) -> str:
    encoded: list[str] = []
    previous_latitude = previous_longitude = 0
    for latitude, longitude in points:
        current_latitude = round(latitude * 100_000)
        current_longitude = round(longitude * 100_000)
        for delta in (current_latitude - previous_latitude, current_longitude - previous_longitude):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                encoded.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            encoded.append(chr(value + 63))
        previous_latitude, previous_longitude = current_latitude, current_longitude
    return "".join(encoded)


def route(points: list[tuple[float, float]]) -> RouteDetails:
    return RouteDetails(
        travel_mode="bicycle",
        distance_m=3000,
        duration_seconds=900,
        polyline=encode_polyline(points),
        origin=RouteLocation(name="Origin", latitude=points[0][0], longitude=points[0][1]),
        destination=RouteLocation(name="Destination", latitude=points[-1][0], longitude=points[-1][1]),
    )


def candidate(place_id: str, latitude: float, longitude: float) -> PlaceResult:
    return PlaceResult(
        place_id=place_id,
        name=place_id,
        latitude=latitude,
        longitude=longitude,
        category="cafe",
        h3_cell="test",
    )


def test_agent_returns_at_most_three_verified_recommendations() -> None:
    journey = route([(51.50, -0.14), (51.50, -0.10), (51.50, -0.06)])
    places = [candidate(f"cafe-{index}", 51.5001, -0.12 + index * 0.01) for index in range(5)]

    recommendations = RouteDiscoveryAgent().recommend(journey, places, target_fraction=0.5)

    assert len(recommendations) == 3
    assert all(place.latitude is not None and place.longitude is not None for place in recommendations)


@pytest.mark.parametrize(("points", "local_candidate"), [
    ([(51.5308, -0.1238), (51.5392, -0.1426)], (51.5350, -0.1332)),  # London
    ([(48.8674, 2.3630), (48.8530, 2.3690)], (48.8602, 2.3660)),  # Paris
    ([(40.4234, -3.7122), (40.4133, -3.7223)], (40.4184, -3.7172)),  # Madrid
    ([(41.8902, 12.4922), (41.8853, 12.4851)], (41.8878, 12.4886)),  # Rome
])
def test_agent_accepts_local_candidates_and_rejects_repeated_london_business(
    points: list[tuple[float, float]],
    local_candidate: tuple[float, float],
) -> None:
    journey = route(points)
    local = candidate("local-cafe", *local_candidate)
    cafe_pedlar = candidate("cafe-pedlar", 51.4620, -0.0670)

    recommendations = RouteDiscoveryAgent().recommend(
        journey,
        [cafe_pedlar, local],
        target_fraction=0.5,
    )

    assert [place.place_id for place in recommendations] == ["local-cafe"]


@pytest.mark.parametrize(("locale", "expected"), [
    ("en-GB", "No requested facilities could be verified"),
    ("fr-FR", "Aucun établissement demandé n'a pu être vérifié"),
    ("es-ES", "No se pudo verificar ningún lugar solicitado"),
    ("it-IT", "Non è stato possibile verificare alcun luogo richiesto"),
])
def test_agent_localizes_honest_empty_results(locale: str, expected: str) -> None:
    assert expected in RouteDiscoveryAgent().empty_result_message(locale)


@pytest.mark.parametrize("prompt", [
    "Find a cafe near the finish",
    "Trouve un café près de l'arrivée",
    "Busca una cafetería cerca del destino",
    "Trova un caffè vicino all'arrivo",
])
def test_agent_understands_supported_near_finish_phrasing(prompt: str) -> None:
    assert RouteDiscoveryAgent().target_fraction(prompt) == 0.85
