"""
scripts/build_data_manifest.py — Stage 1 (Data acquisition & governance).

Lists every object in the challenge's public bucket the pipeline will ever touch — every study
region's `reference/` and `strata/` folders, the national `strata/national/` table, and
`boundaries/` — and records its key, size, ETag, and last-modified timestamp.

This is deliberately NOT a schema/validation pass — it doesn't open a single file, only lists what
exists and how big it is. Schema contracts, null coverage, geometry validity, and CRS consistency
are Stage 2's job (`scripts/audit/audit_bucket.py`). This script's only job is answering "did the
upstream data change under us, and what does the full object inventory look like" cheaply and
repeatably — not full DVC-style data versioning, which would be overkill for a fixed, read-only
public bucket.

Uses obstore (already in requirements.txt) for anonymous S3 listing, not boto3 — consistent with
this project's chosen access-library set. (`scripts/verify_bucket.py`, kept as-is as a record of
early exploratory work, used boto3; that dependency gap is tracked to be resolved when Stage 2
generalizes it into `scripts/audit/audit_bucket.py`, not fixed retroactively here.)

Run with: python scripts/build_data_manifest.py
Writes: docs/data_manifest.csv — committed. It lives under docs/, not data/, so it is NOT swept up
by the repo's blanket `data/` gitignore rule; it's small (one row per bucket object, a few hundred
rows total) and is exactly the kind of lightweight, human- and machine-readable governance artifact
worth keeping under version control.
"""

from __future__ import annotations

import sys
from pathlib import Path

import obstore
import obstore.store as obstore_store
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import REGIONS, ROOT, S3_BUCKET, S3_REGION  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "docs" / "data_manifest.csv"


def list_prefix(s3: obstore_store.S3Store, prefix: str) -> list[dict]:
    """Flattens obstore.list()'s paginated chunks into a single list of object-metadata dicts."""
    objects: list[dict] = []
    for chunk in obstore.list(s3, prefix=prefix):
        objects.extend(chunk)
    return objects


def build_prefixes() -> list[str]:
    prefixes = [f"{ROOT}/strata/national/", f"{ROOT}/boundaries/"]
    for region in REGIONS:
        prefixes.append(f"{ROOT}/reference/{region}/")
        prefixes.append(f"{ROOT}/strata/{region}/")
    return prefixes


def main() -> int:
    s3 = obstore_store.S3Store.from_url(
        f"s3://{S3_BUCKET}",
        region=S3_REGION,
        skip_signature=True,
    )

    rows: list[dict] = []
    for prefix in build_prefixes():
        print(f"Listing {prefix} ...")
        objects = list_prefix(s3, prefix)
        print(f"  {len(objects)} objects")
        for obj in objects:
            rows.append(
                {
                    "key": obj["path"],
                    "size_bytes": obj["size"],
                    "e_tag": obj["e_tag"],
                    "last_modified": obj["last_modified"],
                }
            )

    if not rows:
        print(
            "ERROR: zero objects found across every prefix listed — this almost certainly means "
            "the bucket/region/prefix is wrong or network access to S3 failed silently. Nothing "
            "was written.",
            file=sys.stderr,
        )
        return 1

    manifest = pd.DataFrame(rows).sort_values("key").reset_index(drop=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(OUTPUT_PATH, index=False)

    print(f"\nWrote {len(manifest)} objects to {OUTPUT_PATH}")
    print(f"Total size across every listed object: {manifest['size_bytes'].sum() / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
