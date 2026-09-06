"""Tests for scripts/classify_columns.py (Stage 3 Step 5).

This step needs no live bucket access — every input is already committed, real data from Steps 2-4
(docs/column_domain_map.csv, docs/coverage_null_profile.csv, and
scripts.confirm_domain_vintages.VINTAGE_COLUMNS_BY_SOURCE_TABLE). Every function is tested against
small, hand-built fixtures AND, where the real committed files are present, against the real 232-
column data itself — this step's most important guarantees (allowed_for_scoring is False everywhere,
every zero-variance column is caught) are exactly the kind of thing that must be verified against the
real data, not just a fixture that might not represent it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import scripts.classify_columns as mod

REAL_DOMAIN_MAP_CSV = Path(__file__).resolve().parent.parent / "docs" / "column_domain_map.csv"
REAL_NULL_PROFILE_CSV = Path(__file__).resolve().parent.parent / "docs" / "coverage_null_profile.csv"
REAL_INPUTS_PRESENT = REAL_DOMAIN_MAP_CSV.exists() and REAL_NULL_PROFILE_CSV.exists()


# --- classify_role ---------------------------------------------------------------------------


def test_identifier_columns_are_classified_as_identifier():
    for column in mod.IDENTIFIER_COLUMNS:
        assert mod.classify_role(column, vintage_columns=set()) == mod.ROLE_IDENTIFIER


def test_geometry_measure_columns_are_classified_correctly():
    for column in mod.GEOMETRY_MEASURE_COLUMNS:
        assert mod.classify_role(column, vintage_columns=set()) == mod.ROLE_GEOMETRY_MEASURE


def test_population_columns_are_classified_correctly():
    for column in mod.POPULATION_COLUMNS:
        assert mod.classify_role(column, vintage_columns=set()) == mod.ROLE_POPULATION


def test_a_column_in_the_passed_in_vintage_set_is_classified_as_vintage_metadata():
    assert mod.classify_role("some_made_up_vintage_col", vintage_columns={"some_made_up_vintage_col"}) == mod.ROLE_VINTAGE_METADATA


def test_a_column_ending_in_covered_is_classified_as_coverage_flag():
    assert mod.classify_role("svi_covered", vintage_columns=set()) == mod.ROLE_COVERAGE_FLAG


def test_ever_flag_columns_are_classified_correctly():
    for column in mod.EVER_FLAG_COLUMNS:
        assert mod.classify_role(column, vintage_columns=set()) == mod.ROLE_DERIVED_EVER_FLAG


def test_identity_metadata_columns_are_classified_correctly():
    for column in mod.IDENTITY_METADATA_COLUMNS:
        assert mod.classify_role(column, vintage_columns=set()) == mod.ROLE_IDENTITY_METADATA


def test_an_unmatched_column_defaults_to_measurement():
    assert mod.classify_role("svi_theme1_pctile", vintage_columns=set()) == mod.ROLE_MEASUREMENT


def test_identity_metadata_wins_over_vintage_membership():
    """Regression for a real bug caught on this step's first real run: uhe_city_name/
    uhe_city_country are members of Step 4's VINTAGE_COLUMNS_BY_SOURCE_TABLE (added there so its
    extraction script would pull their live values while investigating the "uhe" dataset's identity)
    but are NOT genuine vintage/edition/methodology metadata — they identify which external city a
    tract was matched to. IDENTITY_METADATA_COLUMNS must be checked before vintage_columns so this
    kind of cross-step list reuse can never leak the wrong role."""
    for column in mod.IDENTITY_METADATA_COLUMNS:
        result = mod.classify_role(column, vintage_columns={column})  # deliberately ALSO "vintage"
        assert result == mod.ROLE_IDENTITY_METADATA, f"{column} should stay identity_metadata even if also in vintage_columns"


def test_priority_order_vintage_membership_beats_the_covered_suffix_check():
    """A column could in principle end in "_covered" AND be listed as vintage metadata (not true of
    any real column today, but the priority order should still be deterministic and documented, not
    accidental) — vintage membership is checked first in classify_role, so it must win."""
    result = mod.classify_role("weird_covered", vintage_columns={"weird_covered"})
    assert result == mod.ROLE_VINTAGE_METADATA


# --- compute_allowed_for_bias -----------------------------------------------------------------


def test_zero_variance_forces_allowed_for_bias_false_regardless_of_role():
    """The hard override: even a role that would otherwise default to True (measurement, coverage
    flag, population, geometry) must be forced to False when n_distinct <= 1."""
    for role in [
        mod.ROLE_MEASUREMENT,
        mod.ROLE_COVERAGE_FLAG,
        mod.ROLE_POPULATION,
        mod.ROLE_GEOMETRY_MEASURE,
        mod.ROLE_DERIVED_EVER_FLAG,
        mod.ROLE_IDENTITY_METADATA,
    ]:
        allowed, reason = mod.compute_allowed_for_bias(role, n_distinct=1)
        assert allowed is False, f"role={role} should be forced False at n_distinct=1"
        assert "constant" in reason

    allowed, reason = mod.compute_allowed_for_bias(mod.ROLE_MEASUREMENT, n_distinct=0)
    assert allowed is False
    assert "constant" in reason


def test_vintage_metadata_is_never_allowed_for_bias_even_with_real_variance():
    """Should be unreachable against the real data (every real vintage column is n_distinct<=1
    nationally, confirmed by the real-data regression test below), but the rule must hold on its own
    logic, not just by accident of the current data."""
    allowed, reason = mod.compute_allowed_for_bias(mod.ROLE_VINTAGE_METADATA, n_distinct=5)
    assert allowed is False
    assert "methodology" in reason


def test_identifier_role_is_not_allowed_for_bias():
    allowed, _ = mod.compute_allowed_for_bias(mod.ROLE_IDENTIFIER, n_distinct=52)
    assert allowed is False


@pytest.mark.parametrize(
    "role",
    [
        mod.ROLE_GEOMETRY_MEASURE,
        mod.ROLE_POPULATION,
        mod.ROLE_COVERAGE_FLAG,
        mod.ROLE_DERIVED_EVER_FLAG,
        mod.ROLE_IDENTITY_METADATA,
        mod.ROLE_MEASUREMENT,
    ],
)
def test_these_roles_default_to_allowed_for_bias_true_when_variance_exists(role):
    allowed, _ = mod.compute_allowed_for_bias(role, n_distinct=10)
    assert allowed is True


def test_ever_flag_reason_names_the_pairing_caveat():
    _, reason = mod.compute_allowed_for_bias(mod.ROLE_DERIVED_EVER_FLAG, n_distinct=2)
    assert "_covered" in reason


# --- build_classification ---------------------------------------------------------------------


def test_build_classification_produces_one_row_per_domain_map_row():
    domain_map = pd.DataFrame(
        [
            ("GEOID", "national-census-tract-table", "geography", "string"),
            ("svi_year", "national-svi-tract-table", "svi", "int64"),
            ("svi_theme1_pctile", "national-svi-tract-table", "svi", "double"),
        ],
        columns=["column_name", "source_table", "domain", "dtype"],
    )
    national_profile = pd.DataFrame(
        {
            "column_name": ["GEOID", "svi_year", "svi_theme1_pctile"],
            "n_distinct": [85396, 1, 20000],
        }
    )
    result = mod.build_classification(domain_map, national_profile, vintage_columns={"svi_year"})

    assert len(result) == 3
    geoid_row = result.loc[result["column_name"] == "GEOID"].iloc[0]
    assert geoid_row["role"] == mod.ROLE_IDENTIFIER
    assert geoid_row["allowed_for_scoring"] == False  # noqa: E712
    assert geoid_row["allowed_for_bias"] == False  # noqa: E712

    svi_year_row = result.loc[result["column_name"] == "svi_year"].iloc[0]
    assert svi_year_row["role"] == mod.ROLE_VINTAGE_METADATA
    assert svi_year_row["allowed_for_bias"] == False  # noqa: E712

    measurement_row = result.loc[result["column_name"] == "svi_theme1_pctile"].iloc[0]
    assert measurement_row["role"] == mod.ROLE_MEASUREMENT
    assert measurement_row["allowed_for_bias"] == True  # noqa: E712


def test_build_classification_allowed_for_scoring_is_always_false():
    domain_map = pd.DataFrame(
        [("a", "t", "d", "int64"), ("b", "t", "d", "int64")],
        columns=["column_name", "source_table", "domain", "dtype"],
    )
    national_profile = pd.DataFrame({"column_name": ["a", "b"], "n_distinct": [5, 5]})
    result = mod.build_classification(domain_map, national_profile, vintage_columns=set())
    assert (result["allowed_for_scoring"] == False).all()  # noqa: E712


# --- main() -------------------------------------------------------------------------------


def test_main_returns_a_clean_error_when_domain_map_is_missing(tmp_path, capsys):
    rc = mod.main(["--domain-map", str(tmp_path / "nope.csv"), "--null-profile", str(tmp_path / "nope2.csv")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_returns_a_clean_error_when_null_profile_is_missing(tmp_path, capsys):
    domain_map_csv = tmp_path / "domain_map.csv"
    pd.DataFrame([("a", "t", "d", "int64")], columns=["column_name", "source_table", "domain", "dtype"]).to_csv(domain_map_csv, index=False)

    rc = mod.main(["--domain-map", str(domain_map_csv), "--null-profile", str(tmp_path / "nope.csv")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_returns_a_clean_error_when_a_domain_map_column_has_no_national_profile_row(tmp_path, capsys):
    domain_map_csv = tmp_path / "domain_map.csv"
    pd.DataFrame(
        [("a", "t", "d", "int64"), ("missing_col", "t", "d", "int64")],
        columns=["column_name", "source_table", "domain", "dtype"],
    ).to_csv(domain_map_csv, index=False)

    profile_csv = tmp_path / "profile.csv"
    pd.DataFrame({"scope": ["national"], "column_name": ["a"], "n_distinct": [5]}).to_csv(profile_csv, index=False)

    rc = mod.main(["--domain-map", str(domain_map_csv), "--null-profile", str(profile_csv)])
    assert rc == 2
    assert "missing_col" in capsys.readouterr().err


def test_main_writes_the_classification_csv_and_returns_zero(tmp_path):
    domain_map_csv = tmp_path / "domain_map.csv"
    pd.DataFrame(
        [("GEOID", "t", "geography", "string"), ("svi_theme1_pctile", "t", "svi", "double")],
        columns=["column_name", "source_table", "domain", "dtype"],
    ).to_csv(domain_map_csv, index=False)

    profile_csv = tmp_path / "profile.csv"
    pd.DataFrame(
        {
            "scope": ["national", "national", "eastern-ok"],
            "column_name": ["GEOID", "svi_theme1_pctile", "GEOID"],
            "n_distinct": [85396, 20000, 1192],
        }
    ).to_csv(profile_csv, index=False)

    output_csv = tmp_path / "classification.csv"
    rc = mod.main(
        [
            "--domain-map", str(domain_map_csv),
            "--null-profile", str(profile_csv),
            "--output", str(output_csv),
        ]
    )
    assert rc == 0
    written = pd.read_csv(output_csv)
    assert len(written) == 2
    assert (written["allowed_for_scoring"] == False).all()  # noqa: E712


# --- Real-data regressions -----------------------------------------------------------------


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_produces_exactly_232_rows_and_zero_allowed_for_scoring():
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    profile = pd.read_csv(REAL_NULL_PROFILE_CSV)
    national_profile = profile.loc[profile["scope"] == "national"]
    from scripts.confirm_domain_vintages import all_vintage_columns

    result = mod.build_classification(domain_map, national_profile, set(all_vintage_columns()))
    assert len(result) == 232
    assert (result["allowed_for_scoring"] == False).all()  # noqa: E712


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_every_role_is_accounted_for_and_sums_to_232():
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    profile = pd.read_csv(REAL_NULL_PROFILE_CSV)
    national_profile = profile.loc[profile["scope"] == "national"]
    from scripts.confirm_domain_vintages import all_vintage_columns

    result = mod.build_classification(domain_map, national_profile, set(all_vintage_columns()))
    counts = result["role"].value_counts()
    assert counts.sum() == 232
    # Every one of the 8 defined roles must actually be used at least once against the real data —
    # a role that never fires would be dead code silently doing nothing.
    expected_roles = {
        mod.ROLE_IDENTIFIER,
        mod.ROLE_GEOMETRY_MEASURE,
        mod.ROLE_POPULATION,
        mod.ROLE_VINTAGE_METADATA,
        mod.ROLE_COVERAGE_FLAG,
        mod.ROLE_DERIVED_EVER_FLAG,
        mod.ROLE_IDENTITY_METADATA,
        mod.ROLE_MEASUREMENT,
    }
    assert set(counts.index) == expected_roles


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_every_vintage_metadata_column_is_actually_forced_to_allowed_for_bias_false():
    """Every column classified with role=vintage_metadata must be allowed_for_bias=False. Note this
    is NOT the same count as len(all_vintage_columns()) — uhe_city_name/uhe_city_country are members
    of that Step 4 list (for extraction-convenience reasons) but correctly get role=identity_metadata
    here instead (see test_identity_metadata_wins_over_vintage_membership), so the vintage_metadata
    role count is exactly two less than the raw vintage-column list's length."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    profile = pd.read_csv(REAL_NULL_PROFILE_CSV)
    national_profile = profile.loc[profile["scope"] == "national"]
    from scripts.confirm_domain_vintages import all_vintage_columns

    result = mod.build_classification(domain_map, national_profile, set(all_vintage_columns()))
    vintage_rows = result.loc[result["role"] == mod.ROLE_VINTAGE_METADATA]
    assert len(vintage_rows) == len(set(all_vintage_columns())) - len(mod.IDENTITY_METADATA_COLUMNS & set(all_vintage_columns()))
    assert (~vintage_rows["allowed_for_bias"]).all()

    identity_columns_also_in_vintage_list = mod.IDENTITY_METADATA_COLUMNS & set(all_vintage_columns())
    assert identity_columns_also_in_vintage_list == {"uhe_city_name", "uhe_city_country"}
    identity_rows = result.loc[result["column_name"].isin(identity_columns_also_in_vintage_list)]
    assert (identity_rows["role"] == mod.ROLE_IDENTITY_METADATA).all()


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_known_zero_variance_flags_are_forced_false():
    """Locks in Step 3 Finding 4 (rucc_covered/ghcn_covered always True nationally) as a permanent
    regression against the real data, via this step's own independent n_distinct check rather than
    trusting the earlier finding was transcribed correctly."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    profile = pd.read_csv(REAL_NULL_PROFILE_CSV)
    national_profile = profile.loc[profile["scope"] == "national"]
    from scripts.confirm_domain_vintages import all_vintage_columns

    result = mod.build_classification(domain_map, national_profile, set(all_vintage_columns()))
    by_column = result.set_index("column_name")
    for column in ["rucc_covered", "ghcn_covered", "hwd_maxtemp_never_defined", "spi_calibration"]:
        assert by_column.loc[column, "allowed_for_bias"] == False, f"{column} should be forced False"  # noqa: E712


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_every_hand_typed_column_set_member_actually_exists_in_the_real_domain_map():
    """Guards against exactly the class of bug this project has already hit twice this session
    (uhe_city_name/uhe_city_country routed to the wrong role by a cross-step list; epht_metric
    silently missing from a keyword sweep): IDENTIFIER_COLUMNS, GEOMETRY_MEASURE_COLUMNS,
    POPULATION_COLUMNS, EVER_FLAG_COLUMNS, and IDENTITY_METADATA_COLUMNS are all hand-typed sets, not
    derived from the data. A single typo in one of them (e.g. "STATFP" instead of "STATEFP") would
    not raise anywhere — classify_role would simply never match the real column and would silently
    fall through to a later, wrong role (or all the way to the ROLE_MEASUREMENT default) with no
    error. This test makes that failure mode loud: every element of every hand-typed set must be a
    real column name in the committed domain map."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    real_columns = set(domain_map["column_name"])

    hand_typed_sets = {
        "IDENTIFIER_COLUMNS": mod.IDENTIFIER_COLUMNS,
        "GEOMETRY_MEASURE_COLUMNS": mod.GEOMETRY_MEASURE_COLUMNS,
        "POPULATION_COLUMNS": mod.POPULATION_COLUMNS,
        "EVER_FLAG_COLUMNS": mod.EVER_FLAG_COLUMNS,
        "IDENTITY_METADATA_COLUMNS": mod.IDENTITY_METADATA_COLUMNS,
    }
    for set_name, column_set in hand_typed_sets.items():
        missing = column_set - real_columns
        assert not missing, f"{set_name} contains column(s) not present in the real domain map (typo?): {sorted(missing)}"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_every_coverage_flag_column_is_actually_boolean_dtype():
    """classify_role detects coverage_flag purely by the `_covered` name suffix, not by dtype — a
    deliberate choice (this table has no other reliable signal), but one worth checking against the
    real data rather than just assuming: every column that role classifies as coverage_flag should
    in fact be a boolean column. If a future column were added whose name happened to end in
    `_covered` but was not boolean (e.g. a coverage percentage), it would be silently misclassified,
    and this test would be the thing that catches it."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    profile = pd.read_csv(REAL_NULL_PROFILE_CSV)
    national_profile = profile.loc[profile["scope"] == "national"]
    from scripts.confirm_domain_vintages import all_vintage_columns

    result = mod.build_classification(domain_map, national_profile, set(all_vintage_columns()))
    coverage_flag_columns = set(result.loc[result["role"] == mod.ROLE_COVERAGE_FLAG, "column_name"])
    dtype_by_column = dict(zip(domain_map["column_name"], domain_map["dtype"]))
    non_boolean = {c for c in coverage_flag_columns if dtype_by_column[c] != "bool"}
    assert not non_boolean, f"coverage_flag column(s) are not boolean dtype: {sorted(non_boolean)}"
