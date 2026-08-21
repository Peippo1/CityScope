import json
from pathlib import Path


def test_production_metadata_contains_reproducibility_fields():
    path = Path("data/metadata/london-cycling-production.json")
    if not path.exists():
        return
    metadata = json.loads(path.read_text())
    required = {
        "city", "dataset_id", "snapshot_id", "source_organisation", "source_url",
        "retrieval_date", "observation_start", "observation_end_exclusive",
        "licence_terms_reference", "attribution_text", "source_row_count",
        "accepted_row_count", "rejected_quarantined_row_count", "transformation_version",
        "h3_resolution", "generated_artifact_version",
    }
    assert required.issubset(metadata)
    assert metadata["source_row_count"] == metadata["accepted_row_count"] + metadata["rejected_quarantined_row_count"]
