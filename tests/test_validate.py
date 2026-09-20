"""
tests/test_validate.py — Stage 7 Step 5 TDD fixture for src/validate.py's submission validator.

A minimal valid 3-row fixture (standing in for the real 9,379-row manifest) proves the validator
accepts a clean submission and rejects each deliberately-broken variant of it, one wrong row at a
time -- row count, GEOID mismatch, a blank cell, and an out-of-range value, per this step's own
"deliberately-wrong row" requirement.
"""

import pandas as pd
import pytest

from src.validate import REQUIRED_COLUMNS, validate_submission

_MANIFEST = pd.DataFrame({"GEOID": ["A", "B", "C"], "region": ["r1", "r1", "r2"]})


def _valid_submission() -> pd.DataFrame:
    filler = {c: 0.5 for c in REQUIRED_COLUMNS if c not in ("GEOID", "region")}
    return pd.DataFrame(
        [
            {**filler, "GEOID": "A", "region": "r1"},
            {**filler, "GEOID": "B", "region": "r1"},
            {**filler, "GEOID": "C", "region": "r2"},
        ]
    )


def test_clean_submission_passes():
    validate_submission(_valid_submission(), manifest=_MANIFEST)  # must not raise


def test_missing_column_fails():
    bad = _valid_submission().drop(columns=["poi_gap_cbp"])
    with pytest.raises(ValueError, match="missing required column"):
        validate_submission(bad, manifest=_MANIFEST)


def test_wrong_row_count_fails():
    bad = _valid_submission().iloc[:2]
    with pytest.raises(ValueError, match="row count"):
        validate_submission(bad, manifest=_MANIFEST)


def test_geoid_mismatch_fails():
    bad = _valid_submission()
    bad.loc[0, "GEOID"] = "Z"  # not in the manifest -- row count stays 3, only GEOID set changes
    with pytest.raises(ValueError, match="GEOID set"):
        validate_submission(bad, manifest=_MANIFEST)


def test_blank_cell_fails():
    bad = _valid_submission()
    bad.loc[0, "coverage_gap_score"] = None
    with pytest.raises(ValueError, match="blank cell"):
        validate_submission(bad, manifest=_MANIFEST)


def test_out_of_range_value_fails():
    bad = _valid_submission()
    bad.loc[0, "coverage_gap_score"] = 1.5
    with pytest.raises(ValueError, match=r"outside \[0, 1\]"):
        validate_submission(bad, manifest=_MANIFEST)
