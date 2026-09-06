"""Tests for scripts/profile_coverage_and_nulls.py (Stage 3 Step 3).

Every function here is pure and tested against small, hand-built fixtures — no network, no real
bucket data. The one thing this test file cannot cover is whether the real bucket's actual values
behave the way these fixtures assume; that can only be confirmed by actually running the script
against the live bucket (Henry's machine), exactly like Stage 3 Step 1's schema inspection.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import scripts.profile_coverage_and_nulls as mod

REAL_DOMAIN_MAP_CSV = Path(__file__).resolve().parent.parent / "docs" / "column_domain_map.csv"


# --- filter_to_geoids -----------------------------------------------------------------------


def test_filter_to_geoids_keeps_only_matching_rows():
    df = pd.DataFrame({"GEOID": ["1", "2", "3"], "x": [10, 20, 30]})
    result = mod.filter_to_geoids(df, {"1", "3"})
    assert sorted(result["GEOID"]) == ["1", "3"]


def test_filter_to_geoids_returns_empty_frame_for_no_matches():
    df = pd.DataFrame({"GEOID": ["1", "2"], "x": [10, 20]})
    result = mod.filter_to_geoids(df, {"does-not-exist"})
    assert len(result) == 0


# --- identify_covered_flag_groups -------------------------------------------------------------


@pytest.fixture
def toy_domain_map() -> pd.DataFrame:
    """Mimics the real shape's two tricky cases in miniature: a single-flag table whose flag name
    does NOT share a prefix with its real measurement columns (like national-cdc-wonder-tract-
    table's cdcw_covered / hwd_* columns), and a two-flag table whose flags DO share a prefix with
    their own measurements but not each other's (like national-nasa-heat-tract-table's gehe_covered
    / uhe_covered)."""
    rows = [
        # Single-flag table, mismatched flag/measurement prefix.
        ("GEOID", "geography", "backbone-table"),
        ("weird_covered", "heat", "single-flag-table"),
        ("weird_meta", "heat", "single-flag-table"),
        ("totally_unrelated_name_a", "heat", "single-flag-table"),
        ("totally_unrelated_name_b", "heat", "single-flag-table"),
        # Two-flag table, each flag's own prefix matches its own measurements only.
        ("alpha_covered", "wildfire", "two-flag-table"),
        ("alpha_value_1", "wildfire", "two-flag-table"),
        ("alpha_value_2", "wildfire", "two-flag-table"),
        ("beta_covered", "wildfire", "two-flag-table"),
        ("beta_value_1", "wildfire", "two-flag-table"),
        ("shared_metadata_window", "wildfire", "two-flag-table"),  # matches neither prefix
        # A table with no covered flag at all.
        ("plain_column", "population", "no-flag-table"),
    ]
    return pd.DataFrame(rows, columns=["column_name", "domain", "source_table"])


def test_single_flag_table_groups_all_other_columns_regardless_of_name(toy_domain_map):
    """The cdcw_covered/hwd_* case: a flag's group is decided by source_table membership, not by
    whether the flag's own name shares a prefix with its measurements."""
    groups = mod.identify_covered_flag_groups(toy_domain_map)
    assert set(groups["weird_covered"]) == {"weird_meta", "totally_unrelated_name_a", "totally_unrelated_name_b"}


def test_two_flag_table_splits_by_each_flags_own_prefix(toy_domain_map):
    groups = mod.identify_covered_flag_groups(toy_domain_map)
    assert set(groups["alpha_covered"]) == {"alpha_value_1", "alpha_value_2"}
    assert set(groups["beta_covered"]) == {"beta_value_1"}


def test_two_flag_table_metadata_matching_neither_prefix_is_unclaimed(toy_domain_map):
    groups = mod.identify_covered_flag_groups(toy_domain_map)
    all_claimed = set(groups["alpha_covered"]) | set(groups["beta_covered"])
    assert "shared_metadata_window" not in all_claimed


def test_a_table_with_no_covered_flag_produces_no_group():
    domain_map = pd.DataFrame(
        [("plain_column", "population", "no-flag-table")],
        columns=["column_name", "domain", "source_table"],
    )
    assert mod.identify_covered_flag_groups(domain_map) == {}


