from apps.api.app.cities import get_city


def test_rome_is_route_enabled_without_historical_dataset_claims() -> None:
    rome = get_city("rome")

    assert rome.routes is True
    assert rome.historical is False
    assert rome.region_code == "IT"
