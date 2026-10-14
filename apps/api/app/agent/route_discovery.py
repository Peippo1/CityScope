from __future__ import annotations

from .route_service import RouteDetails, route_search_points, select_route_places
from .schemas import PlaceResult


_NEAR_FINISH_TERMS = (
    "near the finish",
    "near the destination",
    "at the end",
    "près de l'arrivée",
    "près de la destination",
    "cerca del destino",
    "cerca del final",
    "vicino all'arrivo",
    "vicino alla destinazione",
)

_EMPTY_RESULT_MESSAGES = {
    "en-GB": "No requested facilities could be verified near this route within the bounded search.",
    "fr-FR": "Aucun établissement demandé n'a pu être vérifié à proximité de cet itinéraire dans la zone de recherche limitée.",
    "es-ES": "No se pudo verificar ningún lugar solicitado cerca de esta ruta dentro del área de búsqueda limitada.",
    "it-IT": "Non è stato possibile verificare alcun luogo richiesto vicino a questo percorso nell'area di ricerca limitata.",
}


class RouteDiscoveryAgent:
    """Deterministically discovers optional places around verified route geometry.

    Provider place data is treated as untrusted: only candidates with validated
    coordinates inside the route corridor can become recommendations. This
    component never changes route waypoints and does not invoke a model.
    """

    max_search_points = 2
    max_recommendations = 3

    def target_fraction(self, request: str) -> float:
        lowered = request.casefold()
        return 0.85 if any(term in lowered for term in _NEAR_FINISH_TERMS) else 0.5

    def search_points(self, route: RouteDetails, target_fraction: float) -> list[tuple[float, float]]:
        return route_search_points(route, target_fraction, limit=self.max_search_points)

    def recommend(
        self,
        route: RouteDetails,
        candidates: list[PlaceResult],
        *,
        target_fraction: float,
    ) -> list[PlaceResult]:
        return select_route_places(
            route,
            candidates,
            target_fraction,
            limit=self.max_recommendations,
        )

    def empty_result_message(self, locale: str) -> str:
        return _EMPTY_RESULT_MESSAGES.get(locale, _EMPTY_RESULT_MESSAGES["en-GB"])
