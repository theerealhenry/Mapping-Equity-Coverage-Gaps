"""
tests/test_gap_arithmetic.py — Stage 7 Step 2 golden-case fixture suite (tier 1 of 2).

Hand-computed edge cases for the capped-ratio gap formula and the coverage_gap_score mean, per
`claude/stage7-reference-reconstruction-engine-guideline.md` Step 2. Locks down R-005 (an undefined
component is excluded from the mean entirely, never zeroed) before src/gaps.py's real pipeline is
ever run against real region data. Every expected value is computed by hand in the comment next to
its assertion, not just asserted as a bare number.
"""

import pytest

from src.gaps import capped_ratio_gap, coverage_gap_score


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
