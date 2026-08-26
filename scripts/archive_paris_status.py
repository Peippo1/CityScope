"""Cloud Run job entry point for hourly, private Paris GBFS archive snapshots."""
from __future__ import annotations

import gzip
import json
import os
from datetime import UTC, datetime

from services.city_live_data_mcp.tools import VelibClient


async def archive() -> str:
    bucket_name = os.getenv("CITYSCOPE_PARIS_ARCHIVE_BUCKET")
    if not bucket_name:
        raise RuntimeError("CITYSCOPE_PARIS_ARCHIVE_BUCKET is required")
    result = await VelibClient().get_status(limit=100)
    timestamp = datetime.now(UTC)
    object_name = f"paris-velib/year={timestamp:%Y}/month={timestamp:%m}/day={timestamp:%d}/hour={timestamp:%H}/status.json.gz"
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("google-cloud-storage is required for archival jobs") from exc
    payload = gzip.compress(result.model_dump_json().encode("utf-8"))
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    blob.upload_from_string(payload, content_type="application/gzip")
    return object_name


if __name__ == "__main__":
    import asyncio
    print(asyncio.run(archive()))
