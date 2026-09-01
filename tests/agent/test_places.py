from __future__ import annotations

import asyncio

from apps.api.app.agent.places import (
    MAX_SEARCH_RADIUS_M,
    AmenitySearchPlan,
    google_search_arguments,
    h3_centroid,
    parse_search_result,
    deterministic_amenity_analysis,
    GoogleMapsGroundingClient,
    DEFAULT_CANDIDATE_CELLS,
    DEFAULT_CATEGORIES,
    MAX_CANDIDATE_CELLS,
    MAX_CATEGORIES,
    normalize_amenity_plan,
    MapsSearchResult,
)


CELL = "892a100d2d7ffff"


def test_h3_centroid_and_google_wire_schema_are_deterministic() -> None:
    latitude, longitude = h3_centroid(CELL)
    arguments = google_search_arguments("cafe", CELL)

    assert arguments["text_query"] == "cafes in London, UK"
    assert arguments["location_bias"]["circle"]["center"] == {"latitude": latitude, "longitude": longitude}
    assert arguments["location_bias"]["circle"]["radius_meters"] == MAX_SEARCH_RADIUS_M
    assert arguments["region_code"] == "GB"


def test_google_search_arguments_follow_the_selected_city() -> None:
    arguments = google_search_arguments("cafe", CELL, "chicago")

    assert arguments["text_query"] == "cafes in Chicago, Illinois, USA"
    assert arguments["region_code"] == "US"


def test_maps_client_uses_server_credential_and_official_endpoint_defaults() -> None:
    client = GoogleMapsGroundingClient(api_key="server-only-test-key")

    assert client.url == "https://mapstools.googleapis.com/mcp"
    assert client.api_key == "server-only-test-key"
    assert client.timeout_s == 20.0


def test_amenity_plan_rejects_invalid_categories_and_untrusted_cells() -> None:
    try:
        AmenitySearchPlan(h3_cells=[CELL], categories=["pub"])  # type: ignore[list-item]
    except ValueError:
        pass
    else:
        raise AssertionError("invalid amenity category was accepted")


def test_amenity_defaults_are_small_but_safety_ceilings_remain() -> None:
    assert DEFAULT_CANDIDATE_CELLS == 3
    assert DEFAULT_CATEGORIES == 1
    assert MAX_CANDIDATE_CELLS == 5
    assert MAX_CATEGORIES == 2

    plan = AmenitySearchPlan(h3_cells=[CELL, "89194ad3353ffff", "89194ad3203ffff", "89194ad32cbffff"], categories=["cafe", "coffee_shop"])
    normal = normalize_amenity_plan("Which busy areas have few cafes nearby?", plan)
    explicit = normalize_amenity_plan("Compare cafes and coffee shops across the top five areas", plan)

    assert len(normal.h3_cells) == 3
    assert len(normal.categories) == 1
    assert len(explicit.h3_cells) <= 5
    assert len(explicit.categories) == 2


def test_google_result_parser_keeps_only_provider_identifiers_and_links() -> None:
    parsed = parse_search_result({"summary": "A current result", "places": [{
        "place": "places/abc", "id": "abc", "location": {"latitude": 51.5, "longitude": -0.1},
        "googleMapsLinks": {"placeUrl": "https://maps.google.com/?cid=abc"},
        "attribution": {"title": "Google Maps", "url": "https://maps.google.com"},
    }]}, "cafe", CELL)

    assert parsed.places[0].place_id == "abc"
    assert parsed.places[0].maps_uri == "https://maps.google.com/?cid=abc"
    assert parsed.places[0].name is None
    assert parsed.places[0].h3_cell == CELL


def test_google_result_parser_uses_attribution_title_when_name_is_missing() -> None:
    parsed = parse_search_result({"places": [{
        "id": "abc", "location": {"latitude": 51.5, "longitude": -0.1},
        "attribution": {"title": "Scootercaffe - Google Maps", "url": "https://maps.google.com"},
    }]}, "cafe", CELL)

    assert parsed.places[0].name == "Scootercaffe"


def test_google_result_parser_rejects_places_outside_the_selected_city() -> None:
    payload = {"places": [
        {"id": "chicago", "location": {"latitude": 41.88, "longitude": -87.63}},
        {"id": "london", "location": {"latitude": 51.5, "longitude": -0.1}},
    ]}

    parsed = parse_search_result(payload, "cafe", CELL, "chicago")

    assert [place.place_id for place in parsed.places] == ["chicago"]


def test_deterministic_amenity_analysis_ranks_raw_counts_without_composite_score() -> None:
    result = MapsSearchResult.model_validate({"places": [{
        "place_id": "abc", "latitude": 51.5, "longitude": -0.1, "category": "cafe", "h3_cell": CELL,
    }]})
    rows = deterministic_amenity_analysis([CELL, "892a100d2dfffff"], ["cafe"], {CELL: 100, "892a100d2dfffff": 90}, {(CELL, "cafe"): result})

    assert rows[0]["h3_cell"] == CELL
    assert rows[0]["place_count"] == 1
    assert rows[1]["place_count"] == 0
    assert "opportunity_score" not in rows[0]
