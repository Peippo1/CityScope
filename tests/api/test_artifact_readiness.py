import json

from apps.api.app.artifacts import HISTORICAL_COHORT, verify_deployment_artifact


def test_production_artifact_readiness_verifies_manifest_checksum(tmp_path):
    metadata_dir = tmp_path / "data" / "metadata"
    generated_dir = tmp_path / "data" / "generated"
    metadata_dir.mkdir(parents=True)
    generated_dir.mkdir()
    activity = generated_dir / "london_cycling_activity.parquet"
    journeys = generated_dir / "london_cycling_production_journeys.parquet"
    activity.write_bytes(b"activity")
    journeys.write_bytes(b"journeys")

    from hashlib import sha256
    for city in HISTORICAL_COHORT:
        city_journeys = journeys if city == "london" else generated_dir / f"{city}_cycling_production_journeys.parquet"
        city_journeys.write_bytes(b"journeys")
        generated_artifacts = {"journeys": city_journeys.name}
        checksum_target = city_journeys
        if city == "london":
            generated_artifacts["activity"] = activity.name
            checksum_target = activity
        (metadata_dir / f"{city}-cycling-production.json").write_text(json.dumps({
            "generated_artifacts": generated_artifacts,
            "generated_artifact_version": sha256(checksum_target.read_bytes()).hexdigest(),
        }))

    assert verify_deployment_artifact(tmp_path)["status"] == "ready"

    activity.write_bytes(b"tampered")
    assert verify_deployment_artifact(tmp_path)["status"] == "invalid"
