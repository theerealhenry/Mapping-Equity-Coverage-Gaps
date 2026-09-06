"""Tests for scripts/confirm_domain_vintages.py (Stage 3 Step 4).

Every function here is pure and tested against small, hand-built fixtures — no network, no real
bucket data. The one thing this test file cannot cover is whether the real bucket's actual vintage
values match what external research says each source agency currently documents; that comparison
is done separately, by hand, in docs/data_vintage_confirmation.md, using the real CSV this script
produces when Henry runs it against the live bucket.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import scripts.confirm_domain_vintages as mod

REAL_DOMAIN_MAP_CSV = Path(__file__).resolve().parent.parent / "docs" / "column_domain_map.csv"
REAL_NULL_PROFILE_CSV = Path(__file__).resolve().parent.parent / "docs" / "coverage_null_profile.csv"

# Real, committed columns confirmed (via docs/coverage_null_profile.csv's national scope) to take
# only one distinct value across all 85,396 tracts, that are NOT vintage metadata — a genuine
# measurement or flag that simply happens to carry zero discriminative signal in this dataset, not
# an undocumented table-level constant that should have been listed in
# VINTAGE_COLUMNS_BY_SOURCE_TABLE. Each entry here must be independently justified, not just added
# to make a test pass:
#   - rucc_covered, ghcn_covered: real `_covered` flags, always True nationally (Stage 3 Step 3
#     Finding 4, docs/data_manifest.md Section 4.14) — carry no signal, but are genuine flags, not
#     hidden vintage metadata.
#   - hwd_maxtemp_never_defined: a real per-tract measurement (parallel to hwd_heatindex_never_
#     defined / hwd_heatstress_never_defined, which DO vary nationally) that happens to be False for
#     every single tract — the maxtemp trend is always computable, unlike heatindex/heatstress.
_KNOWN_NON_VINTAGE_ZERO_VARIANCE_COLUMNS = {
    "rucc_covered",
    "ghcn_covered",
    "hwd_maxtemp_never_defined",
}

# Keyword sweep used by the completeness regression test below — mirrors the manual sweep run
# during this step's own review, which is exactly how the review found this list was in fact
# complete (every keyword hit was either already listed or one of the five cvi_baseline* columns,
# confirmed by inspecting their real values to be continuous per-tract CVI sub-scores, not table-
# level vintage metadata at all — a false positive of the keyword match, not a missed column).
_VINTAGE_KEYWORD_PATTERN = re.compile(
    r"year|vintage|edition|version|window|threshold|calibrat|grain|extent|record|date|period"
    r"|epoch|baseline|release",
    re.IGNORECASE,
)

# Real columns that match the keyword sweep above but are deliberately NOT vintage metadata,
# confirmed by inspecting their actual values in docs/coverage_null_profile.csv:
_KNOWN_NON_VINTAGE_KEYWORD_MATCHES = {
    # Continuous 0-1 CVI "baseline vulnerability" sub-index scores (~77,000 distinct values each,
    # varying per tract) — "baseline" here is a CVI methodology component name (baseline
    # vulnerability vs. climate vulnerability), not a data vintage.
    "cvi_baseline",
    "cvi_baseline_health",
    "cvi_baseline_socioeconomic",
    "cvi_baseline_infrastructure",
    "cvi_baseline_environment",
    # Per-tract wildfire-history measurements that happen to contain a year/date-like keyword but
    # vary widely by tract (dozens of distinct values, high null rates) rather than describing the
    # table's own vintage — Step 3 already profiled these as genuine measurement columns.
    "mtbs_wildfire_last_year",
    "mtbs_years_since_wildfire",
    "nifc_wildfire_last_year",
    "nifc_years_since_wildfire",
    "fod_last_fire_year",
    "usgs_wildfire_return_interval_years",
    "usgs_first_year_burned",
    "usgs_last_year_burned",
    "usgs_years_since_last_fire",
}

# The one source table confirmed (by reading its full column list) to carry no vintage/edition
# column of its own at all.
_SOURCE_TABLES_WITH_NO_VINTAGE_COLUMN = {"national-tribal-tract-table"}


# --- all_vintage_columns --------------------------------------------------------------------


def test_all_vintage_columns_flattens_every_table_in_order():
    columns_by_table = {"table-a": ["col1", "col2"], "table-b": ["col3"]}
    assert mod.all_vintage_columns(columns_by_table) == ["col1", "col2", "col3"]


def test_all_vintage_columns_defaults_to_the_real_module_level_mapping():
    result = mod.all_vintage_columns()
    assert "svi_year" in result
    assert "tract_vintage" in result


# --- distinct_value_summary ------------------------------------------------------------------


def test_distinct_value_summary_reports_a_single_constant_value_with_full_count():
    series = pd.Series([2022] * 85_396)
    assert mod.distinct_value_summary(series) == "2022 (85396)"


def test_distinct_value_summary_orders_by_frequency_descending():
    series = pd.Series(["b", "a", "a", "a", "b"])
    assert mod.distinct_value_summary(series) == "'a' (3); 'b' (2)"


def test_distinct_value_summary_truncates_and_notes_remaining_count():
    series = pd.Series([f"city_{i}" for i in range(20)])
    result = mod.distinct_value_summary(series, max_values=5)
    assert result.count(";") == 5  # 5 shown values joined by "; ", plus the "+N more" suffix
    assert "+15 more distinct value(s)" in result


def test_distinct_value_summary_handles_an_all_null_column():
    series = pd.Series([None, None, None], dtype="object")
    assert mod.distinct_value_summary(series) == "(all null)"


def test_distinct_value_summary_ignores_nulls_when_counting_and_ranking():
    series = pd.Series([1.0, 1.0, None, 2.0])
    assert mod.distinct_value_summary(series) == "1.0 (2); 2.0 (1)"


# --- summarize_vintage_columns --------------------------------------------------------------


def test_summarize_vintage_columns_produces_one_row_per_listed_column():
    df = pd.DataFrame(
        {
            "GEOID": ["1", "2", "3"],
            "svi_year": [2022, 2022, 2022],
            "usfs_edition": ["Wildfire Risk to Communities, 2nd Edition"] * 3,
        }
    )
    columns_by_table = {
        "national-svi-tract-table": ["svi_year"],
        "national-usfs-wildfire-tract-table": ["usfs_edition"],
    }
    result = mod.summarize_vintage_columns(df, columns_by_table)

    assert len(result) == 2
    assert set(result["column_name"]) == {"svi_year", "usfs_edition"}

    svi_row = result.loc[result["column_name"] == "svi_year"].iloc[0]
    assert svi_row["source_table"] == "national-svi-tract-table"
    assert svi_row["n_rows"] == 3
    assert svi_row["n_null"] == 0
    assert svi_row["n_distinct"] == 1
    assert svi_row["values"] == "2022 (3)"

    usfs_row = result.loc[result["column_name"] == "usfs_edition"].iloc[0]
    assert "2nd Edition" in usfs_row["values"]


def test_summarize_vintage_columns_reports_null_counts_correctly():
    df = pd.DataFrame({"spi_calibration": [None, None, None]})
    columns_by_table = {"national-drought-gov-tract-table": ["spi_calibration"]}
    result = mod.summarize_vintage_columns(df, columns_by_table)

    row = result.iloc[0]
    assert row["n_null"] == 3
    assert row["pct_null"] == 1.0
    assert row["n_distinct"] == 0
    assert row["values"] == "(all null)"


# --- main() -------------------------------------------------------------------------------


def _minimal_domain_map_columns() -> dict[str, list[str]]:
    return {"national-svi-tract-table": ["svi_year"]}


def test_main_writes_the_summary_csv_and_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mod, "VINTAGE_COLUMNS_BY_SOURCE_TABLE", _minimal_domain_map_columns()
    )
    monkeypatch.setattr(
        mod,
        "load_national_strata_attribute_table",
        lambda table: pd.DataFrame({"GEOID": ["1"] * mod.EXPECTED_NATIONAL_ROW_COUNT, "svi_year": [2022] * mod.EXPECTED_NATIONAL_ROW_COUNT}),
    )

    output_path = tmp_path / "vintages.csv"
    rc = mod.main(["--output", str(output_path)])

    assert rc == 0
    written = pd.read_csv(output_path)
    assert len(written) == 1
    assert written.iloc[0]["column_name"] == "svi_year"


def test_main_warns_but_still_completes_on_an_unexpected_row_count(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        mod, "VINTAGE_COLUMNS_BY_SOURCE_TABLE", _minimal_domain_map_columns()
    )
    # Deliberately not EXPECTED_NATIONAL_ROW_COUNT.
    monkeypatch.setattr(
        mod,
        "load_national_strata_attribute_table",
        lambda table: pd.DataFrame({"GEOID": ["1", "2"], "svi_year": [2022, 2022]}),
    )

    rc = mod.main(["--output", str(tmp_path / "vintages.csv")])

    assert rc == 0
    stderr = capsys.readouterr().err
    assert "85396" in stderr or "85,396" in stderr


def test_main_returns_a_clean_error_when_a_vintage_column_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        mod, "VINTAGE_COLUMNS_BY_SOURCE_TABLE", {"some-table": ["column_not_in_live_table"]}
    )
    monkeypatch.setattr(
        mod, "load_national_strata_attribute_table", lambda table: pd.DataFrame({"GEOID": ["1"]})
    )

    rc = mod.main(["--output", str(tmp_path / "vintages.csv")])

    assert rc == 2
    assert "column_not_in_live_table" in capsys.readouterr().err


# --- Real-data regression: every listed column must actually exist in the committed domain map --


@pytest.mark.skipif(not REAL_DOMAIN_MAP_CSV.exists(), reason="docs/column_domain_map.csv not present")
def test_every_vintage_column_exists_in_the_real_committed_domain_map():
    """Guards against VINTAGE_COLUMNS_BY_SOURCE_TABLE drifting out of sync with the real, committed
    232-column domain map (e.g. a typo, or a column Step 2 later renames)."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    real_columns = set(domain_map["column_name"])
    for source_table, columns in mod.VINTAGE_COLUMNS_BY_SOURCE_TABLE.items():
        for column in columns:
            assert column in real_columns, f"{column!r} (listed under {source_table!r}) not in the real domain map"


