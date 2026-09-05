"""
scripts/inspect_overture_sources.py — Stage 2, Step 1.

Confirms the real structure and value set of Overture's `sources` field before Stage 6 builds a
source-provenance feature (`source_entropy` and similar) against it. Only eastern-ok has been
directly checked so far — confirmed as a list of structs, each carrying its own `confidence`,
distinct from `overture-pois` where `confidence` is a flat top-level column instead. This script
closes that gap properly:

  1. The exact Arrow struct field names/types inside `sources`, for `overture-buildings` and
     `overture-roads`, in EVERY region — confirming schema consistency across regions, not
     assuming eastern-ok's shape holds everywhere.
  2. The real `dataset` value set inside `sources`, sampled per region and per layer — which
     upstream sources (OpenStreetMap, Microsoft ML Buildings, Google Open Buildings, esri Community
     Maps, etc.) actually appear, and how often — since this directly determines what a
     provenance-based feature can distinguish between regions/tracts.

Scoped to `overture-buildings` and `overture-roads` only, not every Overture layer — those are the
two layers Stage 6's building-gap and transport-gap features (and any source-provenance feature
built on top of them) actually depend on; `overture-pois` already has a directly-confirmed,
structurally different `sources`/`confidence` shape and isn't part of this gap.

Uses pyarrow.fs.S3FileSystem (anonymous) — not boto3 — consistent with this project's access
libraries; no dependency on src.config beyond REGIONS/ROOT/S3_BUCKET/S3_REGION (read-only schema
inspection, not the full audit).

Run with: python scripts/inspect_overture_sources.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow.fs import FileSystem, S3FileSystem

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import REGIONS, ROOT, S3_BUCKET, S3_REGION  # noqa: E402

LAYERS = ["overture-buildings", "overture-roads"]
SAMPLE_ROWS = 100_000


def struct_field_signature(sources_field: pa.Field) -> tuple[str, ...]:
    """Reduces a `sources: list<struct<...>>` Arrow field to a stable (name:type, ...) signature
    so two regions' schemas can be compared for exact equality, not just eyeballed.

    Accepts both `list<...>` and `large_list<...>` — the 8 real region/layer combinations checked
    all used the regular `list` type, but `large_list` is a legitimate Arrow encoding for the same
    logical type (used for very large columns) and this check should not misreport a schema as
    inconsistent purely because of that encoding choice."""
    list_type = sources_field.type
    if not (pa.types.is_list(list_type) or pa.types.is_large_list(list_type)):
        return (f"NOT-A-LIST:{list_type}",)
    struct_type = list_type.value_type
    if not pa.types.is_struct(struct_type):
        return (f"LIST-BUT-NOT-STRUCT:{struct_type}",)
    return tuple(f"{struct_type.field(i).name}:{struct_type.field(i).type}" for i in range(struct_type.num_fields))


def inspect_sources_at_path(filesystem: FileSystem, path: str, *, label: str = "") -> dict:
    """Core inspection logic, factored out of inspect_layer() so it's directly testable against a
    local fixture file/filesystem without needing S3_BUCKET/ROOT path construction or network
    access — inspect_layer() is a thin wrapper that builds the real bucket path and calls this."""
    result: dict = {"label": label}

    try:
        pf = pq.ParquetFile(path, filesystem=filesystem)
    except Exception as exc:  # noqa: BLE001 — surfacing the failure is the point here
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    schema = pf.schema_arrow
    if "sources" not in schema.names:
        result["error"] = f"no 'sources' column in schema — columns present: {schema.names}"
        return result

    sources_field = schema.field("sources")
    result["arrow_type"] = str(sources_field.type)
    result["struct_signature"] = struct_field_signature(sources_field)
    result["num_rows_total"] = pf.metadata.num_rows

    dataset_counts: Counter[str] = Counter()
    elements_per_row: list[int] = []
    rows_seen = 0
    if pf.metadata.num_rows > 0:
        # pyarrow's iter_batches raises ValueError for batch_size=0, which min(SAMPLE_ROWS, 0)
        # would produce for a genuinely empty layer — guarded here so an empty region/layer is
        # reported as "0 rows sampled" rather than crashing the whole inspection run. Not a
        # theoretical concern for this project specifically: south-central-tx is already
        # confirmed (docs/data_manifest.md) to be missing a file other regions have, so
        # unexpectedly-empty or missing layers are a real class of issue in this bucket, not a
        # hypothetical one.
        for batch in pf.iter_batches(
            batch_size=min(SAMPLE_ROWS, pf.metadata.num_rows), columns=["sources"]
        ):
            col = batch.column("sources").to_pylist()
            for row in col:
                rows_seen += 1
                if row is None:
                    elements_per_row.append(0)
                    continue
                elements_per_row.append(len(row))
                for element in row:
                    if element is None:
                        continue
                    dataset_counts[element.get("dataset", "<no 'dataset' field>")] += 1
            break  # one batch is our SAMPLE_ROWS-sized sample; no need to read the whole layer

    result["rows_sampled"] = rows_seen
    result["null_sources_rows"] = sum(1 for n in elements_per_row if n == 0)
    result["max_elements_per_row"] = max(elements_per_row) if elements_per_row else 0
    result["dataset_value_counts"] = dataset_counts.most_common()
    return result


def inspect_layer(filesystem: FileSystem, region: str, layer: str) -> dict:
    key = f"{ROOT}/reference/{region}/{region}-{layer}.parquet"
    path = f"{S3_BUCKET}/{key}"
    result = inspect_sources_at_path(filesystem, path, label=f"{region}/{layer}")
    result["region"] = region
    result["layer"] = layer
    result["key"] = key
    return result


def main() -> int:
    filesystem = S3FileSystem(anonymous=True, region=S3_REGION)

    results = []
    for region in REGIONS:
        for layer in LAYERS:
            print(f"Inspecting {region} / {layer} ...")
            r = inspect_layer(filesystem, region, layer)
            results.append(r)
            if "error" in r:
                print(f"  ERROR: {r['error']}")
                continue
            print(f"  arrow type: {r['arrow_type']}")
            print(f"  rows sampled: {r['rows_sampled']:,} of {r['num_rows_total']:,} total")
            print(f"  rows with empty/null sources: {r['null_sources_rows']:,}")
            print(f"  max source elements in one row: {r['max_elements_per_row']}")
            print("  dataset value counts (top 10):")
            for name, count in r["dataset_value_counts"][:10]:
                print(f"    {count:>8,}  {name!r}")

    print("\n" + "=" * 90)
    print("Struct-signature consistency check across all regions/layers")
    print("=" * 90)
    signatures = {
        (r["region"], r["layer"]): r.get("struct_signature") for r in results if "error" not in r
    }
    distinct_signatures = set(signatures.values())
    if len(distinct_signatures) <= 1:
        print("CONSISTENT — every region/layer inspected has the identical struct signature:")
        if distinct_signatures:
            print(f"  {next(iter(distinct_signatures))}")
    else:
        print(f"INCONSISTENT — {len(distinct_signatures)} distinct struct signatures found:")
        for sig in distinct_signatures:
            matching = [f"{region}/{layer}" for (region, layer), s in signatures.items() if s == sig]
            print(f"  {sig}")
            print(f"    -> {', '.join(matching)}")

    errors = [r for r in results if "error" in r]
    if errors:
        print(f"\n{len(errors)} region/layer pair(s) failed to inspect — see ERROR lines above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
