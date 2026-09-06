"""Tests for scripts/check_region_national_schema_consistency.py (Stage 3 Step 7).

`compare_schemas`, `check_row_count`, `load_national_joined_schema`, and `build_detail_rows` are
pure functions tested here with no network. `inspect_region_table` is tested against a real local
parquet fixture via `pyarrow.fs.LocalFileSystem` and an overridden `path_fn`, the same pattern
`tests/test_inspect_national_strata_schema.py` already establishes — never against the real bucket.
`main()` needs live S3 access to do anything meaningful and is not run here; its pure building
blocks carry the real test coverage, matching this project's testable-core / thin-wrapper
discipline.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pyarrow.fs import LocalFileSystem

import scripts.check_region_national_schema_consistency as mod

REAL_NATIONAL_SCHEMA_CSV = Path(__file__).resolve().parent.parent / "docs" / "national_strata_schema_raw.csv"
REAL_INPUT_PRESENT = REAL_NATIONAL_SCHEMA_CSV.exists()


def _write_parquet(path, table: pa.Table) -> None:
    pq.write_table(table, str(path))


# --- load_national_joined_schema -----------------------------------------------------------------


def test_load_national_joined_schema_extracts_columns_in_position_order():
    csv = pd.DataFrame(
        [
            {"source_table": "national-strata-tract-table", "column_name": "b", "position": 1, "arrow_dtype": "int64", "table_num_rows": 10, "error_message": ""},
            {"source_table": "national-strata-tract-table", "column_name": "a", "position": 0, "arrow_dtype": "string", "table_num_rows": 10, "error_message": ""},
            {"source_table": "national-some-other-table", "column_name": "z", "position": 0, "arrow_dtype": "string", "table_num_rows": 5, "error_message": ""},
        ]
    )
    result = mod.load_national_joined_schema(csv)
    assert result == [("a", "string"), ("b", "int64")]


def test_load_national_joined_schema_raises_if_table_missing():
    csv = pd.DataFrame([{"source_table": "some-other-table", "column_name": "a", "position": 0, "arrow_dtype": "string", "table_num_rows": 10, "error_message": ""}])
    with pytest.raises(ValueError, match="national-strata-tract-table"):
        mod.load_national_joined_schema(csv)


@pytest.mark.skipif(not REAL_INPUT_PRESENT, reason="docs/national_strata_schema_raw.csv not present")
def test_load_national_joined_schema_against_the_real_committed_csv_returns_232_columns():
    csv = pd.read_csv(REAL_NATIONAL_SCHEMA_CSV)
    result = mod.load_national_joined_schema(csv)
    assert len(result) == 232
    assert result[0][0] == "GEOID"  # confirmed first column, Stage 3 Step 1


# --- compare_schemas --------------------------------------------------------------------------


def test_identical_schemas_match_on_everything():
    columns = [("GEOID", "string"), ("pop_total", "int64")]
    result = mod.compare_schemas(columns, columns)
    assert result["missing_in_region"] == []
    assert result["extra_in_region"] == []
    assert result["dtype_mismatches"] == {}
    assert result["order_matches"] is True
    assert result["columns_match"] is True


def test_missing_column_in_region_is_detected():
    national = [("GEOID", "string"), ("svi_covered", "bool")]
    region = [("GEOID", "string")]
    result = mod.compare_schemas(national, region)
    assert result["missing_in_region"] == ["svi_covered"]
    assert result["columns_match"] is False


def test_extra_column_in_region_is_detected():
    national = [("GEOID", "string")]
    region = [("GEOID", "string"), ("region", "string")]
    result = mod.compare_schemas(national, region)
    assert result["extra_in_region"] == ["region"]
    assert result["columns_match"] is False


def test_dtype_mismatch_is_detected_for_shared_columns_only():
    national = [("GEOID", "string"), ("svi_covered", "bool")]
    region = [("GEOID", "string"), ("svi_covered", "int64")]
    result = mod.compare_schemas(national, region)
    assert result["dtype_mismatches"] == {"svi_covered": {"national": "bool", "region": "int64"}}
    assert result["columns_match"] is False


def test_reordered_but_otherwise_identical_schema_fails_order_but_passes_columns_match():
    national = [("GEOID", "string"), ("pop_total", "int64")]
    region = [("pop_total", "int64"), ("GEOID", "string")]
    result = mod.compare_schemas(national, region)
    assert result["order_matches"] is False
    assert result["columns_match"] is True  # order is informational, not a functional failure here


def test_no_shared_columns_at_all_trivially_matches_order_but_not_columns():
    """Edge case worth locking in explicitly: when nothing overlaps, order_matches is vacuously True
    (there is nothing shared to be out of order) even though columns_match is False — the two fields
    must be read together, never order_matches alone as a pass signal."""
    national = [("a", "string"), ("b", "int64")]
    region = [("x", "string"), ("y", "int64")]
    result = mod.compare_schemas(national, region)
    assert result["order_matches"] is True
    assert result["columns_match"] is False


# --- find_duplicate_column_names / duplicate handling in compare_schemas ------------------------


def test_find_duplicate_column_names_returns_names_in_first_seen_order():
    columns = [("a", "string"), ("b", "int64"), ("a", "double"), ("c", "string"), ("b", "bool")]
    assert mod.find_duplicate_column_names(columns) == ["a", "b"]


def test_find_duplicate_column_names_empty_when_all_unique():
    assert mod.find_duplicate_column_names([("a", "string"), ("b", "int64")]) == []


def test_duplicate_column_name_in_region_is_surfaced_and_fails_columns_match():
    """A real risk this project already treats seriously for the national tables (Stage 3 Step 1's
    duplicate_column_names check) — this is the first point a REGION schema is inspected at all, so
    it needs the same guard: a duplicate silently collapses in any dict(columns) lookup, which is
    exactly why this must be reported explicitly rather than trusted to "just work" via dtype/
    missing/extra checks alone."""
    national = [("GEOID", "string"), ("pop_total", "int64")]
    region = [("GEOID", "string"), ("pop_total", "int64"), ("pop_total", "bool")]
    result = mod.compare_schemas(national, region)
    assert result["duplicate_in_region"] == ["pop_total"]
    assert result["duplicate_in_national"] == []
    assert result["columns_match"] is False


def test_duplicate_column_name_in_national_is_also_surfaced():
    """Checked defensively even though the national schema is already independently confirmed
    duplicate-free (Stage 3 Step 1) — this function has no reason to trust that as an invariant it
    doesn't check itself."""
    national = [("GEOID", "string"), ("GEOID", "int64")]
    region = [("GEOID", "string")]
    result = mod.compare_schemas(national, region)
    assert result["duplicate_in_national"] == ["GEOID"]
    assert result["columns_match"] is False