@pytest.mark.skipif(not REAL_DOMAIN_MAP_CSV.exists(), reason="docs/column_domain_map.csv not present")
def test_every_vintage_column_is_attributed_to_the_source_table_it_is_listed_under():
    """Guards against a column being listed under the wrong source_table, which would silently mis-
    attribute a value in docs/data_vintage_confirmation.md to the wrong external dataset."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    real_source_table_by_column = dict(zip(domain_map["column_name"], domain_map["source_table"]))
    for source_table, columns in mod.VINTAGE_COLUMNS_BY_SOURCE_TABLE.items():
        for column in columns:
            assert real_source_table_by_column[column] == source_table


def test_all_vintage_columns_has_no_duplicates_in_the_real_module_level_mapping():
    """Locks in the module docstring's claim ("every vintage column name is unique across all 19
    source tables") as an actual regression test rather than an unverified comment — found, during
    this step's own review, to be true today but not previously enforced by anything."""
    columns = mod.all_vintage_columns()
    assert len(columns) == len(set(columns))


@pytest.mark.skipif(not REAL_DOMAIN_MAP_CSV.exists(), reason="docs/column_domain_map.csv not present")
def test_no_vintage_relevant_column_is_missing_from_the_module_level_mapping():
    """Completeness regression, added during this step's own review. A one-off manual keyword sweep
    of the real domain map (year/vintage/edition/version/window/threshold/calibration/grain/extent/
    record/date/period/epoch/baseline/release) found the module's list was in fact complete — every
    hit was either already listed, or one of the cvi_baseline*/wildfire-history columns confirmed by
    inspecting their real values (docs/coverage_null_profile.csv) to be per-tract measurements, not
    table-level vintage metadata (a false positive of the keyword match). This test turns that one-
    off sweep into a permanent guard: if column_domain_map.csv ever gains a new column matching one
    of these keywords, this fails loudly instead of silently leaving it out of the vintage
    confirmation — exactly the kind of drift Step 4 cannot afford to miss."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    keyword_matches = set(
        domain_map.loc[domain_map["column_name"].str.contains(_VINTAGE_KEYWORD_PATTERN), "column_name"]
    )
    listed = set(mod.all_vintage_columns())
    unexplained = keyword_matches - listed - _KNOWN_NON_VINTAGE_KEYWORD_MATCHES
    assert not unexplained, (
        f"Column(s) matching a vintage-like keyword are neither listed in "
        f"VINTAGE_COLUMNS_BY_SOURCE_TABLE nor a documented false positive: {sorted(unexplained)}"
    )


@pytest.mark.skipif(not REAL_DOMAIN_MAP_CSV.exists(), reason="docs/column_domain_map.csv not present")
def test_every_real_source_table_is_either_listed_or_a_documented_exclusion():
    """Completeness regression, added during this step's own review: every one of the 19 real
    source tables must either appear as a key in VINTAGE_COLUMNS_BY_SOURCE_TABLE, or be explicitly
    named in _SOURCE_TABLES_WITH_NO_VINTAGE_COLUMN (today, only national-tribal-tract-table, which
    was confirmed by reading its full column list to carry no vintage/edition column at all). Guards
    against a future 20th source table silently falling through this step unnoticed."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    real_tables = set(domain_map["source_table"])
    covered = set(mod.VINTAGE_COLUMNS_BY_SOURCE_TABLE) | _SOURCE_TABLES_WITH_NO_VINTAGE_COLUMN
    missing = real_tables - covered
    assert not missing, f"Source table(s) neither listed nor a documented exclusion: {sorted(missing)}"


