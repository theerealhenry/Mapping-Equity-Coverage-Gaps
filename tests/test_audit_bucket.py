"""
tests/test_audit_bucket.py — Stage 2, Step 5.

Tests scripts/audit/audit_bucket.py's pure core functions directly (no I/O at all) and its
network-touching wrappers/CLI entry point via dependency injection or monkeypatching — never
against the real bucket, matching this project's established testable-core / thin-wrapper pattern
(see tests/test_io.py, scripts/inspect_overture_sources.py).

Two design points worth calling out for future readers of this file:

1. `audit_reference_layer`/`audit_strata_table` accept a `loader=` keyword whose default is bound
   at function-definition time (ordinary Python semantics for default argument values). That means
   monkeypatching `src.io.load_reference_layer` (or even `scripts.audit.audit_bucket.
   load_reference_layer`, the name imported into this module) AFTER audit_bucket.py has already
   been imported does NOT change what audit_reference_layer's default loader calls — the default
   was already bound to the original function object at import time. The correct way to inject a
   fake loader is the `loader=` keyword argument itself (used throughout this file), and the
   correct way to test `main()` end-to-end without network access is to monkeypatch the higher-level
   `audit_reference_layer`/`audit_strata_table` module attributes, which `main()` looks up by name
   at call time (an ordinary Python global lookup, not an early-bound default) — confirmed directly
   before relying on it in test_main_* below.

2. shapely's `.is_valid` returns False (not True or NaN) for a null (None) geometry — confirmed
   directly (see audit_bucket.py's module docstring) before writing geometry_validity_stats. The
   fixtures below always include a null geometry alongside a genuinely invalid one specifically to
   prove the two are never conflated.
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
import pandera as pa
import pytest
from shapely.geometry import Polygon

from scripts.audit.audit_bucket import (
    _MAX_ERROR_MESSAGE_LENGTH,
    _classify_and_run,
    _empty_finding,
    audit_layer,
    audit_reference_layer,
    audit_strata_table,
    build_parser,
    build_report,
    duplicate_geoid_count,
    geometry_validity_stats,
    main,
    null_coverage,
)

VALID_POLY = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
BOWTIE_POLY = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])  # self-intersecting -> invalid
EMPTY_POLY = Polygon()


# -------------------------------------------------------------------------------------------
# geometry_validity_stats
# -------------------------------------------------------------------------------------------


def test_geometry_validity_stats_separates_null_from_invalid_and_empty():
    """The core subtlety this function exists to get right: a null geometry must be counted as
    null, never as invalid, even though shapely's own .is_valid says False for it too."""
    geoms = gpd.GeoSeries([VALID_POLY, BOWTIE_POLY, EMPTY_POLY, None])
    stats = geometry_validity_stats(geoms)
    assert stats == {
        "row_count": 4,
        "null_geometry_count": 1,
        "invalid_geometry_count": 1,
        "empty_geometry_count": 1,
        "geometry_type_counts": {"Polygon": 3},
    }


def test_geometry_validity_stats_all_valid():
    geoms = gpd.GeoSeries([VALID_POLY, VALID_POLY])
    stats = geometry_validity_stats(geoms)
    assert stats["null_geometry_count"] == 0
    assert stats["invalid_geometry_count"] == 0
    assert stats["empty_geometry_count"] == 0
    assert stats["geometry_type_counts"] == {"Polygon": 2}


def test_geometry_validity_stats_handles_zero_row_series_without_crashing():
    """An empty layer (0 rows) is a real, expected scenario in this project — e.g. a genuinely
    empty reference file — and must not crash the audit with a division-by-zero or similar."""
    geoms = gpd.GeoSeries([], dtype="geometry")
    stats = geometry_validity_stats(geoms)
    assert stats == {
        "row_count": 0,
        "null_geometry_count": 0,
        "invalid_geometry_count": 0,
        "empty_geometry_count": 0,
        "geometry_type_counts": {},
    }


def test_geometry_validity_stats_all_null_does_not_divide_by_zero():
    geoms = gpd.GeoSeries([None, None])
    stats = geometry_validity_stats(geoms)
    assert stats["null_geometry_count"] == 2
    assert stats["invalid_geometry_count"] == 0
    assert stats["empty_geometry_count"] == 0
    assert stats["geometry_type_counts"] == {}


