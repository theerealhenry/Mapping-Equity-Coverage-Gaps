"""
tests/test_inspect_national_strata_schema.py — Stage 3, Step 1.

Tests scripts/inspect_national_strata_schema.py's pure/thin functions directly, against real local
parquet fixtures written in each test (via pyarrow + pyarrow.fs.LocalFileSystem) — never against the
real bucket, matching this project's established testable-core / thin-wrapper testing pattern (see
tests/test_audit_bucket.py, tests/test_io.py). `inspect_table_schema`, `schema_risk_findings`, and
`_build_report` are pure functions with no network dependency at all; `main()` is tested via
monkeypatching `inspect_national_table` (the module-level name main() looks up by name at call
time — the same pattern tests/test_audit_bucket.py already establishes and documents for
audit_bucket.py's main()). This suite proves the script's logic is correct before it is ever run
against the real 26-table `strata/national/` bucket contents.
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow.fs import LocalFileSystem

import scripts.inspect_national_strata_schema as inspect_module
from scripts.inspect_national_strata_schema import (
    _build_report,
    inspect_national_table,
    inspect_table_schema,
    main,
    schema_risk_findings,
)


def _write_parquet(path, table: pa.Table) -> None:
    pq.write_table(table, str(path))


# -------------------------------------------------------------------------------------------
# inspect_table_schema
# -------------------------------------------------------------------------------------------


def test_inspect_table_schema_reads_columns_in_order_and_row_count(tmp_path):
    """The core subtlety this function exists to get right: footer-only inspection must report
    real column order and dtypes and the real row count, without reading any column data."""
    path = tmp_path / "fixture.parquet"
    table = pa.table(
        {
            "GEOID": pa.array(["01001950100", "01001950200"], type=pa.string()),
            "E_TOTPOP": pa.array([1200, 340], type=pa.int64()),
            "RPL_THEMES": pa.array([0.42, None], type=pa.float64()),
        }
    )
    _write_parquet(path, table)

    result = inspect_table_schema(LocalFileSystem(), str(path), label="fixture")

    assert "error" not in result
    assert result["num_rows"] == 2
    assert result["columns"] == [
        ("GEOID", "string"),
        ("E_TOTPOP", "int64"),
        ("RPL_THEMES", "double"),
    ]


def test_inspect_table_schema_reports_an_error_for_a_missing_file_without_raising(tmp_path):
    """A missing/malformed table is a real, expected possibility in this bucket (South-Central
    Texas is already confirmed missing a file every other region has) — this must never raise,
    only report, so one bad table can't sink every other table's inspection in main()'s loop."""
    missing_path = tmp_path / "does_not_exist.parquet"
    result = inspect_table_schema(LocalFileSystem(), str(missing_path), label="missing")
    assert "error" in result
    assert "columns" not in result
    assert "num_rows" not in result


def test_inspect_table_schema_handles_a_zero_row_table(tmp_path):
    """A genuinely empty table is a real, expected scenario (mirrors
    tests/test_audit_bucket.py's zero-row geometry coverage) and must not crash."""
    path = tmp_path / "empty.parquet"
    table = pa.table({"GEOID": pa.array([], type=pa.string())})
    _write_parquet(path, table)
    result = inspect_table_schema(LocalFileSystem(), str(path), label="empty")
    assert result["num_rows"] == 0
    assert result["columns"] == [("GEOID", "string")]


def test_inspect_table_schema_reports_a_duplicate_column_name_without_crashing(tmp_path):
    """A table with a genuinely repeated column name is unusual but not impossible for a
    CSV-derived government export re-saved as parquet — confirms this layer doesn't choke on it;
    schema_risk_findings (tested below) is what actually flags it as a finding."""
    path = tmp_path / "dupe_columns.parquet"
    schema = pa.schema([("GEOID", pa.string()), ("VALUE", pa.float64()), ("GEOID", pa.string())])
    table = pa.table(
        [pa.array(["01001950100"]), pa.array([1.0]), pa.array(["01001950100"])], schema=schema
    )
    _write_parquet(path, table)
    result = inspect_table_schema(LocalFileSystem(), str(path), label="dupe")
    assert "error" not in result
    assert result["columns"] == [("GEOID", "string"), ("VALUE", "double"), ("GEOID", "string")]


# -------------------------------------------------------------------------------------------
# inspect_national_table (thin wrapper — path construction is injectable)
# -------------------------------------------------------------------------------------------


def test_inspect_national_table_uses_the_injected_path_function(tmp_path):
    """Confirms the wrapper calls path_fn(table) to build the path, rather than hardcoding the
    real S3 path builder — the same injectable-dependency pattern used throughout this project's
    scripts (see audit_bucket.py's `loader=` keyword) to make network-touching code testable."""
    path = tmp_path / "national-svi-tract-table.parquet"
    table = pa.table({"GEOID": pa.array(["01001950100"], type=pa.string())})
    _write_parquet(path, table)

    captured: dict = {}

    def fake_path_fn(table_name: str) -> str:
        captured["table_name"] = table_name
        return str(path)

    result = inspect_national_table(
        LocalFileSystem(), "national-svi-tract-table", path_fn=fake_path_fn
    )

    assert captured["table_name"] == "national-svi-tract-table"
    assert result["table"] == "national-svi-tract-table"
    assert result["key"] == str(path)
    assert result["columns"] == [("GEOID", "string")]


