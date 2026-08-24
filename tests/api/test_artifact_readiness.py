import json

from apps.api.app.artifacts import verify_deployment_artifact


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
    (metadata_dir / "london-cycling-production.json").write_text(json.dumps({
        "generated_artifacts": {"activity": activity.name, "journeys": journeys.name},
        "generated_artifact_version": sha256(activity.read_bytes()).hexdigest(),
    }))

    assert verify_deployment_artifact(tmp_path) == {"status": "ready", "dataset": "production"}

    activity.write_bytes(b"tampered")
    assert verify_deployment_artifact(tmp_path)["status"] == "invalid"