def test_a_flag_column_is_never_swallowed_into_another_flags_member_list():
    """Regression, found and fixed during this review: the multi-flag branch used to exclude only
    the CURRENT flag (`c != flag`), not every flag in the table. If one flag's own name happens to
    start with another flag's prefix — not true for any of the 19 real flags today, but not
    something this function should get wrong if it ever does — the naive rule would wrongly treat
    the second flag as an ordinary measurement column of the first, and leave the second flag's own
    group suspiciously empty."""
    domain_map = pd.DataFrame(
        [
            ("alpha_covered", "x", "multi-table"),
            ("alpha_beta_covered", "x", "multi-table"),  # starts with "alpha" -- alpha's own prefix
            ("alpha_value", "x", "multi-table"),
        ],
        columns=["column_name", "domain", "source_table"],
    )
    groups = mod.identify_covered_flag_groups(domain_map)
    assert groups["alpha_covered"] == ["alpha_value"]
    assert "alpha_beta_covered" not in groups["alpha_covered"]


@pytest.mark.skipif(not REAL_DOMAIN_MAP_CSV.exists(), reason="docs/column_domain_map.csv not present")
class TestIdentifyCoveredFlagGroupsAgainstRealDomainMap:
    """Regression tier against Step 2's real, committed output — proving the grouping algorithm
    correctly handles the two real naming traps it was built around, not just the synthetic
    fixtures above."""

    @classmethod
    @pytest.fixture(scope="class")
    def real_groups(cls) -> dict[str, list[str]]:
        domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
        return mod.identify_covered_flag_groups(domain_map)

    def test_all_19_real_covered_flags_get_a_group(self, real_groups):
        assert len(real_groups) == 19

    def test_every_group_is_non_empty(self, real_groups):
        empty = {flag: members for flag, members in real_groups.items() if not members}
        assert empty == {}

    def test_cdcw_covered_is_grouped_by_source_table_not_by_matching_name_prefix(self, real_groups):
        """The real naming trap this whole algorithm exists for: cdcw_covered's real measurement
        columns are named hwd_*, not cdcw_*."""
        members = real_groups["cdcw_covered"]
        assert any(m.startswith("hwd_") for m in members)
        assert "cdcw_grain" in members

    def test_gehe_and_uhe_covered_are_split_by_their_own_prefixes_not_merged(self, real_groups):
        gehe_members = real_groups["gehe_covered"]
        uhe_members = real_groups["uhe_covered"]
        assert all(m.startswith("gehe_") for m in gehe_members)
        assert all(m.startswith("uhe_") for m in uhe_members)
        assert set(gehe_members).isdisjoint(uhe_members)

    def test_pmdi_and_spi_covered_are_split_including_the_spi03_spi12_variants(self, real_groups):
        """spi_covered's own prefix is "spi" (no trailing underscore) specifically so it also
        claims spi03_*/spi12_* columns, which do not contain the literal substring "spi_"."""
        spi_members = real_groups["spi_covered"]
        assert any(m.startswith("spi03_") for m in spi_members)
        assert any(m.startswith("spi12_") for m in spi_members)
        assert "pmdi_mean" not in spi_members
        assert set(real_groups["pmdi_covered"]).isdisjoint(spi_members)


# --- null_profile ----------------------------------------------------------------------------


@pytest.fixture
def toy_profile_domain_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("GEOID", "geography", "backbone-table"),
            ("some_flag", "heat", "flag-table"),
            ("some_measure", "heat", "flag-table"),
            ("some_text", "heat", "flag-table"),
        ],
        columns=["column_name", "domain", "source_table"],
    )


