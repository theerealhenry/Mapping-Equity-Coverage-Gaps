"""
tests/test_gap_arithmetic.py — Stage 7 Step 2 golden-case fixture suite (tier 1 of 2).

Hand-computed edge cases for the capped-ratio gap formula and the coverage_gap_score mean, per
`claude/stage7-reference-reconstruction-engine-guideline.md` Step 2. Locks down R-005 (an undefined
component is excluded from the mean entirely, never zeroed) before src/gaps.py's real pipeline is
ever run against real region data. Every expected value is computed by hand in the comment next to
its assertion, not just asserted as a bare number.
"""

import pandas as pd
import pytest

from src.gaps import _poi_gap_for_row, capped_ratio_gap, coverage_gap_score, score_region


def test_overture_zero_gives_full_gap():
    # 1 - min(1, 0/100) = 1 - 0 = 1.0
    assert capped_ratio_gap(overture=0, reference=100) == 1.0


def test_overture_equals_reference_gives_zero_gap():
    # 1 - min(1, 100/100) = 1 - 1 = 0.0
    assert capped_ratio_gap(overture=100, reference=100) == 0.0


def test_overture_exceeds_reference_caps_at_zero_not_negative():
    # raw ratio 150/100 = 1.5 -> min(1, 1.5) = 1 -> 1 - 1 = 0.0. Must never go negative.
    assert capped_ratio_gap(overture=150, reference=100) == 0.0


def test_reference_zero_is_undefined_not_zeroed():
    # R-005: reference=0 means there's nothing to compare against -> None, excluded from the
    # coverage_gap_score mean entirely. Never silently coerced to 0.0 ("fully covered").
    assert capped_ratio_gap(overture=0, reference=0) is None
    assert capped_ratio_gap(overture=5, reference=0) is None


def test_fractional_overture_matches_exact_ratio_arithmetic():
    # 1 - min(1, 30/40) = 1 - 0.75 = 0.25
    assert capped_ratio_gap(overture=30, reference=40) == 0.25


def test_coverage_gap_score_means_only_defined_components():
    # transport=0.25, building=0.75, poi=undefined(None)
    # -> mean of the two DEFINED values only: (0.25 + 0.75) / 2 = 0.5, denominator 2 not 3.
    score = coverage_gap_score({"transport_gap": 0.25, "building_gap": 0.75, "poi_gap": None})
    assert score == 0.5


def test_coverage_gap_score_all_defined_uses_denominator_three():
    # (0.2 + 0.4 + 0.6) / 3 = 0.4 -- float division, compare with tolerance not `==`
    score = coverage_gap_score({"transport_gap": 0.2, "building_gap": 0.4, "poi_gap": 0.6})
    assert score == pytest.approx(0.4)


def test_coverage_gap_score_all_undefined_is_none():
    score = coverage_gap_score({"transport_gap": None, "building_gap": None, "poi_gap": None})
    assert score is None


def test_poi_gap_uses_nested_mean_not_flat_mean_when_hifld_and_cbp_both_defined():
    # README: "poi_gap_hifld is the mean over the defined [HIFLD] types... poi_gap is the mean
    # of the two halves." This is a NESTED two-stage mean, not a flat mean of all four sub-parts.
    # hifld_mean = mean(0.2, 0.4, 0.6) = 0.4; poi_gap = mean(hifld_mean, cbp) = mean(0.4, 0.8) = 0.6
    # A flat mean of all four (the original, incorrect implementation) would instead give 0.5 --
    # this assertion is what catches that regression.
    row = pd.Series({
        "poi_gap_fire": 0.2, "poi_gap_fire_defined": True,
        "poi_gap_ems": 0.4, "poi_gap_ems_defined": True,
        "poi_gap_schools": 0.6, "poi_gap_schools_defined": True,
        "poi_gap_establishments": 0.8, "poi_gap_establishments_defined": True,
    })
    poi_gap, poi_defined = _poi_gap_for_row(row)
    assert poi_defined is True
    assert poi_gap == pytest.approx(0.6)