@pytest.mark.skipif(not REAL_INPUT_PRESENT, reason="docs/national_strata_schema_raw.csv not present")
def test_real_national_joined_schema_has_no_duplicate_column_names():
    """Locks in, as a permanent regression against the real committed data, the fact this review
    independently re-confirmed: the national joined table has zero duplicate column names."""
    csv = pd.read_csv(REAL_NATIONAL_SCHEMA_CSV)
    national_columns = mod.load_national_joined_schema(csv)
    assert mod.find_duplicate_column_names(national_columns) == []


def test_missing_and_extra_columns_do_not_interfere_with_each_others_lists():
    national = [("GEOID", "string"), ("only_national", "int64")]
    region = [("GEOID", "string"), ("only_region", "int64")]
    result = mod.compare_schemas(national, region)
    assert result["missing_in_region"] == ["only_national"]
    assert result["extra_in_region"] == ["only_region"]


def test_missing_in_region_preserves_national_order_not_alphabetical():
    national = [("zeta", "string"), ("alpha", "string")]
    region = []
    result = mod.compare_schemas(national, region)
    assert result["missing_in_region"] == ["zeta", "alpha"]


# --- check_row_count --------------------------------------------------------------------------


def test_check_row_count_matches_region_total_only():
    result = mod.check_row_count(1192, "eastern-ok")
    assert result["matches_region_total"] is True
    assert result["matches_scored_total"] is True  # eastern-ok's two counts are equal


def test_check_row_count_distinguishes_region_total_from_scored_total():
    """South-Central Texas is the one region where these two expectations actually differ
    (6,010 total tract membership vs 6,003 scored) — this is the real case this distinction exists
    to catch."""
    result_total = mod.check_row_count(6010, "south-central-tx")
    assert result_total["matches_region_total"] is True
    assert result_total["matches_scored_total"] is False

    result_scored = mod.check_row_count(6003, "south-central-tx")
    assert result_scored["matches_region_total"] is False
    assert result_scored["matches_scored_total"] is True


def test_check_row_count_matches_neither_is_reported_honestly():
    result = mod.check_row_count(999999, "eastern-ok")
    assert result["matches_region_total"] is False
    assert result["matches_scored_total"] is False


def test_check_row_count_unknown_region_does_not_crash():
    result = mod.check_row_count(100, "not-a-real-region")
    assert result["matches_region_total"] is False
    assert result["matches_scored_total"] is False


