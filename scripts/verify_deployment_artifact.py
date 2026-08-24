from __future__ import annotations

import json
import sys

from apps.api.app.artifacts import verify_deployment_artifact
from apps.api.app.config import PROJECT_ROOT


if __name__ == "__main__":
    result = verify_deployment_artifact(PROJECT_ROOT)
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "ready" else 1)