def test_null_profile_computes_correct_null_and_distinct_counts(toy_profile_domain_map):
    df = pd.DataFrame(
        {
            "GEOID": ["1", "2", "3", "4"],
            "some_flag": [True, True, False, False],
            "some_measure": [10.0, 20.0, np.nan, np.nan],
            "some_text": ["a", "a", "b", None],
        }
    )
    result = mod.null_profile(df, toy_profile_domain_map, scope="test-scope")

    measure_row = result.loc[result["column_name"] == "some_measure"].iloc[0]
    assert measure_row["n_rows"] == 4
    assert measure_row["n_null"] == 2
    assert measure_row["pct_null"] == pytest.approx(0.5)
    assert measure_row["min"] == 10.0
    assert measure_row["max"] == 20.0
    assert measure_row["mean"] == pytest.approx(15.0)

    text_row = result.loc[result["column_name"] == "some_text"].iloc[0]
    assert text_row["n_null"] == 1
    assert text_row["n_distinct"] == 2  # "a", "b" — None excluded from nunique(dropna=True)
    assert pd.isna(text_row["min"])  # non-numeric: no min/max/mean computed


def test_null_profile_does_not_compute_stats_for_boolean_columns(toy_profile_domain_map):
    """A bool column is technically numeric-castable in pandas but min/max/mean on it would be
    nonsensical for this report (True/False, not a real quantity) — confirmed excluded."""
    df = pd.DataFrame(
        {
            "GEOID": ["1", "2"],
            "some_flag": [True, False],
            "some_measure": [1.0, 2.0],
            "some_text": ["a", "b"],
        }
    )
    result = mod.null_profile(df, toy_profile_domain_map, scope="test-scope")
    flag_row = result.loc[result["column_name"] == "some_flag"].iloc[0]
    assert pd.isna(flag_row["min"])
    assert pd.isna(flag_row["max"])
    assert pd.isna(flag_row["mean"])


def test_null_profile_tags_a_dominant_negative_sentinel():
    domain_map = pd.DataFrame([("suspect_col", "heat", "some-table")], columns=["column_name", "domain", "source_table"])
    # 3 of 5 non-null rows are exactly -1 (60% >> the 1% threshold).
    df = pd.DataFrame({"suspect_col": [-1, -1, -1, 5.0, 10.0]})
    result = mod.null_profile(df, domain_map, scope="test-scope")
    note = result.iloc[0]["sentinel_note"]
    assert note is not None
    assert "-1" in note


def test_null_profile_does_not_flag_a_rare_negative_one_as_a_sentinel():
    domain_map = pd.DataFrame([("suspect_col", "heat", "some-table")], columns=["column_name", "domain", "source_table"])
    # -1 appears in only 1 of 200 rows (0.5%, below the 1% threshold) — plausibly a real value.
    values = [5.0] * 199 + [-1]
    df = pd.DataFrame({"suspect_col": values})
    result = mod.null_profile(df, domain_map, scope="test-scope")
    assert result.iloc[0]["sentinel_note"] is None


def _round_trip_through_plain_parquet(tmp_path, arrow_table: pa.Table) -> pd.DataFrame:
    """Writes an Arrow table with NO embedded pandas metadata (unlike `df.to_parquet(...)`, which
    always embeds it) and reads it back the same way `load_national_strata_attribute_table` does —
    `pq.read_table(...).to_pandas()`. This is the realistic shape: the real bucket's files were not
    produced via `pandas.DataFrame.to_parquet`, so an int column with nulls upcasts to plain
    `float64` and a bool column with nulls becomes `object` dtype (holding True/False/None) rather
    than pandas' nullable Int64/boolean extension types. Confirmed directly against both
    construction paths before relying on this — see docs/data_manifest.md Section 4.13/4.14."""
    path = str(tmp_path / "fixture.parquet")
    pq.write_table(arrow_table, path)
    return pq.read_table(path).to_pandas()


def test_null_profile_correctly_handles_a_realistically_upcast_int_column_with_nulls(tmp_path):
    """An Arrow int32 column with nulls, read with no pandas metadata present, becomes float64 —
    null_profile must still compute correct null/min/max/mean, not silently misbehave on the
    upcast."""
    df = _round_trip_through_plain_parquet(
        tmp_path,
        pa.table({"GEOID": pa.array(["1", "2", "3"]), "fod_fires": pa.array([1, None, 3], type=pa.int32())}),
    )
    assert df["fod_fires"].dtype == np.float64  # confirms the realistic upcast actually happened

    domain_map = pd.DataFrame(
        [("fod_fires", "wildfire", "national-fpa-fod-tract-table")],
        columns=["column_name", "domain", "source_table"],
    )
    result = mod.null_profile(df, domain_map, scope="test-scope").iloc[0]
    assert result["n_null"] == 1
    assert result["min"] == 1.0
    assert result["max"] == 3.0
    assert result["mean"] == pytest.approx(2.0)