# -------------------------------------------------------------------------------------------
# null_coverage
# -------------------------------------------------------------------------------------------


def test_null_coverage_computes_fraction_per_column():
    df = pd.DataFrame({"a": [1, None, 3], "b": [1, 2, 3]})
    result = null_coverage(df)
    assert result["a"] == pytest.approx(1 / 3)
    assert result["b"] == 0.0


def test_null_coverage_excludes_geometry_column_by_default():
    df = pd.DataFrame({"a": [1, None], "geometry": [VALID_POLY, None]})
    result = null_coverage(df)
    assert "geometry" not in result
    assert "a" in result


def test_null_coverage_handles_list_and_dict_valued_columns():
    """Confirmed directly (module docstring) that pandas' .isna() correctly identifies None vs. a
    real list/dict element without raising -- this pins that down for columns shaped like
    Overture's `sources` (list of structs) or Microsoft buildings' `bbox` (dict)."""
    df = pd.DataFrame({"sources": [[{"dataset": "x"}], None, [{"dataset": "y"}]]})
    result = null_coverage(df)
    assert result["sources"] == pytest.approx(1 / 3)


def test_null_coverage_custom_exclude():
    df = pd.DataFrame({"a": [1, None], "skip_me": [None, None]})
    result = null_coverage(df, exclude=("skip_me",))
    assert "skip_me" not in result
    assert result["a"] == 0.5


def test_null_coverage_on_a_zero_row_dataframe_returns_none_not_nan():
    """Regression test (Step 5 review pass): confirmed directly that pandas' .isna().mean() on a
    0-row column returns NaN, and json.dumps(NaN) emits the bare, non-spec-compliant `NaN` token.
    A genuinely empty layer must produce JSON-safe `null` (Python None) for every column instead."""
    empty_df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    result = null_coverage(empty_df)
    assert result == {"a": None}
    serialized = json.dumps(result)
    assert "NaN" not in serialized
    assert json.loads(serialized) == {"a": None}


# -------------------------------------------------------------------------------------------
# duplicate_geoid_count
# -------------------------------------------------------------------------------------------


def test_duplicate_geoid_count_counts_extra_occurrences_not_distinct_dupe_groups():
    df = pd.DataFrame({"GEOID": ["001", "002", "001", "001"]})
    assert duplicate_geoid_count(df) == 2  # keep='first' semantics: 2 extra beyond the first "001"


def test_duplicate_geoid_count_zero_when_all_unique():
    df = pd.DataFrame({"GEOID": ["001", "002", "003"]})
    assert duplicate_geoid_count(df) == 0


def test_duplicate_geoid_count_none_when_column_absent():
    """None (not 0) when there's no GEOID column at all -- "not applicable" and "confirmed zero
    duplicates" are different findings and must not be conflated in the output CSV."""
    df = pd.DataFrame({"some_other_column": [1, 2, 3]})
    assert duplicate_geoid_count(df) is None


# -------------------------------------------------------------------------------------------
# audit_layer / _empty_finding
# -------------------------------------------------------------------------------------------


def test_audit_layer_end_to_end_composition():
    gdf = gpd.GeoDataFrame(
        {"GEOID": ["001", "002", "001"], "x": [1, None, 3]},
        geometry=[VALID_POLY, BOWTIE_POLY, EMPTY_POLY],
    )
    finding = audit_layer(gdf, region="eastern-ok", layer="overture-buildings")
    assert finding["region"] == "eastern-ok"
    assert finding["layer"] == "overture-buildings"
    assert finding["status"] == "ok"
    assert finding["error_message"] == ""
    assert finding["row_count"] == 3
    assert finding["invalid_geometry_count"] == 1
    assert finding["empty_geometry_count"] == 1
    assert finding["duplicate_geoid_count"] == 1
    # geometry_type_counts and null_pct_by_column are JSON-serialized for flat CSV output
    assert json.loads(finding["geometry_type_counts"]) == {"Polygon": 3}
    parsed_null_pct = json.loads(finding["null_pct_by_column"])
    assert parsed_null_pct["x"] == pytest.approx(1 / 3)
    assert "geometry" not in parsed_null_pct


