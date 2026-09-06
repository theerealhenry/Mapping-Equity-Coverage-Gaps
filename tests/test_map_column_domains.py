"""Tests for scripts/map_column_domains.py (Stage 3 Step 2 — column-to-domain mapping).

Two tiers, deliberately: small hand-built fixtures exercise the pure functions' logic and edge
cases in isolation; a second tier runs the same functions against the real, already-committed
docs/national_strata_schema_raw.csv as a regression fixture, proving the real 232-column joined
table is still fully and unambiguously classified. Neither tier touches the network — the real-data
tier reads a file already checked into this repository (Stage 3 Step 1's own output), not the live
bucket.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import scripts.map_column_domains as mod
import src.config as config

REAL_SCHEMA_CSV = Path(__file__).resolve().parent.parent / "docs" / "national_strata_schema_raw.csv"


# --- Fixtures ------------------------------------------------------------------------------------


def _schema_row(source_table, column_name, position, dtype="string", table_num_rows=100):
    return {
        "source_table": source_table,
        "column_name": column_name,
        "position": position,
        "arrow_dtype": dtype,
        "table_num_rows": table_num_rows,
        "error_message": None,
    }


@pytest.fixture
def toy_schema_df() -> pd.DataFrame:
    """A small, hand-built stand-in for docs/national_strata_schema_raw.csv's shape: one joined
    table plus a handful of source tables, including one deliberately unmapped table (to exercise
    the UNCLASSIFIED path) and one deliberately ambiguous, non-backbone column (to exercise the
    AMBIGUOUS path)."""
    rows = [
        # The joined table's own columns.
        _schema_row(mod.JOINED_TABLE, "GEOID", 0),
        _schema_row(mod.JOINED_TABLE, "pop_total", 1, dtype="int64"),
        _schema_row(mod.JOINED_TABLE, "svi_overall", 2, dtype="double"),
        _schema_row(mod.JOINED_TABLE, "weird_shared_col", 3),
        _schema_row(mod.JOINED_TABLE, "column_from_unmapped_table", 4),
        _schema_row(mod.JOINED_TABLE, "totally_missing_column", 5),
        # Source tables.
        _schema_row("national-census-tract-table", "GEOID", 0),
        _schema_row("national-census-tract-table", "pop_total", 1, dtype="int64"),
        _schema_row("national-svi-tract-table", "GEOID", 0),
        _schema_row("national-svi-tract-table", "svi_overall", 1, dtype="double"),
        # weird_shared_col appears in two source tables and is NOT one of the known backbone
        # columns — this should surface as AMBIGUOUS, not be silently resolved.
        _schema_row("national-svi-tract-table", "weird_shared_col", 2),
        _schema_row("national-census-tract-table", "weird_shared_col", 2),
        # A table with no entry in TABLE_DOMAIN at all.
        _schema_row("some-brand-new-unmapped-table", "column_from_unmapped_table", 0),
        # totally_missing_column intentionally has no source-table row anywhere.
    ]
    return pd.DataFrame.from_records(rows)


# --- attribute_source_table -----------------------------------------------------------------


def test_shared_backbone_column_is_attributed_to_the_backbone_table_regardless_of_source_rows(
    toy_schema_df,
):
    non_joined = toy_schema_df.loc[toy_schema_df["source_table"] != mod.JOINED_TABLE]
    source_table, method = mod.attribute_source_table("GEOID", non_joined)
    assert source_table == "national-census-tract-table"
    assert method == "shared-backbone"


def test_column_in_exactly_one_source_table_is_unambiguous(toy_schema_df):
    non_joined = toy_schema_df.loc[toy_schema_df["source_table"] != mod.JOINED_TABLE]
    source_table, method = mod.attribute_source_table("svi_overall", non_joined)
    assert source_table == "national-svi-tract-table"
    assert method == "unambiguous"


def test_column_in_multiple_non_backbone_source_tables_is_flagged_ambiguous(toy_schema_df):
    non_joined = toy_schema_df.loc[toy_schema_df["source_table"] != mod.JOINED_TABLE]
    source_table, method = mod.attribute_source_table("weird_shared_col", non_joined)
    assert method == "AMBIGUOUS"
    assert "national-census-tract-table" in source_table
    assert "national-svi-tract-table" in source_table


def test_column_with_no_source_table_row_at_all_is_flagged_not_found(toy_schema_df):
    non_joined = toy_schema_df.loc[toy_schema_df["source_table"] != mod.JOINED_TABLE]
    source_table, method = mod.attribute_source_table("totally_missing_column", non_joined)
    assert method == "NOT_FOUND"
    assert source_table == "<none>"


# --- classify_domain -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "column,expected_domain",
    [(c, "population") for c in mod.CENSUS_TRACT_TABLE_POPULATION_COLUMNS],
)
def test_census_tract_table_population_columns_are_classified_population(column, expected_domain):
    assert mod.classify_domain(column, mod.BACKBONE_SOURCE_TABLE) == expected_domain


def test_census_tract_table_non_population_columns_are_classified_geography():
    assert mod.classify_domain("GEOID", mod.BACKBONE_SOURCE_TABLE) == "geography"
    assert mod.classify_domain("state_name", mod.BACKBONE_SOURCE_TABLE) == "geography"


def test_a_table_with_no_table_domain_entry_is_classified_unclassified_not_raised():
    assert mod.classify_domain("anything", "some-brand-new-unmapped-table") == "UNCLASSIFIED"


def test_every_table_domain_value_is_a_valid_domain():
    """Guards against a typo in TABLE_DOMAIN's literal domain strings going unnoticed."""
    invalid = {table: domain for table, domain in mod.TABLE_DOMAIN.items() if domain not in mod.VALID_DOMAINS}
    assert invalid == {}