def test_null_profile_excludes_a_realistically_object_dtype_bool_column_from_numeric_stats(tmp_path):
    """An Arrow bool column with nulls, read with no pandas metadata present, becomes object dtype
    (True/False/None as Python objects) — null_profile must still recognize it as non-numeric and
    still count its nulls correctly, not accidentally try to compute a mean of True/False/None."""
    df = _round_trip_through_plain_parquet(
        tmp_path,
        pa.table({"GEOID": pa.array(["1", "2", "3"]), "usfs_covered": pa.array([True, None, False], type=pa.bool_())}),
    )
    assert df["usfs_covered"].dtype == object  # confirms the realistic object-dtype fallback happened

    domain_map = pd.DataFrame(
        [("usfs_covered", "wildfire", "national-usfs-wildfire-tract-table")],
        columns=["column_name", "domain", "source_table"],
    )
    result = mod.null_profile(df, domain_map, scope="test-scope").iloc[0]
    assert result["n_null"] == 1
    assert pd.isna(result["min"])
    assert pd.isna(result["max"])
    assert pd.isna(result["mean"])


def test_covered_flag_consistency_works_against_a_realistically_object_dtype_flag_column(tmp_path):
    """The flag column itself can be the object-dtype-with-None shape, not just its members —
    covered_flag_consistency's `== True` / `== False` comparisons must still behave correctly."""
    df = _round_trip_through_plain_parquet(
        tmp_path,
        pa.table(
            {
                "GEOID": pa.array(["1", "2", "3"]),
                "usfs_covered": pa.array([True, False, None], type=pa.bool_()),
                "usfs_BP_mean": pa.array([5.0, None, 9.0], type=pa.float64()),
            }
        ),
    )
    result = mod.covered_flag_consistency(df, "usfs_covered", ["usfs_BP_mean"], scope="test-scope")
    assert result["n_covered_true"] == 1
    assert result["n_covered_false"] == 1
    assert result["n_covered_true_but_all_members_null"] == 0
    assert result["n_covered_false_but_some_member_non_null"] == 0


# --- _sentinel_note ----------------------------------------------------------------------------


def test_sentinel_note_reports_every_matching_sentinel_not_just_the_first():
    """Regression for a bug introduced and caught during this same review: reporting every match
    naively (without deduplicating -1 vs -1.0-style float/int literal pairs) would have printed the
    same finding twice under two different labels — SENTINEL_CANDIDATES now lists each value once,
    as a float, specifically to avoid that."""
    series = pd.Series([-1.0] * 30 + [9999.0] * 30 + [5.0] * 40)
    note = mod._sentinel_note(series)
    assert note is not None
    assert note.count("-1.0") == 1  # exactly one mention, not a duplicate under two labels
    assert "9999.0" in note


def test_null_profile_handles_an_entirely_null_column_without_crashing():
    domain_map = pd.DataFrame([("empty_col", "heat", "some-table")], columns=["column_name", "domain", "source_table"])
    df = pd.DataFrame({"empty_col": [np.nan, np.nan, np.nan]})
    result = mod.null_profile(df, domain_map, scope="test-scope")
    row = result.iloc[0]
    assert row["n_null"] == 3
    assert row["pct_null"] == 1.0
    assert pd.isna(row["min"])  # no non-null values to take a min/max/mean of


# --- covered_flag_consistency -----------------------------------------------------------------


def test_covered_flag_consistency_reports_zero_exceptions_for_a_clean_flag():
    df = pd.DataFrame(
        {
            "flag": [True, True, False, False],
            "member_a": [1.0, 2.0, np.nan, np.nan],
            "member_b": [10.0, 20.0, np.nan, np.nan],
        }
    )
    result = mod.covered_flag_consistency(df, "flag", ["member_a", "member_b"], scope="test-scope")
    assert result["n_covered_true"] == 2
    assert result["n_covered_false"] == 2
    assert result["n_covered_true_but_all_members_null"] == 0
    assert result["n_covered_false_but_some_member_non_null"] == 0


