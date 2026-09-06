"""
scripts/check_region_national_schema_consistency.py — Stage 3, Step 7.

Every piece of Stage 3 work so far — the domain map (Step 2), the coverage/null profiling (Step 3),
the vintage confirmation (Step 4), the role/allowed_for_scoring/allowed_for_bias classification
(Step 5), and the candidate_hypotheses tagging (Step 6) — was built by reading columns OF
`national-strata-tract-table`, keyed by column NAME. But the four study regions this project is
actually scored on each ship their own separately-joined strata table
(`strata/<region>/<region>-strata-tract-table.parquet` — confirmed to exist in all four regions'
object listings, `docs/data_manifest.csv`), not a slice of the national one. Every column-name-keyed
governance fact from Steps 2/5/6 (`docs/column_domain_map.csv`, `docs/column_classification.csv`,
`docs/column_candidate_hypotheses.csv`) is silently assumed to transfer unchanged to each region's own
table. This step is the first point this project actually checks that assumption against live data,
rather than continuing to assume it.

**What "schema consistency" means here, precisely.** For each region's `<region>-strata-tract-table`,
compared against the already-committed, live-confirmed national schema
(`docs/national_strata_schema_raw.csv`, `source_table == "national-strata-tract-table"` — re-used
as-is, not re-fetched, since nothing about it needs re-confirming here):

- **Column set**: any column present nationally but missing in a region (a governance fact from
  Steps 2/5/6 that a region-level script literally cannot use for that region — this would matter a
  great deal, e.g. if a coverage_flag needed for Measurement Eligibility Bias were absent from a
  region's own table) — and the reverse, any column present in a region but not nationally (a column
  Steps 2/5/6 never classified at all, invisible to every governance field this project has built).
- **Dtype**: for every column present in both, whether the Arrow dtype matches. A silent dtype
  drift (e.g. a boolean `_covered` flag arriving as `int64` in one region) would not necessarily
  crash anything downstream, but could silently corrupt a `==True`/`==False` comparison exactly like
  the ones this project's own coverage-flag logic already depends on (Stage 3 Step 3's `covered_
  flag_consistency` check).
- **Column order**: informational only, not a pass/fail criterion — every one of this project's own
  scripts reads columns by name (`dict(zip(...))`, `.loc[]`, never positional indexing), so a
  reordered-but-otherwise-identical schema is not itself a real risk. Reported anyway, since a
  reordering is sometimes a symptom of a schema having been rebuilt differently, not a coincidence.
- **Row count**: whether each region table's row count matches `src.config.REGION_TRACT_COUNTS`
  (total tract membership, from `boundaries/<region>-tract-geoids.csv`) or
  `src.config.SCORED_TRACT_COUNTS` (the narrower scorable-tract count) — these already differ for
  South-Central Texas specifically (6,010 vs 6,003, Section 4.7/4.8), so this is a live, checkable
  question, not an assumption either way.

**This step needs a live bucket read, unlike Steps 2/5/6.** It queries one new fact per region — the
real schema of a parquet file this project has never inspected before — that is not derivable from
anything already committed. Footer-only (`pq.ParquetFile(...).schema_arrow` / `.metadata.num_rows`),
reusing the exact same core function Stage 3 Step 1 already wrote and tested
(`scripts.inspect_national_strata_schema.inspect_table_schema`) rather than duplicating it — no full
download, safe and cheap to run.

**Scope, stated explicitly rather than left implicit.** This step checks the one artifact every
prior Stage 3 step actually depends on — the pre-joined `<region>-strata-tract-table` — across all
four regions. It deliberately does NOT re-inspect each region's other ~22-23 individual source
tables (the ones the region's own joined table is presumably built from, mirroring
`NATIONAL_STRATA_SOURCE_TABLES`) — that would be a useful future check if this step's result ever
raised a question about HOW a region's joined table was assembled, but is not needed to answer this
step's actual question (does the column-name-keyed governance data from Steps 2/5/6 transfer safely
to each region), which depends only on the joined table's own schema.

Design: testable-core / thin-real-path-wrapper, the same pattern used throughout this project.
`compare_schemas` and `check_row_count` are pure functions, fully unit-tested with no network.
`inspect_region_table` is the one-line network-touching wrapper. `main()` orchestrates, is
non-blocking per region (one region's failure to load must not stop the other three from being
checked, the same reasoning `inspect_national_strata_schema.py`'s per-table isolation already uses),
and writes both a full per-column CSV (audit trail) and a per-region summary CSV.

Run with:
    python -m scripts.check_region_national_schema_consistency

Writes `docs/region_national_schema_consistency.csv` (one row per column per region, covering the
union of national and that region's columns) and `docs/region_national_schema_consistency_summary.
csv` (one row per region: counts of missing/extra/dtype-mismatched columns, order-match, and the
row-count check result).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pyarrow.fs import FileSystem, S3FileSystem

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import (  # noqa: E402
    REGION_TRACT_COUNTS,
    REGIONS,
    S3_REGION,
    SCORED_TRACT_COUNTS,
    STRATA_NATIONAL_JOINED_TABLE,
    STRATA_REGION_JOINED_TABLE,
    strata_s3_path,
)
from scripts.inspect_national_strata_schema import inspect_table_schema  # noqa: E402

DEFAULT_NATIONAL_SCHEMA_PATH = REPO_ROOT / "docs" / "national_strata_schema_raw.csv"
DEFAULT_DETAIL_OUTPUT_PATH = REPO_ROOT / "docs" / "region_national_schema_consistency.csv"
DEFAULT_SUMMARY_OUTPUT_PATH = REPO_ROOT / "docs" / "region_national_schema_consistency_summary.csv"


# -------------------------------------------------------------------------------------------
# Pure core functions — no I/O, fully unit-testable
# -------------------------------------------------------------------------------------------


def load_national_joined_schema(national_schema_csv: pd.DataFrame) -> list[tuple[str, str]]:
    """Extracts the national joined table's (column_name, arrow_dtype) list, in schema order, from
    the already-committed `docs/national_strata_schema_raw.csv`. Raises `ValueError` — loudly, not
    silently returning an empty list — if that table's rows are missing from the given DataFrame,
    since every comparison this step makes depends on this succeeding."""
    rows = national_schema_csv.loc[national_schema_csv["source_table"] == STRATA_NATIONAL_JOINED_TABLE]
    if len(rows) == 0:
        raise ValueError(
            f"{STRATA_NATIONAL_JOINED_TABLE!r} has no rows in the given national schema data — "
            "re-run scripts/inspect_national_strata_schema.py (Stage 3 Step 1) first"
        )
    rows = rows.sort_values("position")
    return list(zip(rows["column_name"], rows["arrow_dtype"]))


def find_duplicate_column_names(columns: list[tuple[str, str]]) -> list[str]:
    """Column names that appear more than once in `columns`, in first-seen order. Every other
    function in this module builds a `dict(columns)` lookup at some point, which silently collapses
    a duplicate to its last occurrence — exactly the risk Stage 3 Step 1's own `schema_risk_
    findings.duplicate_column_names` check already treats as a real, checkable category for the
    national tables. This step is the first point a REGION table's schema is inspected at all, so a
    duplicate there is a live unknown, not something already ruled out — checked explicitly rather
    than silently trusted."""
    seen: set[str] = set()
    dupes: list[str] = []
    for name, _ in columns:
        if name in seen and name not in dupes:
            dupes.append(name)
        seen.add(name)
    return dupes


def compare_schemas(national_columns: list[tuple[str, str]], region_columns: list[tuple[str, str]]) -> dict:
    """Pure comparison between the national joined table's (name, dtype) list and one region's. All
    matching is by column NAME, since that is how every downstream script (Steps 2/5/6's outputs
    included) actually keys its lookups — order is reported separately and is informational only.

    Returns a dict with `missing_in_region`, `extra_in_region` (both lists of column names, in
    their SOURCE list's original order — not alphabetized, so a human scanning the output sees them
    in a familiar order), `dtype_mismatches` (dict of column_name -> {"national": ..., "region":
    ...} for columns present in both with a different Arrow dtype string), `duplicate_in_national`/
    `duplicate_in_region` (lists of column names repeated within that side's OWN schema — see
    `find_duplicate_column_names`; a name appearing here means every other field in this result for
    that name is unreliable, since it was computed against a `dict()` that silently kept only the
    last occurrence), `order_matches` (bool — True only if every column present in both appears in
    the same relative order in both lists), and `columns_match` (bool — True only if there is no
    missing, no extra, no dtype mismatch, AND no duplicate on either side; deliberately does NOT
    factor in `order_matches`, since a same-columns-different-order schema is not a functional
    problem for this project's name-keyed code)."""
    duplicate_in_national = find_duplicate_column_names(national_columns)
    duplicate_in_region = find_duplicate_column_names(region_columns)

    national_dict = dict(national_columns)
    region_dict = dict(region_columns)
    national_names = [name for name, _ in national_columns]
    region_names = [name for name, _ in region_columns]
    national_set = set(national_names)
    region_set = set(region_names)

    missing_in_region = [name for name in national_names if name not in region_set]
    extra_in_region = [name for name in region_names if name not in national_set]

    dtype_mismatches: dict[str, dict[str, str]] = {}
    for name in national_names:
        if name in region_dict and region_dict[name] != national_dict[name]:
            dtype_mismatches[name] = {"national": national_dict[name], "region": region_dict[name]}

    shared_in_national_order = [name for name in national_names if name in region_set]
    shared_in_region_order = [name for name in region_names if name in national_set]
    order_matches = shared_in_national_order == shared_in_region_order

    columns_match = (
        not missing_in_region
        and not extra_in_region
        and not dtype_mismatches
        and not duplicate_in_national
        and not duplicate_in_region
    )

    return {
        "missing_in_region": missing_in_region,
        "extra_in_region": extra_in_region,
        "dtype_mismatches": dtype_mismatches,
        "duplicate_in_national": duplicate_in_national,
        "duplicate_in_region": duplicate_in_region,
        "order_matches": order_matches,
        "columns_match": columns_match,
    }


def check_row_count(num_rows: int, region: str) -> dict:
    """Compares one region's live row count against the two candidate expectations this project
    already has on record for it (`REGION_TRACT_COUNTS`: total tract membership;
    `SCORED_TRACT_COUNTS`: the narrower scorable-tract count — these already differ for South-
    Central Texas, Section 4.7/4.8). Reports both booleans rather than picking one in advance, since
    which one (if either) a region's joined strata table actually matches is exactly the live
    question this function exists to answer, not something to assume."""
    return {
        "num_rows": num_rows,
        "matches_region_total": num_rows == REGION_TRACT_COUNTS.get(region),
        "matches_scored_total": num_rows == SCORED_TRACT_COUNTS.get(region),
    }


def build_detail_rows(region: str, comparison: dict, national_columns: list[tuple[str, str]], region_columns: list[tuple[str, str]]) -> list[dict]:
    """One row per column in the union of national and this region's columns — present/absent and
    dtype on each side, so a human or a later script can audit every single column's fate for this
    region, not just the aggregate counts."""
    national_dict = dict(national_columns)
    region_dict = dict(region_columns)
    national_position = {name: i for i, (name, _) in enumerate(national_columns)}
    region_position = {name: i for i, (name, _) in enumerate(region_columns)}
    all_names = list(dict.fromkeys([n for n, _ in national_columns] + [n for n, _ in region_columns]))

    rows = []
    for name in all_names:
        in_national = name in national_dict
        in_region = name in region_dict
        rows.append(
            {
                "region": region,
                "column_name": name,
                "in_national": in_national,
                "in_region": in_region,
                "national_dtype": national_dict.get(name, ""),
                "region_dtype": region_dict.get(name, ""),
                "dtype_match": (national_dict.get(name) == region_dict.get(name)) if (in_national and in_region) else None,
                "national_position": national_position.get(name),
                "region_position": region_position.get(name),
            }
        )
    return rows


# -------------------------------------------------------------------------------------------
# Thin, network-touching wrapper
# -------------------------------------------------------------------------------------------


def inspect_region_table(filesystem: FileSystem, region: str, *, path_fn=strata_s3_path) -> dict:
    """Inspects one region's `<region>-strata-tract-table.parquet`. `path_fn` defaults to the real
    `src.config.strata_s3_path`; pass an override to test the wrapper's path construction without a
    real S3 path — the same early-binding note as `inspect_national_strata_schema.inspect_national_
    table` applies (a monkeypatch of the imported name after this module loads will NOT affect a
    call that omits `path_fn=`)."""
    path = path_fn(region, STRATA_REGION_JOINED_TABLE)
    result = inspect_table_schema(filesystem, path, label=f"{region}-{STRATA_REGION_JOINED_TABLE}")
    result["region"] = region
    result["key"] = path
    return result


# -------------------------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------------------------


def main() -> int:
    try:
        national_schema_csv = pd.read_csv(DEFAULT_NATIONAL_SCHEMA_PATH)
    except FileNotFoundError:
        print(
            f"ERROR: {DEFAULT_NATIONAL_SCHEMA_PATH} not found. Run "
            "scripts/inspect_national_strata_schema.py first (Stage 3 Step 1).",
            file=sys.stderr,
        )
        return 2

    try:
        national_columns = load_national_joined_schema(national_schema_csv)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"National schema loaded: {len(national_columns)} columns (from the already-committed CSV, not re-fetched).\n")

    filesystem = S3FileSystem(anonymous=True, region=S3_REGION)

    detail_rows: list[dict] = []
    summary_rows: list[dict] = []
    any_region_failed = False

    for region in REGIONS:
        print(f"Inspecting {region}-{STRATA_REGION_JOINED_TABLE} ...")
        result = inspect_region_table(filesystem, region)

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            any_region_failed = True
            summary_rows.append(
                {
                    "region": region,
                    "error": result["error"],
                    "num_columns_national": len(national_columns),
                    "num_columns_region": None,
                    "num_missing_in_region": None,
                    "num_extra_in_region": None,
                    "num_dtype_mismatches": None,
                    "num_duplicate_in_national": None,
                    "num_duplicate_in_region": None,
                    "order_matches": None,
                    "num_rows": None,
                    "matches_region_total": None,
                    "matches_scored_total": None,
                    "schema_consistent": False,
                }
            )
            continue

        region_columns = result["columns"]
        comparison = compare_schemas(national_columns, region_columns)
        row_count_check = check_row_count(result["num_rows"], region)
        detail_rows.extend(build_detail_rows(region, comparison, national_columns, region_columns))

        print(f"  {len(region_columns)} column(s), {result['num_rows']:,} row(s)")
        print(f"  missing_in_region: {len(comparison['missing_in_region'])}, extra_in_region: {len(comparison['extra_in_region'])}, dtype_mismatches: {len(comparison['dtype_mismatches'])}")
        print(f"  order_matches: {comparison['order_matches']}")
        print(f"  row count matches REGION_TRACT_COUNTS ({REGION_TRACT_COUNTS.get(region)}): {row_count_check['matches_region_total']}; matches SCORED_TRACT_COUNTS ({SCORED_TRACT_COUNTS.get(region)}): {row_count_check['matches_scored_total']}")
        if comparison["missing_in_region"]:
            print(f"  MISSING IN REGION: {comparison['missing_in_region']}")
        if comparison["extra_in_region"]:
            print(f"  EXTRA IN REGION: {comparison['extra_in_region']}")
        if comparison["dtype_mismatches"]:
            print(f"  DTYPE MISMATCHES: {comparison['dtype_mismatches']}")
        if comparison["duplicate_in_national"]:
            print(f"  DUPLICATE COLUMN NAMES IN NATIONAL SCHEMA (unexpected — every other finding for these names is unreliable): {comparison['duplicate_in_national']}")
        if comparison["duplicate_in_region"]:
            print(f"  DUPLICATE COLUMN NAMES IN {region.upper()}'S OWN SCHEMA (every other finding for these names is unreliable): {comparison['duplicate_in_region']}")
        print()

        summary_rows.append(
            {
                "region": region,
                "error": "",
                "num_columns_national": len(national_columns),
                "num_columns_region": len(region_columns),
                "num_missing_in_region": len(comparison["missing_in_region"]),
                "num_extra_in_region": len(comparison["extra_in_region"]),
                "num_dtype_mismatches": len(comparison["dtype_mismatches"]),
                "num_duplicate_in_national": len(comparison["duplicate_in_national"]),
                "num_duplicate_in_region": len(comparison["duplicate_in_region"]),
                "order_matches": comparison["order_matches"],
                "num_rows": result["num_rows"],
                "matches_region_total": row_count_check["matches_region_total"],
                "matches_scored_total": row_count_check["matches_scored_total"],
                "schema_consistent": comparison["columns_match"],
            }
        )

    DEFAULT_DETAIL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    detail_df = pd.DataFrame(detail_rows)
    for col in ("national_position", "region_position"):
        if col in detail_df.columns:
            detail_df[col] = detail_df[col].astype("Int64")
    detail_df.to_csv(DEFAULT_DETAIL_OUTPUT_PATH, index=False)

    summary_df = pd.DataFrame(summary_rows)
    for col in ("num_columns_national", "num_columns_region", "num_missing_in_region", "num_extra_in_region", "num_dtype_mismatches", "num_duplicate_in_national", "num_duplicate_in_region", "num_rows"):
        if col in summary_df.columns:
            summary_df[col] = summary_df[col].astype("Int64")
    summary_df.to_csv(DEFAULT_SUMMARY_OUTPUT_PATH, index=False)
    print(f"Wrote {len(detail_rows)} row(s) to {DEFAULT_DETAIL_OUTPUT_PATH}")
    print(f"Wrote {len(summary_rows)} row(s) to {DEFAULT_SUMMARY_OUTPUT_PATH}")

    print("\n" + "=" * 90)
    print("Summary")
    print("=" * 90)
    for row in summary_rows:
        status = "ERROR" if row["error"] else ("CONSISTENT" if row["schema_consistent"] else "INCONSISTENT")
        print(f"  {row['region']:>18}: {status}")

    n_inconsistent = sum(1 for r in summary_rows if not r["error"] and not r["schema_consistent"])
    if any_region_failed or n_inconsistent:
        print(f"\n{n_inconsistent} region(s) schema-inconsistent, {sum(1 for r in summary_rows if r['error'])} region(s) failed to load.")
        return 1

    print("\nAll four regions' strata-tract-table schemas match the national schema exactly (by column name and dtype).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
