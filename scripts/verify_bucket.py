"""
One-off verification script: confirms the actual contents and schemas of the challenge's public
data bucket, ahead of building the coverage-gap pipeline. Not part of the pipeline itself.

Checks:
  1. Full file listing for one region's reference/ folder (real listing, not the README's summary).
  2. A search across all four regions' reference/ folders for anything "gap"/"coverage"/"score"
     shaped, to settle whether an answer-key-style file is actually shipped.
  3. Real column schemas (names + dtypes) for the layers the coverage-gap pipeline will need,
     read from the parquet footer only (no full download).
  4. Real Overture `categories.primary` values sampled from one region's POI layer, to check
     against the README's documented facility category strings.
  5. The real sample-submission.csv columns and GEOID dtype, straight from the bucket.

Run with: python scripts/verify_bucket.py
"""

from __future__ import annotations

import io

import boto3
from botocore import UNSIGNED
from botocore.config import Config
import pyarrow.parquet as pq
from pyarrow.fs import S3FileSystem
import pandas as pd

BUCKET = "us-west-2.opendata.source.coop"
ROOT = "humane-intelligence/bias-bounty-mapping-equity-challenge"
REGIONS = ["maricopa-az", "northern-ca", "eastern-ok", "south-central-tx"]
CHECK_REGION = "eastern-ok"

s3 = boto3.client("s3", region_name="us-west-2", config=Config(signature_version=UNSIGNED))
fs = S3FileSystem(anonymous=True, region="us-west-2")


def list_prefix(prefix: str) -> list[dict]:
    out, token = [], None
    while True:
        kwargs = {"Bucket": BUCKET, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        out.extend(resp.get("Contents", []))
        if not resp.get("IsTruncated"):
            break
        token = resp["NextContinuationToken"]
    return out


def schema_of(key: str) -> None:
    path = f"{BUCKET}/{key}"
    try:
        pf = pq.ParquetFile(path, filesystem=fs)
        print(f"\n--- {key} ---")
        print(f"  rows: {pf.metadata.num_rows:,}   row_groups: {pf.metadata.num_row_groups}")
        for field in pf.schema_arrow:
            print(f"  {field.name:<28} {field.type}")
    except Exception as exc:
        print(f"\n--- {key} ---\n  ERROR: {type(exc).__name__}: {exc}")


print("=" * 90)
print(f"1) Full listing: reference/{CHECK_REGION}/")
print("=" * 90)
objs = list_prefix(f"{ROOT}/reference/{CHECK_REGION}/")
for o in sorted(objs, key=lambda x: x["Key"]):
    size_mb = o["Size"] / 1_048_576
    print(f"  {size_mb:>9,.2f} MB   {o['Key'].split('/')[-1]}")
print(f"  ({len(objs)} objects total)")

print()
print("=" * 90)
print("2) Searching ALL regions' reference/ folders for anything gap/coverage/score-shaped")
print("=" * 90)
suspicious_terms = ("gap", "coverage", "score", "answer", "solution", "target", "label")
found_any = False
for region in REGIONS:
    region_objs = list_prefix(f"{ROOT}/reference/{region}/")
    hits = [o["Key"] for o in region_objs if any(t in o["Key"].lower() for t in suspicious_terms)]
    print(f"  {region}: {len(hits)} matching file(s)")
    for h in hits:
        print(f"    -> {h}")
        found_any = True
if not found_any:
    print("  No answer-key-shaped files found in any region's reference/ folder.")

print()
print("=" * 90)
print("3) Real schemas of the layers the pipeline needs (footer-only read, no full download)")
print("=" * 90)
for layer in [
    "overture-buildings", "overture-roads", "overture-pois",
    "microsoft-buildings", "census-tiger-roads", "census-cbp",
    "hifld-fire-stations", "hifld-ems-stations", "hifld-schools", "hifld-hospitals",
]:
    schema_of(f"{ROOT}/reference/{CHECK_REGION}/{CHECK_REGION}-{layer}.parquet")

print()
print("=" * 90)
print(f"4) Real Overture categories.primary values sampled from {CHECK_REGION}-overture-pois")
print("=" * 90)
try:
    pf = pq.ParquetFile(f"{BUCKET}/{ROOT}/reference/{CHECK_REGION}/{CHECK_REGION}-overture-pois.parquet", filesystem=fs)
    batch = next(pf.iter_batches(batch_size=200_000, columns=["categories"]))
    cats = pd.array(batch.column("categories").to_pylist())
    primaries = pd.Series([c["primary"] if c else None for c in cats])
    vc = primaries.value_counts()
    facility_terms = ("fire", "ambulance", "ems", "school", "hospital")
    matches = vc[vc.index.to_series().fillna("").str.contains("|".join(facility_terms), case=False)]
    print("  Category values containing fire/ambulance/ems/school/hospital:")
    print(matches.to_string())
except Exception as exc:
    print(f"  ERROR: {type(exc).__name__}: {exc}")

print()
print("=" * 90)
print("5) Real sample-submission.csv columns and GEOID dtype, straight from the bucket")
print("=" * 90)
try:
    obj = s3.get_object(Bucket=BUCKET, Key=f"{ROOT}/reference/{CHECK_REGION}/{CHECK_REGION}-sample-submission.csv")
    df = pd.read_csv(io.BytesIO(obj["Body"].read()), dtype=str)
    print(f"  shape: {df.shape}")
    print(f"  columns: {list(df.columns)}")
    print(f"  GEOID sample: {df['GEOID'].iloc[0]!r}  (length {df['GEOID'].str.len().iloc[0]})")
except Exception as exc:
    print(f"  ERROR: {type(exc).__name__}: {exc}")

print()
print("Done.")
