"""Tests for scripts/check_nchs_reclassification.py.

Every pure function here is tested against small, hand-built fixtures — no network. The one thing
this test file cannot cover is whether CDC's real crosswalk file's actual column names match what
`load_nchs_crosswalk` assumes (STFIPS, CTYFIPS, CODE2013, CODE2023) — that assumption comes from
CDC's own published documentation, not from having fetched and inspected the raw file directly (no
network access to cdc.gov was available while building this), and is the one thing Henry's real run
against the live file will confirm or correct.
"""

from __future__ import annotations

import pandas as pd
import pytest

import scripts.check_nchs_reclassification as mod


# --- derive_county_fips -----------------------------------------------------------------------


def test_derive_county_fips_takes_the_first_five_digits():
    assert mod.derive_county_fips("04013110100") == "04013"


def test_derive_county_fips_handles_the_maricopa_package_new_mexico_tract():
    """The known real edge case from Stage 2 (docs/data_manifest.md Section 4.8/4.9): the Maricopa
    package includes one New Mexico tract, 35023970000 (Hidalgo County). Its county FIPS must derive
    correctly like any other tract's — no special-casing anywhere in this script."""
    assert mod.derive_county_fips("35023970000") == "35023"


def test_derive_county_fips_rejects_a_too_short_geoid():
    with pytest.raises(ValueError):
        mod.derive_county_fips("123")


# --- normalize_state_county_fips ---------------------------------------------------------------


def test_normalize_state_county_fips_zero_pads_small_integers():
    assert mod.normalize_state_county_fips(4, 13) == "04013"


def test_normalize_state_county_fips_handles_already_correct_values():
    assert mod.normalize_state_county_fips(48, 29) == "48029"


def test_normalize_state_county_fips_handles_float_like_input():
    """pandas often reads a numeric CSV column as float64 even when every value is a whole number —
    this must still produce the correct zero-padded string, not '4.0counties' or similar."""
    assert mod.normalize_state_county_fips(4.0, 13.0) == "04013"


# --- find_reclassified_counties -----------------------------------------------------------------


@pytest.fixture
def toy_crosswalk() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "county_fips": ["04013", "48029", "40001"],
            "CODE2013": [2, 3, 6],
            "CODE2023": [2, 4, 6],  # 48029 changed, the other two did not
        }
    )


def test_flags_a_county_whose_code_actually_changed(toy_crosswalk):
    """Uses == rather than `is` throughout: pandas hands back numpy bool_ scalars from a DataFrame
    built via pd.DataFrame.from_records, which are == True/False but not `is` Python's singletons —
    an early version of this test file got this wrong (found and fixed during its own first run,
    not a bug in the script itself, whose own main() already used the `== True` idiom throughout,
    matching Step 3's established convention)."""
    result = mod.find_reclassified_counties(toy_crosswalk, {"48029"}, region="test-region")
    row = result.iloc[0]
    assert bool(row["found_in_crosswalk"]) == True  # noqa: E712
    assert row["code_2013"] == 3
    assert row["code_2023"] == 4
    assert row["meaning_2013"] == "Medium metro"
    assert row["meaning_2023"] == "Small metro"
    assert bool(row["reclassified"]) == True  # noqa: E712


def test_does_not_flag_a_county_whose_code_is_unchanged(toy_crosswalk):
    result = mod.find_reclassified_counties(toy_crosswalk, {"04013"}, region="test-region")
    assert bool(result.iloc[0]["reclassified"]) == False  # noqa: E712


def test_reports_a_county_not_present_in_the_crosswalk_rather_than_dropping_it_silently(toy_crosswalk):
    result = mod.find_reclassified_counties(toy_crosswalk, {"99999"}, region="test-region")
    row = result.iloc[0]
    assert bool(row["found_in_crosswalk"]) == False  # noqa: E712
    assert row["reclassified"] is None or pd.isna(row["reclassified"])
    assert pd.isna(row["code_2013"])


def test_checks_every_county_in_the_given_set_independently(toy_crosswalk):
    result = mod.find_reclassified_counties(toy_crosswalk, {"04013", "48029", "40001"}, region="r")
    assert len(result) == 3
    reclassified_fips = set(result.loc[result["reclassified"] == True, "county_fips"])  # noqa: E712
    assert reclassified_fips == {"48029"}


# --- load_nchs_crosswalk -------------------------------------------------------------------------


def test_load_nchs_crosswalk_adds_a_normalized_county_fips_column(tmp_path):
    csv_path = tmp_path / "crosswalk.csv"
    pd.DataFrame(
        {
            "STFIPS": [4, 48],
            "CTYFIPS": [13, 29],
            "ST_ABBREV": ["AZ", "TX"],
            "CTYNAME": ["Maricopa County", "Bexar County"],
            "CODE2013": [2, 3],
            "CODE2023": [2, 4],
        }
    ).to_csv(csv_path, index=False)

    result = mod.load_nchs_crosswalk(str(csv_path))
    assert list(result["county_fips"]) == ["04013", "48029"]


def test_load_nchs_crosswalk_raises_a_clear_error_on_unexpected_columns(tmp_path):
    csv_path = tmp_path / "crosswalk.csv"
    pd.DataFrame({"totally_different_columns": [1, 2]}).to_csv(csv_path, index=False)

    with pytest.raises(RuntimeError, match="missing expected column"):
        mod.load_nchs_crosswalk(str(csv_path))


# --- main() ---------------------------------------------------------------------------------


def test_main_reports_zero_reclassified_and_recommends_dropping_the_claim(tmp_path, monkeypatch, capsys):
    crosswalk_path = tmp_path / "crosswalk.csv"
    pd.DataFrame(
        {
            "STFIPS": [4],
            "CTYFIPS": [13],
            "CODE2013": [2],
            "CODE2023": [2],
        }
    ).to_csv(crosswalk_path, index=False)

    monkeypatch.setattr(mod, "REGIONS", ["fake-region"])
    monkeypatch.setattr(
        mod,
        "load_sample_submission",
        lambda region: pd.DataFrame({"GEOID": ["04013110100", "04013110200"]}),
    )

    rc = mod.main(
        [
            "--crosswalk-source", str(crosswalk_path),
            "--output", str(tmp_path / "results.csv"),
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "DROPPED" in stdout
    written = pd.read_csv(tmp_path / "results.csv")
    assert len(written) == 1
    assert written.iloc[0]["reclassified"] == False  # noqa: E712


def test_main_reports_a_real_reclassification_and_does_not_recommend_dropping(tmp_path, monkeypatch, capsys):
    crosswalk_path = tmp_path / "crosswalk.csv"
    pd.DataFrame(
        {
            "STFIPS": [48],
            "CTYFIPS": [29],
            "CODE2013": [3],
            "CODE2023": [4],
        }
    ).to_csv(crosswalk_path, index=False)

    monkeypatch.setattr(mod, "REGIONS", ["fake-region"])
    monkeypatch.setattr(
        mod,
        "load_sample_submission",
        lambda region: pd.DataFrame({"GEOID": ["48029110100"]}),
    )

    rc = mod.main(
        [
            "--crosswalk-source", str(crosswalk_path),
            "--output", str(tmp_path / "results.csv"),
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "DROPPED" not in stdout
    assert "genuine, quantifiable" in stdout


def test_main_returns_a_clean_error_when_the_crosswalk_cannot_be_loaded(tmp_path, capsys):
    rc = mod.main(
        [
            "--crosswalk-source", str(tmp_path / "does_not_exist.csv"),
            "--output", str(tmp_path / "results.csv"),
        ]
    )
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err