def test_empty_finding_has_the_same_keys_as_audit_layer():
    """The output CSV must have a consistent column set regardless of whether a region/layer
    combination succeeded or failed -- a schema drift between the two would produce a ragged CSV."""
    ok_finding = audit_layer(
        gpd.GeoDataFrame({"GEOID": ["001"]}, geometry=[VALID_POLY]), region="r", layer="l"
    )
    failed_finding = _empty_finding(region="r", layer="l", status="missing_file", error_message="x")
    assert set(ok_finding.keys()) == set(failed_finding.keys())


# -------------------------------------------------------------------------------------------
# _classify_and_run
# -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (FileNotFoundError("no object found"), "missing_file"),
        (NotImplementedError("no schema registered"), "not_implemented"),
        (ValueError("unexpected CRS"), "value_error"),
        (RuntimeError("read failed"), "read_error"),
        (KeyError("boom"), "error"),
    ],
)
def test_classify_and_run_maps_each_exception_type_to_a_distinct_status(exc, expected_status):
    def raiser():
        raise exc

    finding = _classify_and_run(raiser, region="eastern-ok", layer="x")
    assert finding["status"] == expected_status
    assert finding["error_message"] != ""


def test_classify_and_run_maps_schema_validation_error():
    """SchemaValidationError is the (SchemaError, SchemaErrors) tuple exported by src.schemas —
    confirmed here it's classified distinctly from a generic exception, not lumped into "error"."""

    def raiser():
        raise pa.errors.SchemaError(pa.DataFrameSchema(), None, "bad schema")

    finding = _classify_and_run(raiser, region="eastern-ok", layer="x")
    assert finding["status"] == "schema_violation"


def test_classify_and_run_truncates_very_long_error_messages():
    def raiser():
        raise pa.errors.SchemaError(pa.DataFrameSchema(), None, "x" * (_MAX_ERROR_MESSAGE_LENGTH * 2))

    finding = _classify_and_run(raiser, region="eastern-ok", layer="x")
    assert len(finding["error_message"]) <= _MAX_ERROR_MESSAGE_LENGTH


def test_classify_and_run_truncates_long_messages_for_every_exception_type_not_just_schema():
    """Regression test (Step 5 review pass): truncation must apply uniformly via _empty_finding,
    not only to the pandera schema_violation path -- a raw pyarrow/OSError or a generic exception
    can also produce an arbitrarily long message and must not be allowed to dominate the CSV."""

    def raiser():
        raise RuntimeError("y" * (_MAX_ERROR_MESSAGE_LENGTH * 2))

    finding = _classify_and_run(raiser, region="eastern-ok", layer="x")
    assert finding["status"] == "read_error"
    assert len(finding["error_message"]) <= _MAX_ERROR_MESSAGE_LENGTH


def test_max_error_message_length_has_real_headroom_above_a_realistic_lazy_validation_worst_case():
    """Regression test for a real bug found during the Step 5 review pass: the cap was originally
    2000, set before src/schemas.py's validate_layer switched to lazy=True (Stage 2 Step 5 review
    pass). Once every independent schema violation is aggregated into one report instead of just
    the first, the message can legitimately grow past what 2000 chars holds -- confirmed directly
    that a realistic worst case (most of HIFLD_FACILITY_SCHEMA's ~12 declared columns wrong or
    missing at once) produced 2557 characters on its own, which the old cap would have silently
    truncated, discarding real violations and undercutting the entire reason lazy=True exists.
    This pins the cap at a value with real headroom above that measured case, not just an
    arbitrary round number."""
    measured_realistic_worst_case_chars = 2557
    assert _MAX_ERROR_MESSAGE_LENGTH > measured_realistic_worst_case_chars * 2


def test_classify_and_run_returns_ok_finding_on_success():
    def loader():
        return gpd.GeoDataFrame({"GEOID": ["001"]}, geometry=[VALID_POLY])

    finding = _classify_and_run(loader, region="eastern-ok", layer="x")
    assert finding["status"] == "ok"
    assert finding["row_count"] == 1


