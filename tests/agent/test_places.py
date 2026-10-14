from __future__ import annotations

import asyncio

import httpx

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
    resolve_place_from_payload,
    _structured_payload,
)
from apps.api.app.agent.errors import ProviderOperationError, ProviderPayloadError, classify_provider_exception, contains_cancellation


CELL = "892a100d2d7ffff"


def test_provider_diagnostics_classify_http_statuses_without_copying_payloads() -> None:
    request = httpx.Request("POST", "https://mapstools.googleapis.com/mcp")
    for status, category in ((401, "authentication"), (403, "permission"), (429, "quota_or_rate_limit"), (500, "upstream_5xx"), (502, "upstream_5xx"), (503, "upstream_5xx")):
        error = httpx.HTTPStatusError("secret=must-not-escape", request=request, response=httpx.Response(status, request=request))
        diagnostic = classify_provider_exception(error)
        assert diagnostic.category == category
        assert diagnostic.http_status == status
        assert diagnostic.response_received is True


def test_provider_diagnostics_classify_transport_timeout_cancellation_and_payload() -> None:
    request = httpx.Request("POST", "https://mapstools.googleapis.com/mcp")
    assert classify_provider_exception(httpx.ConnectError("api-key=secret", request=request)).category == "transport"
    assert classify_provider_exception(httpx.ReadTimeout("timed out", request=request)).category == "timeout"
    assert classify_provider_exception(asyncio.CancelledError()).category == "transport"
    assert classify_provider_exception(ProviderPayloadError("Google Maps")).category == "invalid_response"
    assert classify_provider_exception(ProviderPayloadError("Google Maps", reason_code="places_empty")).category == "no_match"
    assert classify_provider_exception(ProviderOperationError("Google Maps")).reason_code == "tool_error"
    assert classify_provider_exception(ProviderOperationError("Google Maps")).response_received is True
    assert contains_cancellation(BaseExceptionGroup("cancelled", [asyncio.CancelledError()])) is True


def test_provider_diagnostics_unwrap_nested_exception_groups_and_unknowns() -> None:
    request = httpx.Request("POST", "https://mapstools.googleapis.com/mcp")
    nested = ExceptionGroup("mcp failure", [RuntimeError("token=secret"), ExceptionGroup("upstream", [httpx.HTTPStatusError("forbidden", request=request, response=httpx.Response(403, request=request))])])
    diagnostic = classify_provider_exception(nested)
    assert diagnostic.category == "permission"
    assert diagnostic.http_status == 403
    assert classify_provider_exception(ValueError("coordinates=51.5,-0.1")).category == "unknown"
    invalid_status = classify_provider_exception(httpx.HTTPStatusError("invalid", request=request, response=httpx.Response(600, request=request)))
    assert invalid_status.category == "unknown"
    assert invalid_status.http_status is None


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


def test_google_search_arguments_localize_provider_results_without_changing_geometry() -> None:
    arguments = google_search_arguments("cafe", CELL, "rome", "it-IT")

    assert arguments["language_code"] == "it"
    assert arguments["region_code"] == "IT"
    assert arguments["location_bias"]["circle"]["radius_meters"] == MAX_SEARCH_RADIUS_M


def test_maps_client_uses_server_credential_and_official_endpoint_defaults() -> None:
    client = GoogleMapsGroundingClient(api_key="server-only-test-key")

    assert client.url == "https://mapstools.googleapis.com/mcp"
    assert client.api_key == "server-only-test-key"
    assert client.timeout_s == 20.0


def test_structured_payload_accepts_direct_and_result_wrapped_objects() -> None:
    class Result:
        def __init__(self, structured):
            self.structuredContent = structured
            self.content = []

    payload = {"places": []}
    assert _structured_payload(Result(payload)) == payload
    assert _structured_payload(Result({"result": payload})) == payload


def test_structured_payload_classifies_missing_invalid_and_unexpected_content() -> None:
    class Content:
        def __init__(self, text):
            self.text = text

    class Result:
        def __init__(self, structured=None, content=None):
            self.structuredContent = structured
            self.content = content or []

    for result, reason in (
        (Result(content=[]), "structured_content_missing"),
        (Result(structured=[]), "structured_wrapper_invalid"),
        (Result(content=[Content("not-json")]), "json_content_invalid"),
        (Result(content=[Content("[]")]), "json_content_invalid"),
    ):
        try:
            _structured_payload(result)
        except ProviderPayloadError as exc:
            assert exc.reason_code == reason
        else:
            raise AssertionError(f"expected {reason}")


