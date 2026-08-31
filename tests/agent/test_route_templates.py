from apps.api.app.agent.route_templates import match_route_templates


def test_fulham_to_richmond_matches_curated_template():
    matches = match_route_templates("Fulham", "Richmond Park", ["scenic", "quiet"], ["cafe", "public_bathroom"])
    assert matches
    assert matches[0].template_id == "fulham-richmond-park"
    assert "Curated" not in matches[0].name


def test_unmatched_city_names_do_not_match_london_templates():
    assert match_route_templates("Central Park", "Brooklyn", ["scenic"], ["cafe"]) == []


def test_matcher_returns_at_most_two_templates():
    assert len(match_route_templates("Fulham", "Richmond", ["scenic", "quiet"], ["cafe", "restaurant"])) <= 2


def test_named_london_corridors_match_their_templates():
    cases = [
        ("Greenwich", "Cutty Sark", "greenwich-park-thames"),
        ("Wimbledon", "Wandsworth", "wandle-trail"),
        ("Hackney", "Lee Valley", "lee-valley"),
        ("Leytonstone", "Epping Forest", "epping-forest"),
        ("Little Venice", "Victoria Park", "regents-canal-loop"),
        ("Hyde Park", "Regent's Park", "parks-greenway"),
    ]
    for origin, destination, template_id in cases:
        assert any(item.template_id == template_id for item in match_route_templates(origin, destination, ["scenic"], ["cafe"]))


def test_route_libraries_extend_to_route_capable_cities():
    assert match_route_templates("Chelsea", "Inwood", ["scenic"], ["cafe"], city="new_york")[0].template_id == "hudson-greenway"
    assert match_route_templates("Lincoln Park", "Hyde Park", ["scenic"], ["cafe"], city="chicago")[0].template_id == "chicago-lakefront"
    assert any(item.template_id == "capital-crescent" for item in match_route_templates("Georgetown", "Bethesda", ["quiet"], ["cafe"], city="washington_dc"))
    assert match_route_templates("Fulham", "Richmond Park", ["scenic"], ["cafe"], city="paris") == []


def test_european_route_libraries_are_city_scoped():
    assert any(item.template_id == "copenhagen-harbour" for item in match_route_templates("Nyhavn", "Amager Strand", ["scenic"], ["cafe"], city="copenhagen"))
    assert match_route_templates("Barceloneta", "Port Olimpic", ["scenic"], ["cafe"], city="barcelona")[0].template_id == "barcelona-waterfront"
    assert match_route_templates("Centro", "Madrid Río", ["scenic"], ["cafe"], city="madrid")


def test_each_route_capable_city_has_a_full_selection():
    from apps.api.app.agent.route_templates import CITY_ROUTE_TEMPLATES
    counts = {city: sum(template.city == city for template in CITY_ROUTE_TEMPLATES) for city in ("london", "new_york", "chicago", "washington_dc", "paris", "copenhagen", "barcelona", "madrid")}
    assert all(count >= 15 for count in counts.values()), counts