def test_classify_and_run_does_not_let_a_bug_in_audit_layer_itself_escape(monkeypatch):
    """The real robustness gap this test guards: an earlier version of _classify_and_run called
    audit_layer() OUTSIDE its try/except, on the (untested) assumption that a layer which already
    loaded and passed pandera validation is "safe" to summarize. At the real scale this script
    runs at (10M+ row layers, per docs/data_manifest.md), an unexpected bug in the audit's own
    statistics code must not be able to propagate up and crash the entire batch run, discarding
    every finding already computed for every other region/layer combination. A loader that
    succeeds but whose result blows up inside audit_layer must be classified, not left to escape."""
    import scripts.audit.audit_bucket as ab

    def exploding_audit_layer(gdf, *, region, layer):
        raise TypeError("simulated bug in the audit's own statistics code")

    monkeypatch.setattr(ab, "audit_layer", exploding_audit_layer)

    def loader():
        return gpd.GeoDataFrame({"GEOID": ["001"]}, geometry=[VALID_POLY])

    finding = ab._classify_and_run(loader, region="eastern-ok", layer="x")
    assert finding["status"] == "audit_error"
    assert "TypeError" in finding["error_message"]


# -------------------------------------------------------------------------------------------
# audit_reference_layer / audit_strata_table (injectable loader)
# -------------------------------------------------------------------------------------------


def test_audit_reference_layer_uses_injected_loader():
    def fake_loader(region, layer):
        assert region == "eastern-ok"
        assert layer == "overture-buildings"
        return gpd.GeoDataFrame({"GEOID": ["001"]}, geometry=[VALID_POLY])

    finding = audit_reference_layer("eastern-ok", "overture-buildings", loader=fake_loader)
    assert finding["status"] == "ok"
    assert finding["row_count"] == 1


def test_audit_reference_layer_propagates_missing_file_via_injected_loader():
    def fake_loader(region, layer):
        raise FileNotFoundError("gone")

    finding = audit_reference_layer("south-central-tx", "census-tribal-subdivisions", loader=fake_loader)
    assert finding["status"] == "missing_file"


def test_audit_strata_table_cross_checks_expected_row_count_when_correct():
    def fake_loader(region, table):
        n = 1192  # eastern-ok's real REGION_TRACT_COUNTS value
        return gpd.GeoDataFrame({"GEOID": [f"{i:03d}" for i in range(n)]}, geometry=[VALID_POLY] * n)

    finding = audit_strata_table("eastern-ok", "census-tracts", loader=fake_loader)
    assert finding["status"] == "ok"
    assert finding["expected_row_count"] == 1192
    assert finding["row_count_matches_expected"] is True


def test_audit_strata_table_flags_row_count_mismatch():
    def fake_loader(region, table):
        return gpd.GeoDataFrame({"GEOID": ["001", "002"]}, geometry=[VALID_POLY, VALID_POLY])

    finding = audit_strata_table("eastern-ok", "census-tracts", loader=fake_loader)
    assert finding["status"] == "ok"
    assert finding["expected_row_count"] == 1192
    assert finding["row_count_matches_expected"] is False


def test_audit_strata_table_row_count_check_is_none_for_a_non_census_tracts_table():
    """The REGION_TRACT_COUNTS cross-check is scoped to census-tracts specifically -- any other
    strata table must not silently get a (meaningless) expected-count comparison."""

    def fake_loader(region, table):
        return gpd.GeoDataFrame({"GEOID": ["001"]}, geometry=[VALID_POLY])

    finding = audit_strata_table("eastern-ok", "some-other-table", loader=fake_loader)
    assert finding["expected_row_count"] is None
    assert finding["row_count_matches_expected"] is None


def test_audit_strata_table_row_count_check_is_none_when_the_load_failed():
    """A failed load must not produce a misleading expected_row_count/row_count_matches_expected
    pair -- both stay None, matching _empty_finding's own None-filled shape."""

    def fake_loader(region, table):
        raise FileNotFoundError("missing, e.g. south-central-tx's tribal-subdivisions file")

    finding = audit_strata_table("south-central-tx", "census-tracts", loader=fake_loader)
    assert finding["status"] == "missing_file"
    assert finding["expected_row_count"] is None
    assert finding["row_count_matches_expected"] is None


