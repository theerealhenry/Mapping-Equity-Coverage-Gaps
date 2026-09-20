"""
scripts/build_submission.py — Stage 7 Step 5: builds a real, uploadable submission CSV.

Runs `src.gaps.score_all_regions()`, reshapes it into the exact column set/order/naming
`SampleSubmission 3.csv` uses (`poi_gap_establishments` -> `poi_gap_cbp`, same for its `_defined`
flag), filters down to exactly the manifest's 9,379 scored GEOIDs (south-central-tx's raw
tract-features table has 6010 rows; the manifest keeps only the scored 6003 -- the water-exclusion
tracts already understood and documented in docs/decision_log.md), fills undefined-component NaNs
with the 0.0 placeholder convention the real template uses, and validates the result with
`src.validate` before writing anything to disk.

Two variants, chosen by --mode:
  smoke  -- every gap value forced to a constant 0.5, everything marked defined=True. Spends 1 of
            the 300-submission budget purely to confirm Zindi accepts the file's shape/format.
  score  -- the real, current best-guess score from the pipeline's Step-3 starting-default formula
            choices. NOT the frozen answer -- Stage 7 Steps 6-9 still calibrate the real winners.

Run with:
  python -m scripts.build_submission --mode smoke
  python -m scripts.build_submission --mode score
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.gaps import score_all_regions
from src.validate import load_manifest, validate_submission

SUBMISSIONS_DIR = Path("submissions")

# gaps.py's internal column name -> the real template's column name. Only the establishments/CBP
# component is renamed; every other Step-3 output column name already matches the template.
_RENAME_TO_TEMPLATE = {
    "poi_gap_establishments": "poi_gap_cbp",
    "poi_gap_establishments_defined": "poi_defined_cbp",
    "poi_gap_fire_defined": "poi_defined_fire",
    "poi_gap_ems_defined": "poi_defined_ems",
    "poi_gap_schools_defined": "poi_defined_schools",
}

TEMPLATE_COLUMN_ORDER = [
    "GEOID",
    "coverage_gap_score",
    "region",
    "transport_gap",
    "transport_defined",
    "building_gap",
    "building_defined",
    "poi_gap",
    "poi_defined",
    "poi_gap_fire",
    "poi_defined_fire",
    "poi_gap_ems",
    "poi_defined_ems",
    "poi_gap_schools",
    "poi_defined_schools",
    "poi_gap_cbp",
    "poi_defined_cbp",
]

GAP_COLUMNS = [
    "coverage_gap_score",
    "transport_gap",
    "building_gap",
    "poi_gap",
    "poi_gap_fire",
    "poi_gap_ems",
    "poi_gap_schools",
    "poi_gap_cbp",
]

DEFINED_COLUMNS = [
    "transport_defined",
    "building_defined",
    "poi_defined",
    "poi_defined_fire",
    "poi_defined_ems",
    "poi_defined_schools",
    "poi_defined_cbp",
]


def build_score_submission() -> pd.DataFrame:
    """The real, current-best-guess submission -- Step 3's pipeline output, reshaped to the
    template and filtered to exactly the manifest's GEOID set."""
    scored = score_all_regions().rename(columns=_RENAME_TO_TEMPLATE)
    manifest = load_manifest()

    manifest_geoids_in_scored = manifest["GEOID"].isin(scored["GEOID"])
    if not manifest_geoids_in_scored.all():
        missing = manifest.loc[~manifest_geoids_in_scored, "GEOID"].tolist()
        raise ValueError(
            f"build_score_submission: {len(missing)} manifest GEOID(s) not found in "
            f"score_all_regions() output -- first few: {missing[:5]}"
        )

    submission = manifest[["GEOID", "region"]].merge(
        scored.drop(columns=["region"]), on="GEOID", how="left"
    )

    # Undefined-component NaNs -> the 0.0 placeholder convention the real template uses (a real
    # SampleSubmission 3.csv row has poi_gap_ems=0 with poi_defined_ems=FALSE, never a blank cell).
    submission[GAP_COLUMNS] = submission[GAP_COLUMNS].fillna(0.0)
    submission[DEFINED_COLUMNS] = submission[DEFINED_COLUMNS].fillna(False).astype(bool)

    return submission[TEMPLATE_COLUMN_ORDER]


def build_smoke_submission() -> pd.DataFrame:
    """Every GEOID from the manifest, every gap value pinned to the midpoint 0.5, everything
    marked defined -- purely to confirm Zindi accepts the file's shape before spending any
    submission budget on an actual score."""
    manifest = load_manifest()
    submission = manifest[["GEOID", "region"]].copy()
    submission[GAP_COLUMNS] = 0.5
    submission[DEFINED_COLUMNS] = True
    return submission[TEMPLATE_COLUMN_ORDER]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["smoke", "score"], required=True)
    args = parser.parse_args()

    SUBMISSIONS_DIR.mkdir(exist_ok=True)
    if args.mode == "smoke":
        submission = build_smoke_submission()
        out_path = SUBMISSIONS_DIR / "01-smoke-test-submission.csv"
    else:
        submission = build_score_submission()
        out_path = SUBMISSIONS_DIR / "02-eastern-ok-focused-early-submission.csv"

    validate_submission(submission)
    submission.to_csv(out_path, index=False)
    print(f"Wrote {len(submission)} rows to {out_path} -- validated clean, ready to upload.")


if __name__ == "__main__":
    main()