def test_endpoint_resolution_distinguishes_empty_results() -> None:
    try:
        resolve_place_from_payload({"places": []}, "King's Cross", "london")
    except ProviderPayloadError as exc:
        assert exc.reason_code == "places_empty"
    else:
        raise AssertionError("empty results should not be treated as malformed")


def test_endpoint_resolution_skips_incomplete_first_candidate_for_valid_later_candidate() -> None:
    resolved = resolve_place_from_payload({"places": [
        {"id": "incomplete", "displayName": "Incomplete result"},
        {"id": "valid", "displayName": "King's Cross", "location": {"latitude": 51.5308, "longitude": -0.1238}},
    ]}, "King's Cross", "london")

    assert resolved.place_id == "valid"
    assert resolved.latitude == 51.5308


def test_endpoint_resolution_does_not_substitute_unrelated_later_candidate() -> None:
    try:
        resolve_place_from_payload({"places": [
            {"id": "incomplete"},
            {"id": "unrelated", "displayName": "Café Pedlar", "location": {"latitude": 51.5308, "longitude": -0.1238}},
        ]}, "King's Cross", "london")
    except ProviderPayloadError as exc:
        assert exc.reason_code == "candidate_not_relevant"
    else:
        raise AssertionError("unrelated candidate should not replace the requested endpoint")


def test_endpoint_resolution_does_not_match_on_city_name_only() -> None:
    try:
        resolve_place_from_payload({"places": [
            {"id": "unrelated", "displayName": "London Cafe", "location": {"latitude": 51.5308, "longitude": -0.1238}},
        ]}, "London", "london")
    except ProviderPayloadError as exc:
        assert exc.reason_code == "candidate_not_relevant"
    else:
        raise AssertionError("city name alone must not authorize an unrelated place")


def test_endpoint_resolution_rejects_out_of_city_candidates_without_substitution() -> None:
    try:
        resolve_place_from_payload({"places": [{"id": "chicago", "location": {"latitude": 41.88, "longitude": -87.63}}]}, "King's Cross", "london")
    except ProviderPayloadError as exc:
        assert exc.reason_code == "candidate_outside_city"
    else:
        raise AssertionError("outside-city candidate should be rejected")


def test_endpoint_resolution_requires_verified_id_and_finite_geometry() -> None:
    try:
        resolve_place_from_payload({"places": [
            {"location": {"latitude": 51.5, "longitude": -0.1}},
            {"id": "nan", "location": {"latitude": float("nan"), "longitude": -0.1}},
        ]}, "King's Cross", "london")
    except ProviderPayloadError as exc:
        assert exc.reason_code == "invalid_candidate_geometry"
    else:
        raise AssertionError("unverified candidate should be rejected")


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


def test_google_result_parser_discards_places_without_trusted_coordinates() -> None:
    parsed = parse_search_result({"places": [
        {"id": "missing-location", "displayName": "Unknown Cafe"},
        {"id": "missing-longitude", "location": {"latitude": 51.5}},
    ]}, "cafe", CELL)

    assert parsed.places == []


def test_google_result_parser_discards_untrusted_place_links() -> None:
    parsed = parse_search_result({"places": [{
        "id": "abc", "location": {"latitude": 51.5, "longitude": -0.1},
        "googleMapsLinks": {"placeUrl": "javascript:alert(1)"},
        "attribution": {"title": "Example Cafe", "url": "https://attacker.example/redirect"},
    }]}, "cafe", CELL)

    assert parsed.places[0].maps_uri is None
    assert parsed.places[0].attribution_url is None


def test_google_result_parser_keeps_script_payloads_as_inert_text_only() -> None:
    parsed = parse_search_result({"places": [{
        "id": "abc", "name": "<script>alert(1)</script>",
        "location": {"latitude": 51.5, "longitude": -0.1},
    }]}, "cafe", CELL)

    assert parsed.places[0].name == "<script>alert(1)</script>"
    assert parsed.places[0].maps_uri is None


def test_deterministic_amenity_analysis_ranks_raw_counts_without_composite_score() -> None:
    result = MapsSearchResult.model_validate({"places": [{
        "place_id": "abc", "latitude": 51.5, "longitude": -0.1, "category": "cafe", "h3_cell": CELL,
    }]})
    rows = deterministic_amenity_analysis([CELL, "892a100d2dfffff"], ["cafe"], {CELL: 100, "892a100d2dfffff": 90}, {(CELL, "cafe"): result})

    assert rows[0]["h3_cell"] == CELL
    assert rows[0]["place_count"] == 1
    assert rows[1]["place_count"] == 0
    assert "opportunity_score" not in rows[0]