def test_poi_gap_single_defined_subpart_matches_flat_and_nested_alike():
    # Sanity check: when only one sub-part is defined, flat mean and nested mean agree by
    # construction (mean of one value either way) -- confirms the fix doesn't change this case.
    row = pd.Series({
        "poi_gap_fire": 0.3, "poi_gap_fire_defined": True,
        "poi_gap_ems": 0.0, "poi_gap_ems_defined": False,
        "poi_gap_schools": 0.0, "poi_gap_schools_defined": False,
        "poi_gap_establishments": 0.0, "poi_gap_establishments_defined": False,
    })
    poi_gap, poi_defined = _poi_gap_for_row(row)
    assert poi_defined is True
    assert poi_gap == pytest.approx(0.3)


def test_poi_gap_cbp_only_matches_flat_and_nested_alike():
    # Symmetric to the single-HIFLD-subpart case above: CBP defined, no HIFLD types defined at
    # all. Both formulas agree here too (mean of one value either way).
    row = pd.Series({
        "poi_gap_fire": 0.0, "poi_gap_fire_defined": False,
        "poi_gap_ems": 0.0, "poi_gap_ems_defined": False,
        "poi_gap_schools": 0.0, "poi_gap_schools_defined": False,
        "poi_gap_establishments": 0.7, "poi_gap_establishments_defined": True,
    })
    poi_gap, poi_defined = _poi_gap_for_row(row)
    assert poi_defined is True
    assert poi_gap == pytest.approx(0.7)


def test_poi_gap_none_defined_is_undefined():
    row = pd.Series({
        "poi_gap_fire": 0.0, "poi_gap_fire_defined": False,
        "poi_gap_ems": 0.0, "poi_gap_ems_defined": False,
        "poi_gap_schools": 0.0, "poi_gap_schools_defined": False,
        "poi_gap_establishments": 0.0, "poi_gap_establishments_defined": False,
    })
    poi_gap, poi_defined = _poi_gap_for_row(row)
    assert poi_gap is None
    assert poi_defined is False


def _synthetic_tract_features() -> pd.DataFrame:
    # One row with deliberately different centroid vs. intersection values, so a test can tell
    # which column score_region actually read from.
    return pd.DataFrame([{
        "GEOID": "12345678900",
        "region": "eastern-ok",
        "transport_gap": 0.1, "transport_defined": True,
        "building_gap_centroid": 0.3, "building_gap_centroid_defined": True,
        "building_gap_intersection": 0.9, "building_gap_intersection_defined": True,
        "poi_gap_fire": 0.5, "poi_gap_fire_defined": True,
        "poi_gap_ems": 0.5, "poi_gap_ems_defined": True,
        "poi_gap_schools": 0.5, "poi_gap_schools_defined": True,
        "poi_gap_establishments": 0.5, "poi_gap_establishments_defined": True,
    }])


def test_score_region_defaults_to_centroid_building_column():
    # Stage 7 Step 6: score_region's building_gap_column defaults to gaps.BUILDING_GAP_COLUMN,
    # which Tier A calibration settled on "building_gap_centroid" -- isolated-region and
    # cross-region-confirmed RMSE wins over the prior intersection default (see
    # docs/scoring_assumptions.md entry #2).
    out = score_region(_synthetic_tract_features())
    assert out.loc[0, "building_gap"] == pytest.approx(0.3)


def test_score_region_honors_building_gap_column_override():
    # Stage 7 Step 6: scripts/tier_a_calibration.py's whole mechanism depends on this override
    # actually changing which Stage-6 column feeds building_gap.
    out = score_region(_synthetic_tract_features(), building_gap_column="building_gap_intersection")
    assert out.loc[0, "building_gap"] == pytest.approx(0.9)