def test_table_domain_exactly_covers_the_canonical_national_strata_source_table_list():
    """TABLE_DOMAIN is meant to have one entry for every one of the 25 tables under
    strata/national/ that src/config.py's NATIONAL_STRATA_SOURCE_TABLES names as the single source
    of truth (Step 1, docs/data_manifest.md Section 4.11) — no more, no fewer. Without this check,
    a typo in one of TABLE_DOMAIN's table-name keys (e.g. a missing/extra letter) would silently
    create a dead entry that never matches any real table, while the real table it was meant to
    cover would fall through to UNCLASSIFIED — a failure `find_unresolved` only catches for tables
    that actually contribute a column to the 232-column join, not for one of the four tables that
    contribute zero joined columns (national-cdc-wonder-heat-mortality, national-census-aiannh,
    national-census-tribal-subdivisions, national-census-tribal-tracts) but are still meant to carry
    a correct domain for Stage 3 Step 8's full dictionary later."""
    table_domain_keys = set(mod.TABLE_DOMAIN.keys())
    canonical_tables = set(config.NATIONAL_STRATA_SOURCE_TABLES)
    assert table_domain_keys == canonical_tables, (
        f"missing from TABLE_DOMAIN: {canonical_tables - table_domain_keys}; "
        f"extra/typo'd in TABLE_DOMAIN: {table_domain_keys - canonical_tables}"
    )


# --- build_domain_map / find_unresolved ------------------------------------------------------


def test_build_domain_map_produces_one_row_per_joined_column_in_original_order(toy_schema_df):
    result = mod.build_domain_map(toy_schema_df)
    assert list(result["column_name"]) == [
        "GEOID",
        "pop_total",
        "svi_overall",
        "weird_shared_col",
        "column_from_unmapped_table",
        "totally_missing_column",
    ]
    assert len(result) == 6


def test_build_domain_map_surfaces_the_three_problem_rows_via_find_unresolved(toy_schema_df):
    result = mod.build_domain_map(toy_schema_df)
    unresolved = mod.find_unresolved(result)
    assert set(unresolved["column_name"]) == {
        "weird_shared_col",  # AMBIGUOUS attribution
        "column_from_unmapped_table",  # unambiguous attribution, but UNCLASSIFIED domain
        "totally_missing_column",  # NOT_FOUND attribution
    }


def test_build_domain_map_leaves_clean_rows_out_of_find_unresolved(toy_schema_df):
    result = mod.build_domain_map(toy_schema_df)
    unresolved_columns = set(mod.find_unresolved(result)["column_name"])
    assert "GEOID" not in unresolved_columns
    assert "pop_total" not in unresolved_columns
    assert "svi_overall" not in unresolved_columns