# -------------------------------------------------------------------------------------------
# build_report
# -------------------------------------------------------------------------------------------


def test_build_report_keeps_row_count_as_a_clean_integer_when_a_row_in_the_batch_failed():
    """Regression test (Step 5 review pass): confirmed directly that naive `pd.DataFrame(findings)`
    silently upcasts row_count (and every other count column) to float64 -- rendering a perfectly
    clean layer's row_count as "1.0" in the CSV -- the instant ANY row in the same batch has a
    None/NaN count, which is a real, routine scenario (a failed layer load alongside successful
    ones). build_report must keep these as genuine (nullable) integers regardless."""
    ok_finding = audit_layer(
        gpd.GeoDataFrame({"GEOID": ["001"]}, geometry=[VALID_POLY]), region="r", layer="overture-buildings"
    )
    failed_finding = _empty_finding(region="r", layer="strata/census-tracts", status="missing_file", error_message="x")

    report = build_report([ok_finding, failed_finding])
    assert str(report["row_count"].dtype) == "Int64"
    assert report["row_count"].iloc[0] == 1
    csv_text = report.to_csv(index=False)
    assert ",1,0,0,0," in csv_text  # the clean row's counts, not "1.0,0.0,0.0,0.0"
    assert "1.0" not in csv_text


def test_build_report_casts_row_count_matches_expected_to_nullable_boolean():
    finding_true = dict(
        audit_layer(gpd.GeoDataFrame({"GEOID": ["001"]}, geometry=[VALID_POLY]), region="r", layer="l"),
        expected_row_count=1,
        row_count_matches_expected=True,
    )
    finding_na = _empty_finding(region="r", layer="l2", status="missing_file", error_message="x")
    finding_na["expected_row_count"] = None
    finding_na["row_count_matches_expected"] = None

    report = build_report([finding_true, finding_na])
    assert str(report["row_count_matches_expected"].dtype) == "boolean"
    assert bool(report["row_count_matches_expected"].iloc[0]) is True
    assert report["row_count_matches_expected"].iloc[1] is pd.NA


# -------------------------------------------------------------------------------------------
# CLI argument parsing
# -------------------------------------------------------------------------------------------


def test_build_parser_defaults_to_none_meaning_everything():
    args = build_parser().parse_args([])
    assert args.region is None
    assert args.layers is None
    assert args.skip_strata is False


def test_build_parser_accepts_multiple_regions_and_layers():
    args = build_parser().parse_args(
        ["--region", "eastern-ok", "maricopa-az", "--layers", "overture-buildings", "--skip-strata"]
    )
    assert args.region == ["eastern-ok", "maricopa-az"]
    assert args.layers == ["overture-buildings"]
    assert args.skip_strata is True


def test_build_parser_rejects_unknown_region():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--region", "not-a-real-region"])


def test_build_parser_rejects_unknown_layer():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--layers", "not-a-real-layer"])


def test_region_flag_with_zero_values_still_falls_back_to_all_regions():
    """`--region` (bare, no values) parses to an empty list, which is falsy in Python -- main()'s
    `args.region if args.region else list(REGIONS)` must fall back to "all regions" here, the same
    as when --region is omitted entirely, not silently audit zero regions."""
    args = build_parser().parse_args(["--region"])
    assert args.region == []


# -------------------------------------------------------------------------------------------
# main() end-to-end (audit_reference_layer / audit_strata_table monkeypatched — no network)
# -------------------------------------------------------------------------------------------


def _fake_ok_reference_finding(region, layer):
    return {
        "region": region,
        "layer": layer,
        "status": "ok",
        "error_message": "",
        "row_count": 1,
        "null_geometry_count": 0,
        "invalid_geometry_count": 0,
        "empty_geometry_count": 0,
        "geometry_type_counts": "{}",
        "null_pct_by_column": "{}",
        "duplicate_geoid_count": 0,
    }