@pytest.mark.skipif(not REAL_NULL_PROFILE_CSV.exists(), reason="docs/coverage_null_profile.csv not present")
def test_every_nationally_constant_column_is_either_vintage_or_a_documented_exception():
    """Stronger completeness regression, added while building Stage 3 Step 5 — Step 5's own
    cross-check against real n_distinct data (not a keyword sweep) found `epht_metric`, a genuine
    constant-string methodology-metadata column analogous to `epht_threshold`, that the original
    keyword sweep (`test_no_vintage_relevant_column_is_missing_from_the_module_level_mapping`) had
    missed entirely — "metric" was never one of its keywords, so the column was never even a
    candidate the sweep considered. A column taking only one distinct value across all 85,396 real
    tracts (docs/coverage_null_profile.csv, national scope) is either genuine vintage/methodology
    metadata (belongs in VINTAGE_COLUMNS_BY_SOURCE_TABLE) or a real measurement/flag that happens to
    carry zero variance in this dataset (must be named in _KNOWN_NON_VINTAGE_ZERO_VARIANCE_COLUMNS
    with a specific justification, not silently ignored). This check does not depend on guessing the
    right keywords — it uses the data's own actual values, which is exactly why it caught what the
    keyword sweep missed."""
    profile = pd.read_csv(REAL_NULL_PROFILE_CSV)
    national = profile.loc[profile["scope"] == "national"]
    zero_variance_columns = set(national.loc[national["n_distinct"] <= 1, "column_name"])

    listed = set(mod.all_vintage_columns())
    explained = listed | _KNOWN_NON_VINTAGE_ZERO_VARIANCE_COLUMNS
    unexplained = zero_variance_columns - explained
    assert not unexplained, (
        f"Column(s) take only one distinct value nationally but are neither listed as vintage "
        f"metadata nor a documented zero-variance exception: {sorted(unexplained)}"
    )