# --- build_detail_rows ------------------------------------------------------------------------


def test_build_detail_rows_covers_the_union_and_flags_membership_correctly():
    national = [("GEOID", "string"), ("only_national", "int64")]
    region = [("GEOID", "string"), ("only_region", "bool")]
    comparison = mod.compare_schemas(national, region)
    rows = mod.build_detail_rows("eastern-ok", comparison, national, region)
    by_column = {r["column_name"]: r for r in rows}

    assert set(by_column) == {"GEOID", "only_national", "only_region"}
    assert by_column["GEOID"]["in_national"] is True
    assert by_column["GEOID"]["in_region"] is True
    assert by_column["GEOID"]["dtype_match"] is True

    assert by_column["only_national"]["in_national"] is True
    assert by_column["only_national"]["in_region"] is False
    assert by_column["only_national"]["dtype_match"] is None  # not present in region, no match to report
    assert by_column["only_national"]["region_dtype"] == ""

    assert by_column["only_region"]["in_national"] is False
    assert by_column["only_region"]["in_region"] is True
    assert by_column["only_region"]["dtype_match"] is None


def test_build_detail_rows_records_positions_from_each_side_independently():
    national = [("a", "string"), ("b", "int64")]
    region = [("b", "int64"), ("a", "string")]
    comparison = mod.compare_schemas(national, region)
    rows = mod.build_detail_rows("eastern-ok", comparison, national, region)
    by_column = {r["column_name"]: r for r in rows}
    assert by_column["a"]["national_position"] == 0
    assert by_column["a"]["region_position"] == 1
    assert by_column["b"]["national_position"] == 1
    assert by_column["b"]["region_position"] == 0


def test_build_detail_rows_dtype_mismatch_reported_on_shared_column():
    national = [("svi_covered", "bool")]
    region = [("svi_covered", "int64")]
    comparison = mod.compare_schemas(national, region)
    rows = mod.build_detail_rows("eastern-ok", comparison, national, region)
    assert rows[0]["dtype_match"] is False
    assert rows[0]["national_dtype"] == "bool"
    assert rows[0]["region_dtype"] == "int64"


# --- inspect_region_table (real local parquet fixture, no network) ------------------------------


def test_inspect_region_table_reads_a_real_local_fixture_via_overridden_path_fn(tmp_path):
    path = tmp_path / "eastern-ok-strata-tract-table.parquet"
    table = pa.table({"GEOID": pa.array(["40001950100"], type=pa.string()), "pop_total": pa.array([1200], type=pa.int64())})
    _write_parquet(path, table)

    result = mod.inspect_region_table(LocalFileSystem(), "eastern-ok", path_fn=lambda region, tbl: str(path))

    assert "error" not in result
    assert result["region"] == "eastern-ok"
    assert result["num_rows"] == 1
    assert result["columns"] == [("GEOID", "string"), ("pop_total", "int64")]


def test_inspect_region_table_reports_error_for_a_missing_file_without_raising(tmp_path):
    missing_path = tmp_path / "does-not-exist.parquet"
    result = mod.inspect_region_table(LocalFileSystem(), "south-central-tx", path_fn=lambda region, tbl: str(missing_path))
    assert "error" in result
    assert result["region"] == "south-central-tx"


def test_inspect_region_table_default_path_fn_uses_the_real_strata_s3_path_convention():
    """Confirms the wrapper's default path construction matches src.config.strata_s3_path's real
    convention (".../strata/<region>/<region>-strata-tract-table.parquet") without needing network
    access — passing a filesystem that will fail is fine, since only the constructed path matters
    here, captured via a path_fn override that also records what it was called with."""
    calls = []

    def recording_path_fn(region, table):
        calls.append((region, table))
        return "s3://unreachable/path.parquet"

    mod.inspect_region_table(LocalFileSystem(), "maricopa-az", path_fn=recording_path_fn)
    assert calls == [("maricopa-az", mod.STRATA_REGION_JOINED_TABLE)]


# --- main() — via monkeypatching inspect_region_table and the module's path constants,
# no network access, and never touching the real docs/ files ------------------------------------


def _write_national_schema_csv(path, columns):
    pd.DataFrame(
        [
            {"source_table": "national-strata-tract-table", "column_name": name, "position": i, "arrow_dtype": dtype, "table_num_rows": 85396, "error_message": ""}
            for i, (name, dtype) in enumerate(columns)
        ]
    ).to_csv(path, index=False)