def _fake_ok_strata_finding(region, table):
    finding = _fake_ok_reference_finding(region, f"strata/{table}")
    finding["expected_row_count"] = None
    finding["row_count_matches_expected"] = None
    return finding


def _fake_missing_strata_finding(region, table):
    finding = _empty_finding(
        region=region, layer=f"strata/{table}", status="missing_file", error_message="missing for test"
    )
    finding["expected_row_count"] = None
    finding["row_count_matches_expected"] = None
    return finding


def test_main_writes_csv_and_returns_zero_when_everything_ok(tmp_path, monkeypatch):
    import scripts.audit.audit_bucket as ab

    monkeypatch.setattr(ab, "audit_reference_layer", _fake_ok_reference_finding)
    monkeypatch.setattr(ab, "audit_strata_table", _fake_ok_strata_finding)

    out_path = tmp_path / "findings.csv"
    exit_code = main(["--region", "eastern-ok", "--layers", "overture-buildings", "--output", str(out_path)])

    assert exit_code == 0
    assert out_path.exists()
    report = pd.read_csv(out_path)
    assert len(report) == 2  # one reference layer + one strata table
    assert (report["status"] == "ok").all()


def test_main_returns_one_and_reports_failures_when_a_layer_fails(tmp_path, monkeypatch):
    import scripts.audit.audit_bucket as ab

    monkeypatch.setattr(ab, "audit_reference_layer", _fake_ok_reference_finding)
    monkeypatch.setattr(ab, "audit_strata_table", _fake_missing_strata_finding)

    out_path = tmp_path / "findings.csv"
    exit_code = main(["--region", "south-central-tx", "--layers", "overture-buildings", "--output", str(out_path)])

    assert exit_code == 1
    report = pd.read_csv(out_path)
    assert "missing_file" in set(report["status"])


def test_main_skip_strata_flag_omits_strata_rows(tmp_path, monkeypatch):
    import scripts.audit.audit_bucket as ab

    monkeypatch.setattr(ab, "audit_reference_layer", _fake_ok_reference_finding)

    def fail_if_called(region, table):
        raise AssertionError("audit_strata_table must not be called when --skip-strata is set")

    monkeypatch.setattr(ab, "audit_strata_table", fail_if_called)

    out_path = tmp_path / "findings.csv"
    exit_code = main(
        ["--region", "eastern-ok", "--layers", "overture-buildings", "--skip-strata", "--output", str(out_path)]
    )

    assert exit_code == 0
    report = pd.read_csv(out_path)
    assert len(report) == 1
    assert not report["layer"].str.startswith("strata/").any()


def test_main_creates_output_directory_if_missing(tmp_path, monkeypatch):
    import scripts.audit.audit_bucket as ab

    monkeypatch.setattr(ab, "audit_reference_layer", _fake_ok_reference_finding)
    monkeypatch.setattr(ab, "audit_strata_table", _fake_ok_strata_finding)

    out_path = tmp_path / "nested" / "does" / "not" / "exist" / "findings.csv"
    exit_code = main(["--region", "eastern-ok", "--layers", "overture-buildings", "--output", str(out_path)])

    assert exit_code == 0
    assert out_path.exists()


def test_main_audits_every_region_and_layer_by_default(tmp_path, monkeypatch):
    """Confirms main()'s default (no --region/--layers) genuinely fans out across all four regions
    and every registered layer, not just the one combination other tests happen to pass."""
    import scripts.audit.audit_bucket as ab

    calls = []

    def recording_reference(region, layer):
        calls.append((region, layer))
        return _fake_ok_reference_finding(region, layer)

    monkeypatch.setattr(ab, "audit_reference_layer", recording_reference)
    monkeypatch.setattr(ab, "audit_strata_table", _fake_ok_strata_finding)

    out_path = tmp_path / "findings.csv"
    exit_code = main(["--output", str(out_path)])

    assert exit_code == 0
    from src.config import REGIONS
    from src.schemas import LAYER_SCHEMAS

    assert {region for region, _ in calls} == set(REGIONS)
    assert {layer for _, layer in calls} == set(LAYER_SCHEMAS)
    assert len(calls) == len(REGIONS) * len(LAYER_SCHEMAS)