def test_covered_flag_consistency_catches_covered_true_but_all_members_null():
    df = pd.DataFrame(
        {
            "flag": [True, False],
            "member_a": [np.nan, np.nan],  # flag says covered, but data is missing anyway
        }
    )
    result = mod.covered_flag_consistency(df, "flag", ["member_a"], scope="test-scope")
    assert result["n_covered_true_but_all_members_null"] == 1


def test_covered_flag_consistency_catches_covered_false_but_member_has_data():
    df = pd.DataFrame(
        {
            "flag": [False, True],
            "member_a": [5.0, 10.0],  # flag says not covered, but there's a real value anyway
        }
    )
    result = mod.covered_flag_consistency(df, "flag", ["member_a"], scope="test-scope")
    assert result["n_covered_false_but_some_member_non_null"] == 1


def test_covered_flag_consistency_treats_a_null_flag_value_as_neither_true_nor_false():
    df = pd.DataFrame(
        {
            "flag": [True, False, np.nan],
            "member_a": [1.0, np.nan, 99.0],  # row 3: unknown coverage status, has data anyway
        }
    )
    result = mod.covered_flag_consistency(df, "flag", ["member_a"], scope="test-scope")
    assert result["n_covered_true"] == 1
    assert result["n_covered_false"] == 1
    # Row 3 (NaN flag) must not be silently counted as either bucket, so its "surprising" data
    # does not get miscounted as a covered_false exception.
    assert result["n_covered_false_but_some_member_non_null"] == 0


def test_covered_flag_consistency_handles_an_empty_member_list_without_dividing_by_zero():
    df = pd.DataFrame({"flag": [True, False]})
    result = mod.covered_flag_consistency(df, "flag", [], scope="test-scope")
    assert result["n_member_columns"] == 0
    assert result["n_covered_true_but_all_members_null"] == 0
    assert result["n_covered_false_but_some_member_non_null"] == 0


# --- build_domain_scope_summary -----------------------------------------------------------------


def test_build_domain_scope_summary_excludes_geography_and_population_domains():
    profile_df = pd.DataFrame(
        [
            {"scope": "national", "domain": "geography", "pct_null": 0.0},
            {"scope": "national", "domain": "population", "pct_null": 0.0},
            {"scope": "national", "domain": "heat", "pct_null": 0.2},
            {"scope": "national", "domain": "heat", "pct_null": 0.4},
        ]
    )
    summary = mod.build_domain_scope_summary(profile_df)
    assert "geography" not in summary.index
    assert "population" not in summary.index
    assert summary.loc["heat", "national"] == pytest.approx(0.3)


# --- main() ------------------------------------------------------------------------------------


