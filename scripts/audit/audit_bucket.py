"""
scripts/audit/audit_bucket.py — Stage 2, Step 5.

The generalized replacement for scripts/verify_bucket.py's eastern-ok-only, boto3-based, ad hoc
spot check. This script runs the real Gate A quality pass PROJECT_BLUEPRINT.md's Stage 2 calls
for: null coverage per column, duplicate-GEOID checks, geometry validity (invalid/empty/null
geometries), and CRS/schema-contract pass-fail — across every one of the four study regions and
every reference layer type `src/schemas.py` (Stage 2 Step 3) covers, not just one region as a spot
check. It also fixes the two carried-forward issues Henry flagged in `verify_bucket.py` and asked
to defer here rather than fix in place: this script uses `src.io`'s loaders (obstore/pyarrow under
the hood, not `boto3`) and imports every constant from `src.config` rather than redefining
`BUCKET`/`ROOT`/`REGIONS` locally.

What this script does NOT do: it does not re-implement CRS normalization or pandera validation —
it calls `src.io.load_reference_layer`/`load_strata_table`, which already do both (Stage 2 Steps
2-4). This script's own job is everything Stage 2 Steps 2-4 deliberately left OUT of their own
scope: cross-row statistics (null coverage, duplicate GEOIDs) and geometry-level QA (validity,
emptiness) that a per-column pandera contract cannot express, plus running the whole pipeline for
real across every region so Gate A's "every layer in every region has a passing schema contract"
can actually be signed off, not assumed from a single-region spot check.

A second, deliberate purpose: several constraints in `src/schemas.py` were marked "ASSUMPTION, not
yet audit-confirmed" and left permissive specifically so they wouldn't break the pipeline before
this script existed to check them for real (see e.g. `OVERTURE_BUILDINGS_SCHEMA`'s `class`
nullability, `MICROSOFT_BUILDINGS_SCHEMA`'s `height`/`confidence` nullability). This script's
`null_pct_by_column` output is exactly the evidence needed to go back and either tighten those
schemas (if the real null rate is 0%) or leave them permissive with a confirmed, cited number
instead of a guess.

Design: every function that touches the network is a thin wrapper around a pure, dependency-free
core function — the same testable-core pattern used throughout this project's scripts (see
scripts/inspect_overture_sources.py's `inspect_sources_at_path`). `geometry_validity_stats`,
`null_coverage`, `duplicate_geoid_count`, and `audit_layer` take an already-loaded GeoDataFrame and
have no I/O at all; `audit_reference_layer`/`audit_strata_table` accept an injectable `loader`
callable (defaulting to the real `src.io` functions) so the exception-to-status classification
logic is fully unit-testable without network access — see tests/test_audit_bucket.py.

A subtlety worth being explicit about, confirmed directly before relying on it: shapely's
`.is_valid` returns `False` for a null (None) geometry, not `True` or `NaN` — treating that as
"invalid" would conflate MISSING geometries with MALFORMED ones, two different, differently
actionable findings. Every geometry-QA function below explicitly separates null geometries out
first and only computes validity/emptiness/geom_type statistics over the non-null remainder.

Run with:
    python scripts/audit/audit_bucket.py                       # all 4 regions, all 10 layers
    python scripts/audit/audit_bucket.py --region maricopa-az   # one region, fast iteration
    python scripts/audit/audit_bucket.py --layers overture-buildings census-cbp
    python scripts/audit/audit_bucket.py --skip-strata          # reference layers only

Writes findings to docs/audit_findings.csv (one row per region/layer or region/strata-table
combination) and exits 1 if any combination did not load cleanly, 0 otherwise — suitable for a
CI/Makefile gate later, though wiring that up is not this step's scope.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import REGION_TRACT_COUNTS, REGIONS, STRATA_KEY_COLUMN  # noqa: E402
from src.io import load_reference_layer, load_strata_table  # noqa: E402
from src.schemas import LAYER_SCHEMAS, SchemaValidationError  # noqa: E402

DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "audit_findings.csv"

REFERENCE_LAYERS = sorted(LAYER_SCHEMAS)
"""Every layer name with a registered pandera schema (Stage 2 Step 3) — the 10 real per-region
files (7 distinct layer TYPES, with the 4 HIFLD facility files sharing one schema) this script
audits by default. Deliberately sourced from the registry itself, not hand-typed, so a layer added
to src/schemas.py later is picked up here automatically without this file needing an edit."""

STRATA_TABLES_TO_AUDIT = ("census-tracts",)
"""Strata tables audited per region beyond the reference layers above. Scoped narrowly to the one
table this project's tract-membership counts depend on (REGION_TRACT_COUNTS cross-check below) —
not every strata table under strata/<region>/, which src/schemas.py does not cover yet (see
src/io.py's module docstring on that scope boundary). Extend this tuple, not this script's
structure, if a future stage needs another strata table audited the same way."""


# -------------------------------------------------------------------------------------------
# Pure core functions — no I/O, fully unit-testable
# -------------------------------------------------------------------------------------------


def geometry_validity_stats(geometry: gpd.GeoSeries) -> dict:
    """Null/invalid/empty/geom-type counts for a geometry column. Null geometries are separated
    out FIRST and excluded from the invalid/empty/geom-type statistics — see the module docstring
    for why (`.is_valid` returns False, not NaN, for a null geometry; conflating "missing" with
    "malformed" would misreport both)."""
    null_count = int(geometry.isna().sum())
    non_null = geometry.dropna()
    if len(non_null) > 0:
        invalid_count = int((~non_null.is_valid).sum())
        empty_count = int(non_null.is_empty.sum())
        geom_type_counts = {str(k): int(v) for k, v in non_null.geom_type.value_counts().items()}
    else:
        invalid_count = 0
        empty_count = 0
        geom_type_counts = {}
    return {
        "row_count": int(len(geometry)),
        "null_geometry_count": null_count,
        "invalid_geometry_count": invalid_count,
        "empty_geometry_count": empty_count,
        "geometry_type_counts": geom_type_counts,
    }


def null_coverage(df: pd.DataFrame, *, exclude: tuple[str, ...] = ("geometry",)) -> dict:
    """Fraction of null values per non-geometry column (0.0-1.0), or None for a genuinely 0-row
    layer (a real, expected case -- e.g. an Overture layer type this project doesn't use, guarded
    against in scripts/inspect_overture_sources.py). Works uniformly across scalar columns
    (str/float/int) and object columns holding lists/dicts (`sources`, `categories`, `bbox`) —
    confirmed directly that pandas' `.isna()` correctly identifies None vs. a real list/dict value
    element-wise for these, rather than raising or misclassifying.

    Confirmed directly (and regression-tested below) that `.isna().mean()` on a 0-row column
    returns NaN, not 0.0 or an error -- `json.dumps` then emits the bare, non-spec-compliant `NaN`
    token for it (Python's own `json.loads` tolerates this, but a stricter downstream JSON parser
    would not), so the 0-row case is mapped to `None` (valid JSON `null`) explicitly rather than
    left as a silent NaN."""
    n_rows = len(df)
    return {
        col: (float(df[col].isna().mean()) if n_rows > 0 else None)
        for col in df.columns
        if col not in exclude
    }


def duplicate_geoid_count(df: pd.DataFrame) -> int | None:
    """Count of GEOID values appearing more than once (each duplicate beyond the first counted
    once — i.e. `.duplicated()`'s default `keep='first'` semantics). Returns None, not 0, when the
    layer has no GEOID column at all — a real "no duplicates" (0) and "not applicable" (None) are
    different findings and must not be conflated in the output CSV."""
    if STRATA_KEY_COLUMN not in df.columns:
        return None
    return int(df[STRATA_KEY_COLUMN].duplicated().sum())


def audit_layer(gdf: gpd.GeoDataFrame, *, region: str, layer: str) -> dict:
    """Composes the pure checks above into one successful-load finding row. Only called after a
    layer has already loaded and passed src.io's CRS-normalization and schema validation — this
    function adds the audit-level statistics Stage 2 Steps 2-4 deliberately left out of their own
    scope (see module docstring)."""
    finding: dict = {"region": region, "layer": layer, "status": "ok", "error_message": ""}
    finding.update(geometry_validity_stats(gdf.geometry))
    finding["geometry_type_counts"] = json.dumps(finding["geometry_type_counts"])
    finding["null_pct_by_column"] = json.dumps(null_coverage(gdf))
    finding["duplicate_geoid_count"] = duplicate_geoid_count(gdf)
    return finding


_MAX_ERROR_MESSAGE_LENGTH = 8000
"""Applied uniformly to every failure path in _empty_finding, not just pandera's -- SchemaErrors
messages are the most likely to be long (one entry per independent violation, up to pandera's own
internal per-check truncation), but a raw pyarrow/OSError message can also be long, and there's no
reason one bad layer's error text should be allowed to dominate the output CSV regardless of which
exception type produced it.

Raised from an original 2000 during the Step 5 review pass, once `src/schemas.py`'s validate_layer
switched to `lazy=True` (aggregating every independent violation into one report instead of
stopping at the first). Confirmed directly that this genuinely matters: a realistic worst case for
HIFLD_FACILITY_SCHEMA (most of its ~12 declared columns wrong or missing at once) produced a 2557-
character message on its own -- already past the OLD 2000-character cap, which would have silently
dropped the last violation and directly undercut the reason lazy=True was adopted in the first
place. 8000 gives real headroom above that measured worst case while staying bounded: each
individual check's own failure text is naturally capped by pandas' own Series-repr truncation
(confirmed separately -- a check against millions of failing rows still produces only a few hundred
characters, since pandas' repr shows just the head/tail with "..." regardless of the real row
count), so the aggregate message's size scales with the number of DISTINCT VIOLATING CHECKS a
schema can have (bounded by its own column count, well under 20 for every schema in this project),
not with the number of failing rows -- it cannot grow unboundedly."""


def _empty_finding(*, region: str, layer: str, status: str, error_message: str) -> dict:
    """A finding row for a layer that never made it to audit_layer -- every field audit_layer
    would have populated is present but empty/None, so the output CSV has a consistent column set
    regardless of whether a given region/layer combination succeeded or failed. error_message is
    truncated here, once, for every failure path (see _MAX_ERROR_MESSAGE_LENGTH)."""
    return {
        "region": region,
        "layer": layer,
        "status": status,
        "error_message": error_message[:_MAX_ERROR_MESSAGE_LENGTH],
        "row_count": None,
        "null_geometry_count": None,
        "invalid_geometry_count": None,
        "empty_geometry_count": None,
        "geometry_type_counts": "",
        "null_pct_by_column": "",
        "duplicate_geoid_count": None,
    }


_INT_COLUMNS = (
    "row_count",
    "null_geometry_count",
    "invalid_geometry_count",
    "empty_geometry_count",
    "duplicate_geoid_count",
    "expected_row_count",
)
"""Every count column that is a genuine integer whenever it's populated, but None for a failed or
not-applicable row. Cast to pandas' *nullable* Int64 (capital I) dtype in build_report -- plain
int64 can't hold None/NaN at all, and the naive `pd.DataFrame(findings)` construction otherwise
silently upcasts these to plain float64 the moment ANY row in the run has a None (which happens
routinely -- e.g. south-central-tx's confirmed-missing census-tribal-subdivisions file, per
docs/data_manifest.md Section 3), rendering every row_count as "1.0" instead of "1" in the CSV,
including on rows that loaded and validated perfectly cleanly. Confirmed directly before fixing:
without this cast, mixing one failed finding into a batch is enough to corrupt every numeric
column's formatting for the whole file, not just the failed row's own fields."""


def build_report(findings: list[dict]) -> pd.DataFrame:
    """Builds the output DataFrame with clean, stable dtypes -- pandas' nullable Int64/boolean
    dtypes for the count/flag columns (see _INT_COLUMNS docstring), rather than letting
    `pd.DataFrame(findings)` infer dtypes column-by-column, which silently drifts to float64 the
    moment a None/NaN appears anywhere in that column across the batch."""
    report = pd.DataFrame(findings)
    for col in _INT_COLUMNS:
        if col in report.columns:
            report[col] = report[col].astype("Int64")
    if "row_count_matches_expected" in report.columns:
        report["row_count_matches_expected"] = report["row_count_matches_expected"].astype("boolean")
    return report


def _classify_and_run(
    loader: Callable[[], gpd.GeoDataFrame], *, region: str, layer: str
) -> dict:
    """Calls `loader()` (a zero-arg closure over the real src.io call) and classifies whatever
    happens into a distinct, actionable status string, rather than a single generic "failed"
    bucket -- "missing_file" (a real, expected case for some strata tables), "schema_violation"
    (a pandera contract failure), "not_implemented" (a layer this script asked to audit but
    src/schemas.py has no contract for -- should not happen given REFERENCE_LAYERS is sourced
    from the same registry, but defensive rather than silently mis-attributed to "error" if that
    registry and this script's layer list ever drift), "value_error" (e.g. a CRS this project's
    data is not expected to be in), "read_error" (a wrapped I/O failure), "audit_error" (the load
    and schema validation both succeeded, but computing this script's OWN audit-level statistics —
    geometry_validity_stats/null_coverage/duplicate_geoid_count — raised; see below for why this
    is caught separately rather than left to escape), or "error" (anything else, unclassified but
    never silently swallowed).

    Two separate try/except blocks, deliberately: the first covers `loader()` (the network read +
    CRS normalize + schema validate composed in src.io), the second covers `audit_layer()` alone.
    An earlier version of this function called `audit_layer()` OUTSIDE any try/except, on the
    reasoning that a layer which already loaded and passed its pandera contract "should" be safe
    to summarize. That reasoning doesn't hold at the real scale this script runs at (a single
    region/layer combination can be 10+ million rows, per docs/data_manifest.md) — an unexpected
    edge case in the audit's own statistics code (a dtype `.isna()` doesn't handle the way tested,
    a geometry type `.geom_type`/`.is_valid` chokes on, anything not covered by the synthetic
    fixtures in tests/test_audit_bucket.py) would otherwise propagate all the way up through
    main()'s double loop and crash the ENTIRE batch run -- discarding every finding already
    computed for every other region/layer combination, since docs/audit_findings.csv is only
    written once, after the full loop completes. One bad layer must not be able to sink 43 good
    findings; the second try/except is what guarantees that."""
    try:
        gdf = loader()
    except FileNotFoundError as exc:
        return _empty_finding(region=region, layer=layer, status="missing_file", error_message=str(exc))
    except NotImplementedError as exc:
        return _empty_finding(region=region, layer=layer, status="not_implemented", error_message=str(exc))
    except SchemaValidationError as exc:
        return _empty_finding(region=region, layer=layer, status="schema_violation", error_message=str(exc))
    except ValueError as exc:
        return _empty_finding(region=region, layer=layer, status="value_error", error_message=str(exc))
    except RuntimeError as exc:
        return _empty_finding(region=region, layer=layer, status="read_error", error_message=str(exc))
    except Exception as exc:  # noqa: BLE001 — deliberately the last resort, never silently swallowed
        return _empty_finding(
            region=region, layer=layer, status="error", error_message=f"{type(exc).__name__}: {exc}"
        )

    try:
        return audit_layer(gdf, region=region, layer=layer)
    except Exception as exc:  # noqa: BLE001 — see the docstring: this is deliberately separate
        return _empty_finding(
            region=region, layer=layer, status="audit_error", error_message=f"{type(exc).__name__}: {exc}"
        )


# -------------------------------------------------------------------------------------------
# Thin, network-touching wrappers
# -------------------------------------------------------------------------------------------


def audit_reference_layer(
    region: str, layer: str, *, loader: Callable[[str, str], gpd.GeoDataFrame] = load_reference_layer
) -> dict:
    """Audits one reference layer. `loader` defaults to the real `src.io.load_reference_layer` —
    overriding it (with a fake that raises a specific exception on demand) is how this function's
    classification logic is tested without network access."""
    return _classify_and_run(lambda: loader(region, layer), region=region, layer=layer)


def audit_strata_table(
    region: str, table: str, *, loader: Callable[[str, str], gpd.GeoDataFrame] = load_strata_table
) -> dict:
    """Audits one per-region strata table. Same injectable-loader pattern as
    `audit_reference_layer`. When `table` is "census-tracts" and the load succeeds, also cross-
    checks the row count against `REGION_TRACT_COUNTS` (docs/data_manifest.md Section 4.7) —
    stored in the finding as `expected_row_count`/`row_count_matches_expected` rather than as a
    pass/fail on `status`, since a mismatch here is a data finding worth recording, not a schema
    contract violation the way the reference-layer checks are."""
    finding = _classify_and_run(lambda: loader(region, table), region=region, layer=f"strata/{table}")
    if table == "census-tracts" and finding["status"] == "ok":
        expected = REGION_TRACT_COUNTS.get(region)
        finding["expected_row_count"] = expected
        finding["row_count_matches_expected"] = expected is not None and finding["row_count"] == expected
    else:
        finding["expected_row_count"] = None
        finding["row_count_matches_expected"] = None
    return finding


# -------------------------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 2 Step 5 bucket audit: schema pass/fail, null coverage, geometry validity, "
            "and duplicate-GEOID checks, across all regions and reference layers."
        )
    )
    parser.add_argument(
        "--region",
        nargs="*",
        choices=REGIONS,
        default=None,
        help="Restrict to specific region(s). Default: all four.",
    )
    parser.add_argument(
        "--layers",
        nargs="*",
        choices=REFERENCE_LAYERS,
        default=None,
        help="Restrict to specific reference layer(s). Default: every layer with a registered schema.",
    )
    parser.add_argument(
        "--skip-strata",
        action="store_true",
        help="Skip the per-region strata-table audit (faster iteration on reference layers alone).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"CSV output path (default: {DEFAULT_OUTPUT_PATH}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    regions = args.region if args.region else list(REGIONS)
    layers = args.layers if args.layers else list(REFERENCE_LAYERS)

    findings: list[dict] = []
    for region in regions:
        for layer in layers:
            print(f"Auditing {region} / {layer} ...")
            finding = audit_reference_layer(region, layer)
            findings.append(finding)
            _print_finding_summary(finding)

        if not args.skip_strata:
            for table in STRATA_TABLES_TO_AUDIT:
                print(f"Auditing {region} / strata/{table} ...")
                finding = audit_strata_table(region, table)
                findings.append(finding)
                _print_finding_summary(finding)

    report = build_report(findings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(f"\nWrote {len(report)} finding(s) to {args.output}")

    n_ok = int((report["status"] == "ok").sum())
    n_total = len(report)
    print(f"{n_ok}/{n_total} region/layer combination(s) loaded and validated cleanly.")

    failures = report[report["status"] != "ok"]
    if len(failures):
        print(f"\n{len(failures)} failure(s):")
        for _, row in failures.iterrows():
            print(f"  {row['region']} / {row['layer']}: {row['status']} — {str(row['error_message'])[:200]}")
        return 1
    return 0


def _print_finding_summary(finding: dict) -> None:
    if finding["status"] != "ok":
        print(f"  status: {finding['status']} — {str(finding['error_message'])[:200]}")
        return
    print(
        f"  status: ok — {finding['row_count']:,} rows, "
        f"{finding['null_geometry_count']} null / {finding['invalid_geometry_count']} invalid / "
        f"{finding['empty_geometry_count']} empty geometr(y/ies)"
        + (
            f", {finding['duplicate_geoid_count']} duplicate GEOID(s)"
            if finding["duplicate_geoid_count"] is not None
            else ""
        )
    )


if __name__ == "__main__":
    sys.exit(main())