def test_inspect_national_table_propagates_an_error_without_raising(tmp_path):
    missing_path = tmp_path / "missing.parquet"
    result = inspect_national_table(
        LocalFileSystem(), "some-table", path_fn=lambda table: str(missing_path)
    )
    assert "error" in result
    assert result["table"] == "some-table"


# -------------------------------------------------------------------------------------------
# schema_risk_findings
# -------------------------------------------------------------------------------------------


def test_schema_risk_findings_flags_missing_geoid_column_with_no_alias():
    results = [
        {"table": "national-noaa-ghcn-stations", "columns": [("station_id", "string")]},
        {"table": "national-svi-tract-table", "columns": [("GEOID", "string")]},
    ]
    findings = schema_risk_findings(results)
    assert findings["missing_geoid"] == ["national-noaa-ghcn-stations"]
    assert findings["possible_geoid_alias"] == {}
    assert findings["unsafe_geoid_dtype"] == {}
    assert findings["duplicate_column_names"] == {}


def test_schema_risk_findings_surfaces_a_geoid_alias_separately_from_missing():
    """A column named differently-cased or differently-named (GEOID10, fips_code) must be
    surfaced as a candidate, not silently conflated with "no key column at all"."""
    results = [
        {"table": "national-legacy-table", "columns": [("GEOID10", "string"), ("value", "double")]},
        {"table": "national-other-table", "columns": [("fips_code", "int64")]},
    ]
    findings = schema_risk_findings(results)
    assert findings["missing_geoid"] == ["national-legacy-table", "national-other-table"]
    assert findings["possible_geoid_alias"] == {
        "national-legacy-table": ["GEOID10"],
        "national-other-table": ["fips_code"],
    }


def test_schema_risk_findings_flags_an_integer_geoid_dtype():
    """The core regression this check exists to catch: GEOID declared as an int type would
    silently drop a leading-zero state FIPS downstream (this project's single most-cited real
    risk) -- confirmed here that the check actually fires for exactly that case."""
    results = [
        {"table": "national-bad-table", "columns": [("GEOID", "int64"), ("value", "double")]},
    ]
    findings = schema_risk_findings(results)
    assert findings["missing_geoid"] == []
    assert findings["unsafe_geoid_dtype"] == {"national-bad-table": "int64"}


def test_schema_risk_findings_accepts_large_string_and_string_view_as_safe():
    results = [
        {"table": "t1", "columns": [("GEOID", "large_string")]},
        {"table": "t2", "columns": [("GEOID", "string_view")]},
    ]
    findings = schema_risk_findings(results)
    assert findings["unsafe_geoid_dtype"] == {}


def test_schema_risk_findings_flags_duplicate_column_names_and_excludes_from_geoid_checks():
    """A table with a repeated column name must be reported as its own finding, and must NOT also
    be run through the GEOID checks against a dict(columns) lookup that already lost information
    about it -- confirmed here it lands only in duplicate_column_names, nowhere else."""
    results = [
        {
            "table": "national-messy-table",
            "columns": [("GEOID", "string"), ("VALUE", "double"), ("GEOID", "int64")],
        },
    ]
    findings = schema_risk_findings(results)
    assert findings["duplicate_column_names"] == {"national-messy-table": ["GEOID"]}
    assert findings["missing_geoid"] == []
    assert findings["unsafe_geoid_dtype"] == {}


def test_schema_risk_findings_skips_tables_that_failed_to_inspect():
    """A table that errored out has no `columns` key at all -- this must not KeyError, it must
    simply be excluded from every check (it's already reported as a hard failure elsewhere)."""
    results = [
        {"table": "national-broken-table", "error": "FileNotFoundError: nope"},
        {"table": "national-good-table", "columns": [("GEOID", "string")]},
    ]
    findings = schema_risk_findings(results)
    assert findings["missing_geoid"] == []
    assert findings["unsafe_geoid_dtype"] == {}
    assert findings["duplicate_column_names"] == {}


def test_schema_risk_findings_falls_back_to_label_key_without_raising():
    """Confirms the function tolerates raw inspect_table_schema output ("label", not "table") --
    it must never itself be the reason a run fails, per its own docstring."""
    results = [{"label": "some-fixture", "columns": [("station_id", "string")]}]
    findings = schema_risk_findings(results)
    assert findings["missing_geoid"] == ["some-fixture"]


def test_schema_risk_findings_on_an_empty_results_list():
    assert schema_risk_findings([]) == {
        "missing_geoid": [],
        "possible_geoid_alias": {},
        "unsafe_geoid_dtype": {},
        "duplicate_column_names": {},
    }


