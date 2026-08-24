from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_deployment_artifact(root: Path) -> dict[str, str]:
    """Validate only the generated deployment artifact; raw TfL inputs are never needed at runtime."""
    metadata_path = root / "data" / "metadata" / "london-cycling-production.json"
    if not metadata_path.exists():
        return {"status": "invalid", "reason": "production metadata is unavailable"}
    try:
        metadata = json.loads(metadata_path.read_text())
        artifacts = metadata["generated_artifacts"]
        activity = root / "data" / "generated" / artifacts["activity"]
        journeys = root / "data" / "generated" / artifacts["journeys"]
        if not activity.exists() or not journeys.exists():
            return {"status": "invalid", "reason": "generated dataset artifacts are unavailable"}
        if _sha256(activity) != metadata["generated_artifact_version"]:
            return {"status": "invalid", "reason": "activity artifact checksum does not match provenance metadata"}
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        return {"status": "invalid", "reason": "production provenance metadata is invalid"}
    return {"status": "ready", "dataset": "production"}
