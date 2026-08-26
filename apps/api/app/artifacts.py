from __future__ import annotations

import hashlib
import json
from pathlib import Path


HISTORICAL_COHORT = ("london", "new_york", "chicago", "washington_dc")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_deployment_artifact(root: Path) -> dict[str, str]:
    """Validate the complete generated cohort; raw source files are never needed at runtime."""
    for city in HISTORICAL_COHORT:
        metadata_path = root / "data" / "metadata" / f"{city}-cycling-production.json"
        if not metadata_path.exists():
            return {"status": "invalid", "reason": f"production metadata is unavailable for {city}"}
        try:
            metadata = json.loads(metadata_path.read_text())
            artifacts = metadata["generated_artifacts"]
            journeys = root / "data" / "generated" / artifacts["journeys"]
            checksum_target = root / "data" / "generated" / artifacts.get("activity", artifacts["journeys"])
            if not journeys.exists() or not checksum_target.exists():
                return {"status": "invalid", "reason": f"generated dataset artifacts are unavailable for {city}"}
            if _sha256(checksum_target) != metadata["generated_artifact_version"]:
                return {"status": "invalid", "reason": f"artifact checksum does not match provenance metadata for {city}"}
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            return {"status": "invalid", "reason": f"production provenance metadata is invalid for {city}"}
    return {"status": "ready", "dataset": "production", "cohort": ",".join(HISTORICAL_COHORT)}