def test_domain_summary_counts_match_the_domain_column(toy_schema_df):
    result = mod.build_domain_map(toy_schema_df)
    counts = mod.domain_summary(result)
    assert counts["geography"] == 1  # GEOID
    assert counts["population"] == 1  # pop_total
    assert counts["svi"] == 1  # svi_overall


# --- Real-data regression tier (reads the committed Step 1 artifact, no network) --------------


@pytest.mark.skipif(not REAL_SCHEMA_CSV.exists(), reason="docs/national_strata_schema_raw.csv not present")
class TestAgainstRealCommittedSchema:
    @classmethod
    @pytest.fixture(scope="class")
    def real_domain_map(cls) -> pd.DataFrame:
        schema_df = mod.load_schema_csv(REAL_SCHEMA_CSV)
        return mod.build_domain_map(schema_df)

    def test_all_232_real_joined_columns_are_present_exactly_once(self, real_domain_map):
        assert len(real_domain_map) == 232
        assert real_domain_map["column_name"].nunique() == 232

    def test_no_real_column_is_unresolved(self, real_domain_map):
        unresolved = mod.find_unresolved(real_domain_map)
        assert len(unresolved) == 0, unresolved.to_string(index=False)

    def test_attribution_methods_are_only_the_two_expected_clean_outcomes(self, real_domain_map):
        assert set(real_domain_map["attribution_method"]) == {"unambiguous", "shared-backbone"}

    def test_shared_backbone_count_matches_step_1s_documented_finding(self, real_domain_map):
        """Step 1 (docs/data_manifest.md Section 4.11) found exactly 9 shared backbone columns."""
        backbone_rows = real_domain_map.loc[real_domain_map["attribution_method"] == "shared-backbone"]
        assert len(backbone_rows) == 9
        assert set(backbone_rows["column_name"]) == mod.SHARED_BACKBONE_COLUMNS

    def test_every_domain_present_is_a_valid_domain(self, real_domain_map):
        assert set(real_domain_map["domain"]).issubset(mod.VALID_DOMAINS)

    def test_domain_counts_sum_to_232(self, real_domain_map):
        assert mod.domain_summary(real_domain_map).sum() == 232


# --- main() ------------------------------------------------------------------------------------


def test_main_writes_output_csv_and_returns_zero_on_a_clean_run(tmp_path, toy_schema_df):
    # Remove the three unresolved-by-design joined columns so this run is clean end to end; keep
    # every source-table row as-is (the leftover weird_shared_col/column_from_unmapped_table rows
    # under their source tables are harmless — build_domain_map only iterates the joined table's
    # own rows, never a bare source table's).
    clean_df = toy_schema_df[
        ~toy_schema_df["column_name"].isin(
            ["weird_shared_col", "column_from_unmapped_table", "totally_missing_column"]
        )
        | (toy_schema_df["source_table"] != mod.JOINED_TABLE)
    ]
    schema_csv = tmp_path / "schema.csv"
    clean_df.to_csv(schema_csv, index=False)

    output_csv = tmp_path / "out" / "column_domain_map.csv"
    rc = mod.main(["--schema-csv", str(schema_csv), "--output", str(output_csv)])

    assert rc == 0
    assert output_csv.exists()
    written = pd.read_csv(output_csv)
    assert set(written["column_name"]) == {"GEOID", "pop_total", "svi_overall"}


def test_main_returns_nonzero_when_unresolved_rows_remain(tmp_path, toy_schema_df):
    schema_csv = tmp_path / "schema.csv"
    toy_schema_df.to_csv(schema_csv, index=False)
    output_csv = tmp_path / "out" / "column_domain_map.csv"

    rc = mod.main(["--schema-csv", str(schema_csv), "--output", str(output_csv)])

    assert rc == 1
    # The file is still written even on a failing run, so a human can inspect exactly what's
    # unresolved without re-running anything.
    assert output_csv.exists()


def test_main_returns_a_clean_error_code_and_message_when_schema_csv_is_missing(tmp_path, capsys):
    missing_csv = tmp_path / "does_not_exist.csv"
    output_csv = tmp_path / "out" / "column_domain_map.csv"

    rc = mod.main(["--schema-csv", str(missing_csv), "--output", str(output_csv)])

    assert rc == 2
    assert not output_csv.exists()
    captured = capsys.readouterr()
    assert "not found" in captured.err
    assert "inspect_national_strata_schema.py" in captured.err