# -------------------------------------------------------------------------------------------
# _build_report
# -------------------------------------------------------------------------------------------


def test_build_report_includes_a_sentinel_row_for_a_failed_table():
    """The core fix this function exists to make: a failed table must still appear in the CSV --
    as one row with its error_message populated -- never silently vanish."""
    results = [
        {"table": "national-good-table", "columns": [("GEOID", "string")], "num_rows": 5},
        {"table": "national-broken-table", "error": "RuntimeError: boom"},
    ]
    report = _build_report(results)
    assert len(report) == 2
    good = report[report["source_table"] == "national-good-table"].iloc[0]
    assert good["column_name"] == "GEOID"
    assert good["position"] == 0
    assert good["table_num_rows"] == 5
    assert good["error_message"] == ""

    broken = report[report["source_table"] == "national-broken-table"].iloc[0]
    assert broken["column_name"] is None or str(broken["column_name"]) == "None"
    assert broken["error_message"] == "RuntimeError: boom"


def test_build_report_keeps_integer_columns_clean_when_a_row_in_the_batch_failed():
    """Regression test, mirroring scripts/audit/audit_bucket.py's build_report: mixing one failed
    table's None-valued row into the batch must not upcast position/table_num_rows to float64 for
    every OTHER table's real integer values."""
    results = [
        {
            "table": "national-good-table",
            "columns": [("GEOID", "string"), ("VALUE", "double")],
            "num_rows": 42,
        },
        {"table": "national-broken-table", "error": "boom"},
    ]
    report = _build_report(results)
    assert str(report["position"].dtype) == "Int64"
    assert str(report["table_num_rows"].dtype) == "Int64"
    good_rows = report[report["source_table"] == "national-good-table"]
    assert list(good_rows["position"]) == [0, 1]
    assert list(good_rows["table_num_rows"]) == [42, 42]


def test_build_report_on_all_successful_tables_has_no_error_rows():
    results = [
        {"table": "t1", "columns": [("GEOID", "string")], "num_rows": 1},
    ]
    report = _build_report(results)
    assert (report["error_message"] == "").all()


def test_build_report_on_empty_results_has_expected_columns():
    report = _build_report([])
    assert len(report) == 0
    assert list(report.columns) == [
        "source_table",
        "column_name",
        "position",
        "arrow_dtype",
        "table_num_rows",
        "error_message",
    ]


# -------------------------------------------------------------------------------------------
# main() — via monkeypatching inspect_national_table, no network access
# -------------------------------------------------------------------------------------------


def test_main_returns_zero_and_writes_the_csv_when_every_table_succeeds(tmp_path, monkeypatch):
    def fake_inspect(filesystem, table):
        return {"table": table, "columns": [("GEOID", "string")], "num_rows": 1, "key": table}

    monkeypatch.setattr(inspect_module, "inspect_national_table", fake_inspect)
    output_path = tmp_path / "national_strata_schema_raw.csv"
    monkeypatch.setattr(inspect_module, "DEFAULT_OUTPUT_PATH", output_path)

    exit_code = main()

    assert exit_code == 0
    assert output_path.exists()
    written = output_path.read_text()
    assert "national-strata-tract-table" in written
    assert "error_message" in written


def test_main_returns_one_and_still_writes_a_sentinel_row_when_a_table_fails(tmp_path, monkeypatch):
    def fake_inspect(filesystem, table):
        if table == "national-svi-tract-table":
            return {"table": table, "error": "RuntimeError: simulated failure"}
        return {"table": table, "columns": [("GEOID", "string")], "num_rows": 1, "key": table}

    monkeypatch.setattr(inspect_module, "inspect_national_table", fake_inspect)
    output_path = tmp_path / "national_strata_schema_raw.csv"
    monkeypatch.setattr(inspect_module, "DEFAULT_OUTPUT_PATH", output_path)

    exit_code = main()

    assert exit_code == 1
    written = output_path.read_text()
    assert "national-svi-tract-table" in written
    assert "simulated failure" in written


def test_main_reports_missing_joined_table_gracefully(tmp_path, monkeypatch):
    """If the joined table itself fails to inspect, main() must still complete (not crash) and
    still exit 1 -- this is arguably the single worst-case real outcome of this script's actual
    run, so it must be handled explicitly, not just fall out of generic error handling by luck."""

    def fake_inspect(filesystem, table):
        if table == "national-strata-tract-table":
            return {"table": table, "error": "AccessDenied"}
        return {"table": table, "columns": [("GEOID", "string")], "num_rows": 1, "key": table}

    monkeypatch.setattr(inspect_module, "inspect_national_table", fake_inspect)
    output_path = tmp_path / "national_strata_schema_raw.csv"
    monkeypatch.setattr(inspect_module, "DEFAULT_OUTPUT_PATH", output_path)

    exit_code = main()

    assert exit_code == 1
    assert output_path.exists()
