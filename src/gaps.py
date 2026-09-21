"""
src/gaps.py — Stage 7 (Reference Reconstruction Engine).

Owned by Stage 7. This is the Reference Reconstruction Engine itself (System A) — the deterministic
computation, not a trained model, at the center of this project. Responsible for reading only
`competition`-tagged columns from the Stage 6 feature tables and producing the composite
`coverage_gap_score` per tract, computed as the capped-ratio formula `1 - min(1, overture/
reference)` per component (transport, building, POI), with undefined components excluded from the
mean entirely (never zeroed) — the exact edge cases `tests/test_gap_arithmetic.py` exists to lock
down before this module is ever run against real data. Calls into `src/geometry.py` for every
spatial assignment (point-in-polygon, centroid-in-polygon vs. intersection, line-clip-and-sum) —
`gaps.py` owns the formula and orchestration, `geometry.py` owns every spatial operation, by
explicit design so no component re-implements its own slightly different spatial logic.

Step 3 status: the real pipeline is built below, against `eastern-ok` first per this project's
smallest-region-first convention. `COMPETITION_ALLOWED_COLUMNS` (src/schemas.py) was widened at
this step, with Henry's explicit approval, from empty to the seven Step-3 candidate gap columns
plus their `_defined` companions — see that constant's own comment and docs/decision_log.md for
the full reasoning. The building-assignment rule used here (`building_gap_intersection`) is a
STARTING DEFAULT, not the frozen choice: `claude/final-project-plan.md` states a working bias
toward the more conservative, boundary-inclusive intersection rule pending real calibration
evidence, and Stage 7 Steps 6-9 are what actually decide between it and `building_gap_centroid`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import REGIONS
from src.features import assert_competition_only

PROCESSED_DIR = Path("data/processed")

# Step 3's starting-default candidate choice per component. NOT frozen -- Stage 7 Steps 6-9
# calibrate the real winners on RMSE evidence; scoring/v1/formula.yaml (Step 11) records whichever
# wins. Transport and the four POI sub-parts have only one candidate each (no rule to pick between)
# so there is nothing to default here for them.
TRANSPORT_GAP_COLUMN = "transport_gap"
# Irregular name -- every other gap column's defined-flag is "<col>_defined" (see
# src.schemas._DEFINED_COLUMN_NAMES), but transport's is "transport_defined", not
# "transport_gap_defined". Kept as its own explicit constant rather than derived from
# TRANSPORT_GAP_COLUMN by string concatenation, specifically so this naming exception can never
# silently reappear as a bug (it already did once, caught by Henry's own eastern-ok run raising
# assert_competition_only on the wrongly-derived "transport_gap_defined").
TRANSPORT_DEFINED_COLUMN = "transport_defined"
BUILDING_GAP_COLUMN = "building_gap_centroid"  # Stage 7 Step 6 Tier A calibration result: centroid
# beat intersection in both the isolated south-central-tx test (0.00015295 -> 0.00014674) and the
# mandatory all-region cross-region confirmation (-> 0.000145067). See
# docs/scoring_assumptions.md entry #2 and docs/decision_log.md's Tier A section.
POI_SUBPART_COLUMNS = ("poi_gap_fire", "poi_gap_ems", "poi_gap_schools", "poi_gap_establishments")
# poi_gap is a NESTED two-stage mean, not a flat mean of all four sub-parts -- confirmed by the
# challenge's own README: "poi_gap_hifld is the mean over the defined types... The CBP half...
# is unchanged, and poi_gap is the mean of the two halves." HIFLD_SUBPART_COLUMNS form one half
# (their own internal mean, poi_gap_hifld); CBP is the other half, on its own. The two halves are
# then meaned together -- giving CBP roughly 2x-3x the weight a flat four-way mean would give it
# whenever 2 or 3 HIFLD types are defined alongside CBP for the same tract. Found via source-driven
# verification against the README (not a leaderboard result) after Step 3's original implementation
# used a flat mean -- see docs/decision_log.md for the discovery and docs/scoring_assumptions.md
# for the corrected, README-confirmed status.
# Derived from POI_SUBPART_COLUMNS (not restated) so the two can never silently drift apart --
# the exact failure mode already seen once on this project (transport_gap_defined vs.
# transport_defined). POI_SUBPART_COLUMNS' own order (fire, ems, schools, establishments) is load-
# bearing here: the first three are the HIFLD half, the last is CBP.
HIFLD_SUBPART_COLUMNS = POI_SUBPART_COLUMNS[:3]
CBP_COLUMN = POI_SUBPART_COLUMNS[3]


def capped_ratio_gap(overture: float, reference: float) -> float | None:
    """The challenge's capped-ratio gap formula: ``1 - min(1, overture / reference)``.

    Returns ``None`` (not ``0.0``) when ``reference == 0`` — there is nothing to compare against,
    so the value is undefined, not "fully covered". This is R-005 from the risk register: an
    undefined component must be excluded from `coverage_gap_score`'s mean entirely, never silently
    zeroed. Callers must not coerce this ``None`` into a number.

    The ratio is capped at 1 before subtracting, so a tract where Overture reports MORE than the
    reference (overture > reference) still floors at gap 0.0 — never negative.

    Not called from `score_region` below: Stage 6 already applied this exact formula when it
    materialized `transport_gap`/`building_gap_*`/`poi_gap_*` (src/schemas.py's `_GAP_RATIO_COLUMNS`
    comment: "every one is a `_capped_ratio` output"). This function exists so
    `tests/test_gap_arithmetic.py` can lock down the formula's edge cases independently of Stage 6's
    own implementation, and so a human reader has one place that states the formula in code."""
    if reference == 0:
        return None
    return 1 - min(1.0, overture / reference)


def coverage_gap_score(components: dict[str, float | None]) -> float | None:
    """The composite score: the arithmetic mean of only the DEFINED component gap values —
    ``None`` or NaN both count as undefined (``pd.notna`` covers real pandas data, which stores
    "undefined" as NaN, not the ``None`` this function's own unit tests use). Divisor is however
    many components are defined (1, 2, or 3) — never a fixed 3, and an undefined component is
    excluded, not treated as 0. Returns ``None`` if every component is undefined for that tract."""
    defined = [v for v in components.values() if pd.notna(v)]
    if not defined:
        return None
    return sum(defined) / len(defined)


def _poi_gap_for_row(row: pd.Series) -> tuple[float | None, bool]:
    """`poi_gap`'s NESTED half-definedness rule, per the challenge README (see
    `HIFLD_SUBPART_COLUMNS`'s comment above for the exact quote): `poi_gap_hifld` is the mean of
    whichever of {fire, ems, schools} are defined for this tract; `poi_gap` is then the mean of
    `poi_gap_hifld` and the CBP-establishments value, with either half excluded from that outer
    mean if it's undefined. This is NOT a flat mean of all four sub-parts -- that flat-mean
    version was this function's original, incorrect implementation (caught via source-driven
    verification against the README, not a test or a leaderboard result -- see
    `tests/test_gap_arithmetic.py`'s `test_poi_gap_uses_nested_mean_not_flat_mean_...` for the
    regression test this fix must pass). Uses each sub-part's own `<col>_defined` boolean, not a
    bare `notna()` check on the value (Stage 6's placeholder convention stores a numeric 0 even
    for undefined sub-parts, per the real sample-submission template: `poi_gap_ems=0` with
    `poi_defined_ems=FALSE` is a real row in `SampleSubmission 3.csv`).

    Returns `(poi_gap, poi_defined)` -- `poi_defined` is True iff at least one of the two halves
    is defined, matching the template's own separate `poi_defined` column (distinct from
    `poi_defined_fire`/`poi_defined_ems`/`poi_defined_schools`/`poi_defined_cbp`)."""
    hifld_defined_values = [
        row[col] for col in HIFLD_SUBPART_COLUMNS if bool(row[f"{col}_defined"])
    ]
    poi_gap_hifld = (
        sum(hifld_defined_values) / len(hifld_defined_values) if hifld_defined_values else None
    )

    poi_gap_cbp = row[CBP_COLUMN] if bool(row[f"{CBP_COLUMN}_defined"]) else None

    halves = [v for v in (poi_gap_hifld, poi_gap_cbp) if pd.notna(v)]
    if not halves:
        return None, False
    return sum(halves) / len(halves), True


def score_region(
    tract_features: pd.DataFrame, *, building_gap_column: str = BUILDING_GAP_COLUMN
) -> pd.DataFrame:
    """Scores one region's Stage 6 tract-features table. Returns a tidy per-tract table:
    `GEOID`, `region`, each component gap + its `_defined` flag, and `coverage_gap_score`.

    `building_gap_column` -- Stage 7 Step 6 (Tier A calibration): which of the two Stage-6
    building-assignment candidates (`building_gap_centroid` or `building_gap_intersection`) to
    use for THIS call. Defaults to `BUILDING_GAP_COLUMN` (the current best-trusted default, not
    yet frozen) so every existing caller is unaffected; `scripts/tier_a_calibration.py` is the
    only caller that passes a non-default value, one region at a time, per the designed-experiment
    protocol (three regions held fixed, one varied). Both candidates are already in
    `src.schemas.COMPETITION_ALLOWED_COLUMNS` -- no schema change needed to support this.

    Calls `assert_competition_only` first, naming every Stage-6 column this function reads -- the
    fail-closed gate raises before any real computation if a column isn't in
    `src.schemas.COMPETITION_ALLOWED_COLUMNS`, catching a typo'd or not-yet-allowed column name
    before it can influence a score."""
    columns_used = {
        TRANSPORT_GAP_COLUMN,
        TRANSPORT_DEFINED_COLUMN,
        building_gap_column,
        f"{building_gap_column}_defined",
        *POI_SUBPART_COLUMNS,
        *(f"{c}_defined" for c in POI_SUBPART_COLUMNS),
    }
    assert_competition_only(columns_used)

    out = pd.DataFrame(
        {"GEOID": tract_features["GEOID"], "region": tract_features["region"]}
    )
    out["transport_gap"] = tract_features[TRANSPORT_GAP_COLUMN]
    out["transport_defined"] = tract_features[TRANSPORT_DEFINED_COLUMN]
    out["building_gap"] = tract_features[building_gap_column]
    out["building_defined"] = tract_features[f"{building_gap_column}_defined"]

    poi_results = tract_features.apply(_poi_gap_for_row, axis=1, result_type="expand")
    out["poi_gap"] = poi_results[0]
    out["poi_defined"] = poi_results[1]
    # Also carry the four POI sub-part columns through -- already in COMPETITION_ALLOWED_COLUMNS
    # and already read above (columns_used), Step 5's build_submission.py needs them as their own
    # template columns (poi_gap_fire/ems/schools/cbp), not just folded into the poi_gap mean.
    for col in POI_SUBPART_COLUMNS:
        out[col] = tract_features[col]
        out[f"{col}_defined"] = tract_features[f"{col}_defined"]

    out["coverage_gap_score"] = out.apply(
        lambda r: coverage_gap_score(
            {
                "transport_gap": r["transport_gap"],
                "building_gap": r["building_gap"],
                "poi_gap": r["poi_gap"],
            }
        ),
        axis=1,
    )
    return out


def score_all_regions(
    regions: list[str] = REGIONS,
    *,
    building_gap_overrides: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Reads every region's `data/processed/<region>-tract-features.parquet` and returns one
    concatenated scored table across all four regions.

    `building_gap_overrides` -- Stage 7 Step 6 Tier A calibration: an optional `{region:
    building_gap_column}` mapping. A region present in the mapping is scored with that building-
    assignment column instead of `BUILDING_GAP_COLUMN`'s default; every region absent from the
    mapping (or when the mapping itself is omitted) keeps the default -- this is exactly the
    "three regions held fixed, one varied" shape the designed-experiment protocol needs, and the
    "flip every region at once" cross-region-confirmation shape (pass all four regions in the
    mapping) with the same parameter."""
    overrides = building_gap_overrides or {}
    frames = []
    for region in regions:
        path = PROCESSED_DIR / f"{region}-tract-features.parquet"
        tract_features = pd.read_parquet(path)
        building_gap_column = overrides.get(region, BUILDING_GAP_COLUMN)
        frames.append(score_region(tract_features, building_gap_column=building_gap_column))
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    # ---------------------------------------------------------------------------------------
    # Step 3 sanity check against real data, eastern-ok first (smallest region) -- row count,
    # value range [0,1], no unexpected nulls. Not a substitute for Step 4's any-of-three-undefined
    # self-check (a different, published statistic); this only confirms the pipeline runs end to
    # end and produces sane output before spending it on all four regions.
    # ---------------------------------------------------------------------------------------
    eastern_ok = pd.read_parquet(PROCESSED_DIR / "eastern-ok-tract-features.parquet")
    scored = score_region(eastern_ok)
    print(f"eastern-ok: {len(scored)} rows scored")
    assert len(scored) == 1192, f"expected 1192 rows, got {len(scored)}"

    for col in ("transport_gap", "building_gap", "poi_gap", "coverage_gap_score"):
        defined_values = scored[col].dropna()
        assert len(defined_values) > 0, f"{col}: no defined values at all -- pipeline is broken"
        assert defined_values.between(0.0, 1.0).all(), (
            f"{col}: values outside [0,1] found -- {defined_values[~defined_values.between(0, 1)].tolist()}"
        )
    assert scored["coverage_gap_score"].isna().sum() == 0, (
        "eastern-ok has at least one component defined for every tract in practice (published "
        "any-of-three-undefined rate is 21%, not 100%), so coverage_gap_score should never be "
        "all-undefined for a real tract here -- investigate if this fires"
    )
    print("eastern-ok: PASS (row count, [0,1] range, no fully-undefined tracts)")

    all_regions = score_all_regions()
    print(f"all regions: {len(all_regions)} rows scored")
    for region, expected_n in {
        "eastern-ok": 1192,
        "maricopa-az": 1593,
        "northern-ca": 591,
        "south-central-tx": 6010,
    }.items():
        n = (all_regions["region"] == region).sum()
        assert n == expected_n, f"{region}: expected {expected_n} rows, got {n}"
    print("All Stage 7 Step 3 self-checks passed.")