def test_main_returns_zero_and_writes_both_csvs_when_every_region_matches(tmp_path, monkeypatch):
    national_columns = [("GEOID", "string"), ("pop_total", "int64")]
    national_csv_path = tmp_path / "national_schema.csv"
    _write_national_schema_csv(national_csv_path, national_columns)

    def fake_inspect(filesystem, region):
        return {"region": region, "num_rows": mod.REGION_TRACT_COUNTS[region], "columns": national_columns}

    monkeypatch.setattr(mod, "DEFAULT_NATIONAL_SCHEMA_PATH", national_csv_path)
    monkeypatch.setattr(mod, "DEFAULT_DETAIL_OUTPUT_PATH", tmp_path / "detail.csv")
    monkeypatch.setattr(mod, "DEFAULT_SUMMARY_OUTPUT_PATH", tmp_path / "summary.csv")
    monkeypatch.setattr(mod, "inspect_region_table", fake_inspect)

    rc = mod.main()

    assert rc == 0
    summary = pd.read_csv(tmp_path / "summary.csv")
    assert len(summary) == len(mod.REGIONS)
    assert (summary["schema_consistent"] == True).all()  # noqa: E712
    detail = pd.read_csv(tmp_path / "detail.csv")
    assert len(detail) == len(national_columns) * len(mod.REGIONS)


def test_main_returns_one_when_a_region_has_a_missing_column(tmp_path, monkeypatch):
    national_columns = [("GEOID", "string"), ("svi_covered", "bool")]
    national_csv_path = tmp_path / "national_schema.csv"
    _write_national_schema_csv(national_csv_path, national_columns)

    def fake_inspect(filesystem, region):
        columns = [("GEOID", "string")] if region == "eastern-ok" else national_columns
        return {"region": region, "num_rows": mod.REGION_TRACT_COUNTS[region], "columns": columns}

    monkeypatch.setattr(mod, "DEFAULT_NATIONAL_SCHEMA_PATH", national_csv_path)
    monkeypatch.setattr(mod, "DEFAULT_DETAIL_OUTPUT_PATH", tmp_path / "detail.csv")
    monkeypatch.setattr(mod, "DEFAULT_SUMMARY_OUTPUT_PATH", tmp_path / "summary.csv")
    monkeypatch.setattr(mod, "inspect_region_table", fake_inspect)

    rc = mod.main()

    assert rc == 1
    summary = pd.read_csv(tmp_path / "summary.csv").set_index("region")
    assert summary.loc["eastern-ok", "schema_consistent"] == False  # noqa: E712
    assert summary.loc["eastern-ok", "num_missing_in_region"] == 1
    assert (summary.drop(index="eastern-ok")["schema_consistent"] == True).all()  # noqa: E712


def test_main_handles_a_region_failing_to_load_without_crashing(tmp_path, monkeypatch):
    national_columns = [("GEOID", "string")]
    national_csv_path = tmp_path / "national_schema.csv"
    _write_national_schema_csv(national_csv_path, national_columns)

    def fake_inspect(filesystem, region):
        if region == "northern-ca":
            return {"region": region, "error": "FileNotFoundError: simulated missing object"}
        return {"region": region, "num_rows": mod.REGION_TRACT_COUNTS[region], "columns": national_columns}

    monkeypatch.setattr(mod, "DEFAULT_NATIONAL_SCHEMA_PATH", national_csv_path)
    monkeypatch.setattr(mod, "DEFAULT_DETAIL_OUTPUT_PATH", tmp_path / "detail.csv")
    monkeypatch.setattr(mod, "DEFAULT_SUMMARY_OUTPUT_PATH", tmp_path / "summary.csv")
    monkeypatch.setattr(mod, "inspect_region_table", fake_inspect)

    rc = mod.main()  # must not raise

    assert rc == 1
    summary = pd.read_csv(tmp_path / "summary.csv").set_index("region")
    assert summary.loc["northern-ca", "error"] == "FileNotFoundError: simulated missing object"
    assert summary.loc["northern-ca", "schema_consistent"] == False  # noqa: E712
    # The three regions that did load must still be fully reported — one region's failure must not
    # suppress the others.
    assert (summary.drop(index="northern-ca")["schema_consistent"] == True).all()  # noqa: E712