def test_main_returns_a_clean_error_when_domain_map_is_missing(tmp_path, capsys):
    rc = mod.main(["--domain-map", str(tmp_path / "does_not_exist.csv")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_does_not_crash_when_the_domain_map_has_zero_covered_flag_columns(tmp_path, monkeypatch):
    """Regression, found and fixed during this review: identify_covered_flag_groups returning an
    empty dict (no column ends in "_covered") used to leave consistency_records empty, which built
    a columnless DataFrame from pd.DataFrame.from_records([]) — main()'s later
    consistency_df["n_covered_true_but_all_members_null"] filter then raised KeyError instead of
    simply reporting zero exceptions. Never triggered by the real, committed 232-column domain map
    (it has 19 covered flags), but not something an arbitrary --domain-map should be able to crash
    on."""
    domain_map_csv = tmp_path / "column_domain_map.csv"
    pd.DataFrame(
        [("GEOID", "geography", "some-table"), ("value", "heat", "some-table")],
        columns=["column_name", "domain", "source_table"],
    ).to_csv(domain_map_csv, index=False)

    monkeypatch.setattr(
        mod,
        "load_national_strata_attribute_table",
        lambda table: pd.DataFrame({"GEOID": ["1", "2"], "value": [1.0, 2.0]}),
    )
    monkeypatch.setattr(mod, "REGIONS", [])

    rc = mod.main(
        [
            "--domain-map", str(domain_map_csv),
            "--profile-output", str(tmp_path / "profile.csv"),
            "--domain-summary-output", str(tmp_path / "summary.csv"),
            "--flag-consistency-output", str(tmp_path / "flags.csv"),
        ]
    )

    assert rc == 0
    written = pd.read_csv(tmp_path / "flags.csv")
    assert list(written.columns) == mod._FLAG_CONSISTENCY_COLUMNS
    assert len(written) == 0


def test_main_returns_a_clean_error_when_the_live_table_is_missing_a_domain_map_column(
    tmp_path, monkeypatch, capsys
):
    """If the bucket's schema ever drifts from what Steps 1/2 last confirmed, this must fail
    loudly with a clear pointer back to those steps, not silently profile a smaller table."""
    domain_map_csv = tmp_path / "column_domain_map.csv"
    pd.DataFrame(
        [("GEOID", "geography", "some-table"), ("column_not_in_live_table", "heat", "some-table")],
        columns=["column_name", "domain", "source_table"],
    ).to_csv(domain_map_csv, index=False)

    monkeypatch.setattr(
        mod,
        "load_national_strata_attribute_table",
        lambda table: pd.DataFrame({"GEOID": ["1"]}),
    )

    rc = mod.main(["--domain-map", str(domain_map_csv)])
    assert rc == 2
    assert "column_not_in_live_table" in capsys.readouterr().err


def test_main_warns_but_still_completes_on_an_unexpected_national_row_count(tmp_path, monkeypatch, capsys):
    domain_map_csv = tmp_path / "column_domain_map.csv"
    pd.DataFrame(
        [("GEOID", "geography", "some-table"), ("value", "heat", "some-table")],
        columns=["column_name", "domain", "source_table"],
    ).to_csv(domain_map_csv, index=False)

    # Deliberately NOT 85,396 rows.
    small_df = pd.DataFrame({"GEOID": ["1", "2"], "value": [1.0, 2.0]})
    monkeypatch.setattr(mod, "load_national_strata_attribute_table", lambda table: small_df)
    monkeypatch.setattr(mod, "REGIONS", [])  # skip region loading entirely for this test

    rc = mod.main(
        [
            "--domain-map", str(domain_map_csv),
            "--profile-output", str(tmp_path / "profile.csv"),
            "--domain-summary-output", str(tmp_path / "summary.csv"),
            "--flag-consistency-output", str(tmp_path / "flags.csv"),
        ]
    )

    assert rc == 0  # a row-count surprise warns, it does not block the run
    stderr = capsys.readouterr().err
    assert "85396" in stderr or "85,396" in stderr


def test_main_warns_when_a_regions_geoid_list_has_entries_missing_from_the_national_table(
    tmp_path, monkeypatch, capsys
):
    domain_map_csv = tmp_path / "column_domain_map.csv"
    pd.DataFrame(
        [("GEOID", "geography", "some-table"), ("value", "heat", "some-table")],
        columns=["column_name", "domain", "source_table"],
    ).to_csv(domain_map_csv, index=False)

    national_df = pd.DataFrame({"GEOID": ["1", "2"], "value": [1.0, 2.0]})
    monkeypatch.setattr(mod, "load_national_strata_attribute_table", lambda table: national_df)
    monkeypatch.setattr(mod, "REGIONS", ["fake-region"])
    monkeypatch.setattr(
        mod,
        "load_sample_submission",
        lambda region: pd.DataFrame({"GEOID": ["1", "2", "3-not-in-national-table"]}),
    )

    rc = mod.main(
        [
            "--domain-map", str(domain_map_csv),
            "--profile-output", str(tmp_path / "profile.csv"),
            "--domain-summary-output", str(tmp_path / "summary.csv"),
            "--flag-consistency-output", str(tmp_path / "flags.csv"),
        ]
    )

    assert rc == 0
    assert "WARNING" in capsys.readouterr().err
