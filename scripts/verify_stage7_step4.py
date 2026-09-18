"""
scripts/verify_stage7_step4.py — Stage 7 Step 4: any-of-three-undefined self-check.

Reproduces the published "at least one component undefined" percentage per region
(claude/final-project-plan.md Section 1b: eastern-ok 21%, northern-ca 37%, south-central-tx 28%,
maricopa-az 55%, rounded) from src/gaps.py's own component-definedness output, independent of
whatever the eventual capped-ratio VALUE turns out to be -- this only checks which tracts have at
least one undefined component among {transport, building, poi}, not the gap numbers themselves.

Different statistic from Stage 5/6's transport-only-undefined check (road + tract data alone): this
one genuinely could not be verified until building- and poi-definedness existed, which is why it's
sequenced here, after Step 3, not earlier. A close match is strong evidence the definedness logic
across all three components is correct; a mismatch means a real bug that must be localized and
fixed BEFORE Step 5 spends any real submission budget calibrating a pipeline that might be wrong in
a way this check would have caught for free.

Run with: python scripts/verify_stage7_step4.py
"""

from __future__ import annotations

import sys

from src.gaps import PROCESSED_DIR, score_region
import pandas as pd

# Rounded published figures, claude/final-project-plan.md Section 1b.
PUBLISHED_ANY_UNDEFINED_PCT = {
    "eastern-ok": 21,
    "northern-ca": 37,
    "south-central-tx": 28,
    "maricopa-az": 55,
}

# How close counts as "a clean match" rather than "a bug to localize". The published figures are
# themselves rounded to the nearest percentage point, so +/-1.5pp absorbs that rounding alone;
# anything wider is treated as a real discrepancy, not noise, per this step's own "why".
TOLERANCE_PP = 1.5


def any_of_three_undefined_pct(region: str) -> float:
    """The real, computed rate for one region: the percentage of tracts where at least one of
    {transport_defined, building_defined, poi_defined} is False."""
    tract_features = pd.read_parquet(PROCESSED_DIR / f"{region}-tract-features.parquet")
    scored = score_region(tract_features)
    any_undefined = ~(
        scored["transport_defined"] & scored["building_defined"] & scored["poi_defined"]
    )
    return 100 * any_undefined.mean()


def main() -> int:
    print(f"{'region':<20}{'published':>12}{'computed':>12}{'delta':>10}  status")
    all_clean = True
    for region, published_pct in PUBLISHED_ANY_UNDEFINED_PCT.items():
        computed_pct = any_of_three_undefined_pct(region)
        delta = computed_pct - published_pct
        clean = abs(delta) <= TOLERANCE_PP
        all_clean &= clean
        status = "PASS" if clean else "FAIL -- localize before Step 5"
        print(f"{region:<20}{published_pct:>11}%{computed_pct:>11.1f}%{delta:>+9.1f}pp  {status}")

    if all_clean:
        print("\nAll four regions match within tolerance -- definedness logic confirmed sane.")
        return 0
    print("\nAt least one region is outside tolerance -- do NOT proceed to Step 5 until localized.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