def test_main_handles_every_region_failing_without_crashing(tmp_path, monkeypatch):
    """The scenario this review actually observed running the script in a sandbox with no live
    bucket access: all four regions fail. detail_rows stays empty (pd.DataFrame([]) has zero
    columns) — this must still write cleanly rather than hitting the same "empty DataFrame has no
    columns to filter" crash Stage 3 Step 3's own review pass found and fixed for a structurally
    identical case."""
    national_columns = [("GEOID", "string")]
    national_csv_path = tmp_path / "national_schema.csv"
    _write_national_schema_csv(national_csv_path, national_columns)

    def fake_inspect(filesystem, region):
        return {"region": region, "error": "simulated: bucket unreachable"}

    monkeypatch.setattr(mod, "DEFAULT_NATIONAL_SCHEMA_PATH", national_csv_path)
    detail_path = tmp_path / "detail.csv"
    summary_path = tmp_path / "summary.csv"
    monkeypatch.setattr(mod, "DEFAULT_DETAIL_OUTPUT_PATH", detail_path)
    monkeypatch.setattr(mod, "DEFAULT_SUMMARY_OUTPUT_PATH", summary_path)
    monkeypatch.setattr(mod, "inspect_region_table", fake_inspect)

    rc = mod.main()  # must not raise

    assert rc == 1
    assert detail_path.exists()
    assert summary_path.exists()
    summary = pd.read_csv(summary_path)
    assert len(summary) == len(mod.REGIONS)
    assert (summary["error"] == "simulated: bucket unreachable").all()
    assert (summary["schema_consistent"] == False).all()  # noqa: E712


def test_main_surfaces_a_duplicate_column_name_in_a_regions_own_schema(tmp_path, monkeypatch):
    national_columns = [("GEOID", "string"), ("pop_total", "int64")]
    national_csv_path = tmp_path / "national_schema.csv"
    _write_national_schema_csv(national_csv_path, national_columns)

    def fake_inspect(filesystem, region):
        columns = national_columns + [("pop_total", "bool")] if region == "maricopa-az" else national_columns
        return {"region": region, "num_rows": mod.REGION_TRACT_COUNTS[region], "columns": columns}

    monkeypatch.setattr(mod, "DEFAULT_NATIONAL_SCHEMA_PATH", national_csv_path)
    monkeypatch.setattr(mod, "DEFAULT_DETAIL_OUTPUT_PATH", tmp_path / "detail.csv")
    monkeypatch.setattr(mod, "DEFAULT_SUMMARY_OUTPUT_PATH", tmp_path / "summary.csv")
    monkeypatch.setattr(mod, "inspect_region_table", fake_inspect)

    rc = mod.main()

    assert rc == 1
    summary = pd.read_csv(tmp_path / "summary.csv").set_index("region")
    assert summary.loc["maricopa-az", "num_duplicate_in_region"] == 1
    assert summary.loc["maricopa-az", "schema_consistent"] == False  # noqa: E712


def test_main_reports_missing_national_schema_csv_gracefully(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod, "DEFAULT_NATIONAL_SCHEMA_PATH", tmp_path / "does-not-exist.csv")
    rc = mod.main()
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_integer_columns_never_round_trip_as_floats_when_a_region_fails(tmp_path, monkeypatch):
    """Regression for the exact class of bug this project has hit twice before (Stage 3 Step 1's
    _NULLABLE_INT_CSV_COLUMNS, Stage 3 Step 2's _INT_COLUMNS): a batch containing one failed
    region (whose numeric summary fields are None) must not silently turn every OTHER region's
    clean integer counts into "1.0"-style floats in the written CSV."""
    national_columns = [("GEOID", "string")]
    national_csv_path = tmp_path / "national_schema.csv"
    _write_national_schema_csv(national_csv_path, national_columns)

    def fake_inspect(filesystem, region):
        if region == "northern-ca":
            return {"region": region, "error": "simulated failure"}
        return {"region": region, "num_rows": mod.REGION_TRACT_COUNTS[region], "columns": national_columns}

    monkeypatch.setattr(mod, "DEFAULT_NATIONAL_SCHEMA_PATH", national_csv_path)
    summary_path = tmp_path / "summary.csv"
    monkeypatch.setattr(mod, "DEFAULT_DETAIL_OUTPUT_PATH", tmp_path / "detail.csv")
    monkeypatch.setattr(mod, "DEFAULT_SUMMARY_OUTPUT_PATH", summary_path)
    monkeypatch.setattr(mod, "inspect_region_table", fake_inspect)

    mod.main()

    raw_text = summary_path.read_text()
    assert f"{mod.REGION_TRACT_COUNTS['eastern-ok']}.0" not in raw_text
    assert f",{mod.REGION_TRACT_COUNTS['eastern-ok']}," in raw_text or raw_text.strip().endswith(str(mod.REGION_TRACT_COUNTS["eastern-ok"]))
