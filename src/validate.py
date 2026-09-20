"""
src/validate.py — Stage 7 Step 5: the pre-submission validator.

A last-line-of-defense, fail-closed gate run before EVERY submission upload for the rest of this
project, no exceptions -- the same security-and-hardening "validate before trusting" posture as
`assert_competition_only` in Stage 6, applied here to an irreversible, submission-budget-consuming
action instead of a scoring computation. This checks structural correctness only (row counts,
GEOID membership, value range, no blanks); it says nothing about whether the SCORES are good, only
whether the file is even a legal submission.

The 9,379-row manifest (`data/reference/sample-submission-manifest.csv`, a local copy of Henry's
own `SampleSubmission 3.csv`) is the single source of truth for both the exact GEOID set AND the
expected per-region row counts -- this validator derives per-region counts from the manifest
itself rather than duplicating `src.config.SCORED_TRACT_COUNTS` as a second hardcoded copy that
could silently drift out of sync; the manifest's own counts already equal those constants exactly
(1192/1593/591/6003), so checking against the manifest checks against them too.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

MANIFEST_PATH = Path("data/reference/sample-submission-manifest.csv")

# The float-valued gap columns every real submission carries, per SampleSubmission 3.csv's own
# column header -- each must fall in [0, 1]. An undefined component uses the 0.0 placeholder
# convention (SampleSubmission 3.csv itself has real rows like poi_gap_ems=0 with
# poi_defined_ems=FALSE), never a blank cell.
GAP_VALUE_COLUMNS = (
    "coverage_gap_score",
    "transport_gap",
    "building_gap",
    "poi_gap",
    "poi_gap_fire",
    "poi_gap_ems",
    "poi_gap_schools",
    "poi_gap_cbp",
)

DEFINED_FLAG_COLUMNS = (
    "transport_defined",
    "building_defined",
    "poi_defined",
    "poi_defined_fire",
    "poi_defined_ems",
    "poi_defined_schools",
    "poi_defined_cbp",
)

REQUIRED_COLUMNS = ("GEOID", "region", *GAP_VALUE_COLUMNS, *DEFINED_FLAG_COLUMNS)


def load_manifest() -> pd.DataFrame:
    """The frozen GEOID/region manifest every real submission must match exactly. `dtype=str` on
    GEOID is load-bearing, not cosmetic -- Maricopa's real GEOIDs start with '04' and a plain
    integer read would silently drop that leading zero."""
    return pd.read_csv(MANIFEST_PATH, dtype={"GEOID": str})


def validate_submission(submission: pd.DataFrame, *, manifest: pd.DataFrame | None = None) -> None:
    """Raises ValueError (naming exactly what's wrong) on the first structural problem found;
    returns None on a clean submission. Checks run cheapest/most-informative first: columns
    present, row count, per-region row counts, GEOID membership, blank cells, value range."""
    if manifest is None:
        manifest = load_manifest()

    missing_columns = set(REQUIRED_COLUMNS) - set(submission.columns)
    if missing_columns:
        raise ValueError(
            f"validate_submission: missing required column(s): {sorted(missing_columns)}"
        )

    if len(submission) != len(manifest):
        raise ValueError(
            f"validate_submission: row count {len(submission)} != manifest's {len(manifest)}"
        )

    expected_per_region = manifest.groupby("region").size().to_dict()
    actual_per_region = submission.groupby("region").size().to_dict()
    if actual_per_region != expected_per_region:
        raise ValueError(
            f"validate_submission: per-region row counts don't match the manifest -- "
            f"expected {expected_per_region}, got {actual_per_region}"
        )

    submission_geoids = set(submission["GEOID"])
    manifest_geoids = set(manifest["GEOID"])
    extra = submission_geoids - manifest_geoids
    missing = manifest_geoids - submission_geoids
    if extra or missing:
        raise ValueError(
            f"validate_submission: GEOID set does not exactly match the manifest -- "
            f"{len(extra)} extra, {len(missing)} missing "
            f"(first few extra: {sorted(extra)[:5]}, first few missing: {sorted(missing)[:5]})"
        )

    blank_cells = submission[list(REQUIRED_COLUMNS)].isna()
    if blank_cells.any().any():
        bad_columns = blank_cells.any()[blank_cells.any()].index.tolist()
        raise ValueError(
            f"validate_submission: blank cell(s) found in column(s) {bad_columns} -- an "
            "undefined component must use the 0.0 placeholder convention (with its _defined flag "
            "set False), never a blank cell"
        )

    for col in GAP_VALUE_COLUMNS:
        out_of_range = ~submission[col].between(0.0, 1.0)
        if out_of_range.any():
            bad_values = submission.loc[out_of_range, col].tolist()[:5]
            raise ValueError(
                f"validate_submission: column {col!r} has value(s) outside [0, 1]: {bad_values}"
            )
