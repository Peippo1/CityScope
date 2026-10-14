import asyncio

from apps.api.app.agent.schemas import InvestigationRequest
from apps.api.app.agent.places import MapsSearchResult
from apps.api.app.agent.route_service import ResolvedPlace, RouteDetails
from apps.api.app.agent.service import InvestigationService


class UnavailableModel:
    async def decide(self, question: str, context: str, tool_results: list[dict]):
        raise RuntimeError("model unavailable")


class Maps:
    async def resolve_location(self, query: str, city: str = "london", locale: str | None = None) -> ResolvedPlace:
        points = {
            "Place de la République": (48.867, 2.363),
            "Bastille": (48.853, 2.369),
        }
        latitude, longitude = points[query]
        return ResolvedPlace(name=query, place_id=f"place-{query}", latitude=latitude, longitude=longitude)

    async def search_places(self, category: str, cell: str, city: str = "london", locale: str | None = None) -> MapsSearchResult:
        return MapsSearchResult(places=[])


class Routes:
    async def compute_bicycle_route(self, origin, destination, waypoints):
        return RouteDetails(distance_m=1700, duration_seconds=420, polyline="route", origin=origin, destination=destination, waypoints=waypoints)

    async def compute_walking_route(self, origin, destination, waypoints):
        return RouteDetails(travel_mode="walking", distance_m=1700, duration_seconds=420, polyline="route", origin=origin, destination=destination, waypoints=waypoints)


def test_structured_french_route_context_survives_model_unavailability() -> None:
    request = InvestigationRequest(
        city="paris",
        question="Planifie un itinéraire à vélo.",
        context={
            "activity": "cycling",
            "locale": "fr-FR",
            "start_location": "Place de la République",
            "destination": "Bastille",
        },
    )
    service = InvestigationService(model=UnavailableModel(), maps_client=Maps(), route_service=Routes())

    # The fallback is reached before any provider client is needed; execution
    # of the resulting route remains owned by the normal deterministic path.
    result = asyncio.run(service.investigate(request))

    assert result.status == "answered"
    assert result.route is not None
    assert result.route.travel_mode == "bicycle"
    assert result.route.origin.name == "Place de la République"
    assert result.route.destination.name == "Bastille"
    assert result.answer.startswith("L’itinéraire bicycle validé")
