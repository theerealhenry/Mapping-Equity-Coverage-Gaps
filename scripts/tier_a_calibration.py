"""
scripts/tier_a_calibration.py — Stage 7 Step 6: Tier A designed-experiment calibration submissions.

Builds a submission CSV with one or more regions' building-assignment column overridden away from
`src.gaps.BUILDING_GAP_COLUMN`'s current default (`building_gap_intersection`), per the calibration
protocol in `claude/stage7-reference-reconstruction-engine-guideline.md` Step 6: hold three regions
fixed at the current best-trusted value, vary only the candidate in the fourth region -- the RMSE
delta between the paired submissions is attributable to that one region's change. The same
`--override` flag also builds the mandatory cross-region-confirmation submission (pass all four
regions at once) before any isolated-region "win" is treated as settled.

This script does NOT change `src/gaps.py`'s own default -- it only builds alternate submission
files for calibration. Adopting a new default (if Tier A confirms one) is a separate, explicit
code change to `BUILDING_GAP_COLUMN` after the evidence is in, not something this script does
silently.

Usage:
  # isolated-region test: south-central-tx (largest region, best statistical power) on centroid,
  # the other three regions stay on the current default (intersection).
  python -m scripts.tier_a_calibration --override south-central-tx=building_gap_centroid \\
      --out submissions/tier_a/01-building-rule-sctx-centroid.csv

  # cross-region confirmation: every region on centroid at once, checked against the
  # all-intersection baseline (submissions/02-eastern-ok-focused-early-submission.csv).
  python -m scripts.tier_a_calibration \\
      --override eastern-ok=building_gap_centroid \\
      --override maricopa-az=building_gap_centroid \\
      --override northern-ca=building_gap_centroid \\
      --override south-central-tx=building_gap_centroid \\
      --out submissions/tier_a/02-building-rule-all-centroid.csv

  # noise floor: no overrides at all -- reproduces the current baseline byte-for-byte, to be
  # uploaded as a fresh submission and compared against the already-scored baseline.
  python -m scripts.tier_a_calibration --out submissions/tier_a/00-noise-floor-baseline-repeat.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.build_submission import build_score_submission
from src.validate import validate_submission

VALID_BUILDING_GAP_COLUMNS = ("building_gap_centroid", "building_gap_intersection")
VALID_REGIONS = ("eastern-ok", "maricopa-az", "northern-ca", "south-central-tx")


def _parse_override(raw: str) -> tuple[str, str]:
    region, _, column = raw.partition("=")
    if region not in VALID_REGIONS:
        raise argparse.ArgumentTypeError(
            f"--override: unknown region {region!r} -- must be one of {VALID_REGIONS}"
        )
    if column not in VALID_BUILDING_GAP_COLUMNS:
        raise argparse.ArgumentTypeError(
            f"--override: unknown building-gap column {column!r} for region {region!r} -- "
            f"must be one of {VALID_BUILDING_GAP_COLUMNS}"
        )
    return region, column


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--override",
        action="append",
        type=_parse_override,
        default=[],
        metavar="REGION=BUILDING_GAP_COLUMN",
        help="Repeatable. e.g. --override south-central-tx=building_gap_centroid. "
        "Omit entirely to reproduce the current all-default baseline (for a noise-floor repeat).",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    overrides = dict(args.override)
    submission = build_score_submission(building_gap_overrides=overrides)
    validate_submission(submission)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(args.out, index=False)

    if overrides:
        print(f"Overrides applied: {overrides}")
    else:
        print("No overrides -- this reproduces the current default baseline exactly.")
    print(f"Wrote {len(submission)} rows to {args.out} -- validated clean, ready to upload.")


if __name__ == "__main__":
    main()
