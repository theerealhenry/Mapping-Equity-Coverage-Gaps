"""Tests for scripts/build_data_dictionary.py (Stage 3 Step 8).

Every merge/render function is pure and tested here with no network. `read_frac_inside_aoi_column`
is tested against a real local parquet fixture via `pyarrow.fs.LocalFileSystem` and an overridden
`path_fn`, the same pattern every prior live-touching wrapper in this project uses — never against
the real bucket. `main()` is exercised end-to-end with `--skip-live-read` against the real,
already-committed docs/*.csv inputs, which is the one meaningful thing that can be verified without
network access; the live frac_inside_aoi read itself needs Henry's machine, matching every other
live-bucket step in this project.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pyarrow.fs import LocalFileSystem

import scripts.build_data_dictionary as mod
from src.config import NATIONAL_STRATA_SOURCE_TABLES

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
REAL_INPUTS_PRESENT = all(
    (DOCS / name).exists()
    for name in (
        "national_strata_schema_raw.csv",
        "column_domain_map.csv",
        "coverage_null_profile.csv",
        "column_classification.csv",
        "column_candidate_hypotheses.csv",
        "region_national_schema_consistency.csv",
    )
)


def _write_parquet(path, table: pa.Table) -> None:
    pq.write_table(table, str(path))


# --- load_national_joined_columns -----------------------------------------------------------------


def test_load_national_joined_columns_extracts_in_position_order():
    csv = pd.DataFrame(
        [
            {"source_table": "national-strata-tract-table", "column_name": "b", "position": 1, "arrow_dtype": "int64"},
            {"source_table": "national-strata-tract-table", "column_name": "a", "position": 0, "arrow_dtype": "string"},
            {"source_table": "national-other-table", "column_name": "z", "position": 0, "arrow_dtype": "string"},
        ]
    )
    result = mod.load_national_joined_columns(csv)
    assert result["column_name"].tolist() == ["a", "b"]
    assert result["dtype"].tolist() == ["string", "int64"]
    assert result["national_position"].tolist() == [0, 1]


def test_load_national_joined_columns_raises_if_table_missing():
    csv = pd.DataFrame([{"source_table": "some-other-table", "column_name": "a", "position": 0, "arrow_dtype": "string"}])
    with pytest.raises(ValueError, match="national-strata-tract-table"):
        mod.load_national_joined_columns(csv)


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/*.csv not present")
def test_load_national_joined_columns_against_the_real_committed_csv_returns_232_columns():
    csv = pd.read_csv(DOCS / "national_strata_schema_raw.csv")
    result = mod.load_national_joined_columns(csv)
    assert len(result) == 232
    assert result["column_name"].iloc[0] == "GEOID"


# --- summarize_region_presence --------------------------------------------------------------------


def _region_row(region, column_name, in_national, in_region):
    return {"region": region, "column_name": column_name, "in_national": in_national, "in_region": in_region}


_FAKE_FOUR_REGIONS = ["a", "b", "c", "d"]


def test_summarize_region_presence_all_present():
    df = pd.DataFrame(
        [_region_row(r, "GEOID", True, True) for r in ("a", "b", "c", "d")]
    )
    result = mod.summarize_region_presence(df, all_regions=_FAKE_FOUR_REGIONS)
    row = result.iloc[0]
    assert row["present_in_regions"] == "a;b;c;d"
    assert row["missing_from_regions"] == ""
    assert row["present_in_all_four_regions"] == True  # noqa: E712


def test_summarize_region_presence_missing_in_some():
    df = pd.DataFrame(
        [
            _region_row("b", "AWATER", True, False),
            _region_row("a", "AWATER", True, False),
            _region_row("c", "AWATER", True, True),
            _region_row("d", "AWATER", True, True),
        ]
    )
    result = mod.summarize_region_presence(df, all_regions=_FAKE_FOUR_REGIONS)
    row = result.iloc[0]
    assert row["present_in_regions"] == "c;d"
    assert row["missing_from_regions"] == "a;b"
    assert row["present_in_all_four_regions"] == False  # noqa: E712


def test_summarize_region_presence_present_in_fewer_than_four_rows_is_not_all_four():
    # A column that only appears in 3 of the 4 regions' detail rows at all (should never happen
    # against the real always-four-region output, but must not be silently treated as complete).
    df = pd.DataFrame(
        [
            _region_row("a", "weird_col", False, True),
            _region_row("b", "weird_col", False, True),
            _region_row("c", "weird_col", False, True),
        ]
    )
    result = mod.summarize_region_presence(df, all_regions=_FAKE_FOUR_REGIONS)
    row = result.iloc[0]
    assert row["present_in_all_four_regions"] == False  # noqa: E712


def test_summarize_region_presence_missing_from_regions_catches_regions_with_zero_rows():
    # Regression test for a real, confirmed bug: when a column is present in only SOME regions,
    # Step 7's real per-region detail CSV never emits a row at all for a region that lacks the
    # column entirely (as opposed to a row with in_region=False) — so a region absent from `group`
    # outright must still show up in `missing_from_regions`, not just a region with an explicit
    # in_region=False row. Before the fix, `missing_from_regions` was computed as
    # `~group["in_region"]`, which is empty whenever every row present in the group happens to have
    # in_region=True (even though two of the four regions never produced a row for this column at
    # all) — silently reporting `missing_from_regions=""` for a column that is genuinely absent from
    # half the regions, and this exact case (present_in_all_four_regions correctly False, but
    # missing_from_regions silently wrong) had no test coverage at all.
    df = pd.DataFrame(
        [
            _region_row("a", "region_only_col", False, True),
            _region_row("b", "region_only_col", False, True),
            # No rows at all for regions "c" or "d" — they never carry this column.
        ]
    )
    result = mod.summarize_region_presence(df, all_regions=_FAKE_FOUR_REGIONS)
    row = result.iloc[0]
    assert row["present_in_regions"] == "a;b"
    assert row["missing_from_regions"] == "c;d"
    assert row["present_in_all_four_regions"] == False  # noqa: E712


def test_summarize_region_presence_defaults_to_the_real_four_regions():
    # The production default (no all_regions override) must use src.config.REGIONS, not some
    # arbitrary count — this is what the real call site in main() relies on.
    from src.config import REGIONS

    df = pd.DataFrame([_region_row(REGIONS[0], "some_col", True, True)])
    result = mod.summarize_region_presence(df)
    row = result.iloc[0]
    assert row["missing_from_regions"] == ";".join(sorted(REGIONS[1:]))
    assert row["present_in_all_four_regions"] == False  # noqa: E712


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/region_national_schema_consistency.csv not present")
def test_summarize_region_presence_against_real_data_matches_step7_known_findings():
    df = pd.read_csv(DOCS / "region_national_schema_consistency.csv")
    result = mod.summarize_region_presence(df).set_index("column_name")
    for name in ("state_usps", "state_name", "AWATER", "INTPTLAT", "INTPTLON", "tract_vintage"):
        assert result.loc[name, "present_in_all_four_regions"] == False  # noqa: E712
        assert result.loc[name, "missing_from_regions"] == "eastern-ok;maricopa-az;northern-ca;south-central-tx"
    assert result.loc["frac_inside_aoi", "present_in_all_four_regions"] == True  # noqa: E712
    assert result.loc["GEOID", "present_in_all_four_regions"] == True  # noqa: E712


# --- profile_series ---------------------------------------------------------------------------


def test_profile_series_basic():
    series = pd.Series([1.0, 2.0, 3.0, None])
    result = mod.profile_series(series)
    assert result["n_rows"] == 4
    assert result["n_null"] == 1
    assert result["pct_null"] == 0.25
    assert result["n_distinct"] == 3
    assert result["min"] == 1.0
    assert result["max"] == 3.0
    assert result["mean"] == 2.0


def test_profile_series_all_null_does_not_crash():
    series = pd.Series([None, None])
    result = mod.profile_series(series)
    assert result["n_null"] == 2
    assert math.isnan(result["min"])
    assert math.isnan(result["max"])
    assert math.isnan(result["mean"])


def test_profile_series_empty_series_does_not_crash():
    series = pd.Series([], dtype="float64")
    result = mod.profile_series(series)
    assert result["n_rows"] == 0
    assert math.isnan(result["pct_null"])


# --- build_frac_inside_aoi_row ------------------------------------------------------------------


_TEMPLATE_COLUMNS = [
    "column_name", "national_position", "dtype",
    "source_table", "domain", "attribution_method",
    "n_null", "pct_null", "n_distinct", "min", "max", "mean", "sentinel_note",
    "role", "allowed_for_scoring", "scoring_reason", "allowed_for_bias", "bias_reason",
    "candidate_hypotheses", "candidate_hypotheses_reason",
    "present_in_regions", "missing_from_regions", "present_in_all_four_regions",
    "region_only", "profile_scope", "vintage_status", "vintage_note",
]


def test_build_frac_inside_aoi_row_has_every_template_column_in_order():
    profile = {"n_rows": 100, "n_null": 5, "pct_null": 0.05, "n_distinct": 42, "min": 0.1, "max": 1.0, "mean": 0.7}
    row = mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS, profile)
    assert list(row.keys()) == _TEMPLATE_COLUMNS
    assert row["column_name"] == "frac_inside_aoi"
    assert row["region_only"] is True
    assert row["allowed_for_scoring"] is False
    assert row["allowed_for_bias"] is True
    assert row["candidate_hypotheses"] == "Tribal Sub-type + Edge Effect"
    assert row["present_in_all_four_regions"] == True  # noqa: E712
    assert row["missing_from_regions"] == ""
    assert row["n_distinct"] == 42
    assert "9,389" not in row["profile_scope"]  # not a hardcoded figure — comes from the profile
    assert "100" in row["profile_scope"]


def test_build_frac_inside_aoi_row_constant_value_override_matches_the_real_live_finding():
    # The exact real-world result Henry's live run produced: constant at 1.0 across all 9,386
    # tracts in all four regions. This must trigger the same hard, data-driven override Step 5
    # already established (compute_allowed_for_bias: n_distinct <= 1 forces allowed_for_bias=False
    # regardless of role) — NOT the structural geometry_measure-based True this column would
    # otherwise get if it varied.
    profile = {"n_rows": 9386, "n_null": 0, "pct_null": 0.0, "n_distinct": 1, "min": 1.0, "max": 1.0, "mean": 1.0}
    row = mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS, profile, regions_included=list(mod.REGIONS))
    assert row["allowed_for_bias"] is False
    assert row["candidate_hypotheses"] == ""
    assert "constant" in row["bias_reason"]
    assert "9,386" in row["bias_reason"]
    assert "1.0" in row["bias_reason"]
    assert row["candidate_hypotheses_reason"] != ""


def test_build_frac_inside_aoi_row_uses_the_structural_classification_when_real_data_does_vary():
    profile = {"n_rows": 9386, "n_null": 0, "pct_null": 0.0, "n_distinct": 50, "min": 0.1, "max": 1.0, "mean": 0.9}
    row = mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS, profile)
    assert row["allowed_for_bias"] is True
    assert row["candidate_hypotheses"] == "Tribal Sub-type + Edge Effect"
    assert "PROVISIONAL" not in row["bias_reason"]


def test_build_frac_inside_aoi_row_flags_the_classification_as_provisional_with_no_live_data():
    # The offline --skip-live-read default: n_rows=0 means neither the constant-value override nor
    # the "confirmed to vary" case can actually be evaluated — the row must say so explicitly rather
    # than silently presenting a confirmed-looking classification.
    profile = {"n_rows": 0, "n_null": 0, "pct_null": float("nan"), "n_distinct": 0, "min": float("nan"), "max": float("nan"), "mean": float("nan")}
    row = mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS, profile, regions_included=[])
    assert row["allowed_for_bias"] is True
    assert "PROVISIONAL" in row["bias_reason"]


def test_build_frac_inside_aoi_row_raises_loudly_if_main_catalog_schema_grows_a_new_column():
    profile = {"n_rows": 1, "n_null": 0, "pct_null": 0.0, "n_distinct": 1, "min": 0.0, "max": 1.0, "mean": 0.5}
    with pytest.raises(AssertionError, match="missing catalog column"):
        mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS + ["a_brand_new_catalog_column"], profile)


def test_build_frac_inside_aoi_row_profile_scope_reflects_regions_included_default_all_four():
    profile = {"n_rows": 9386, "n_null": 0, "pct_null": 0.0, "n_distinct": 100, "min": 0.0, "max": 1.0, "mean": 0.9}
    row = mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS, profile)
    assert "9,386" in row["profile_scope"]
    assert "4 region(s)" in row["profile_scope"]


def test_build_frac_inside_aoi_row_profile_scope_reflects_a_partial_region_set():
    # Mirrors main()'s real behavior when one region's live read fails: profile_scope must say so,
    # not silently claim "4 regions" for numbers that only came from 3.
    profile = {"n_rows": 3000, "n_null": 0, "pct_null": 0.0, "n_distinct": 50, "min": 0.0, "max": 1.0, "mean": 0.8}
    row = mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS, profile, regions_included=["eastern-ok", "maricopa-az"])
    assert "2 region(s)" in row["profile_scope"]
    assert "eastern-ok" in row["profile_scope"]
    assert "maricopa-az" in row["profile_scope"]


def test_build_frac_inside_aoi_row_profile_scope_reflects_zero_regions():
    profile = {"n_rows": 0, "n_null": 0, "pct_null": float("nan"), "n_distinct": 0, "min": float("nan"), "max": float("nan"), "mean": float("nan")}
    row = mod.build_frac_inside_aoi_row(_TEMPLATE_COLUMNS, profile, regions_included=[])
    assert "0 region(s): none" in row["profile_scope"]


# --- build_catalog -----------------------------------------------------------------------------


def _minimal_inputs():
    national_columns = pd.DataFrame(
        [
            {"column_name": "GEOID", "national_position": 0, "dtype": "string"},
            {"column_name": "AWATER", "national_position": 1, "dtype": "double"},
        ]
    )
    domain_map = pd.DataFrame(
        [
            {"column_name": "GEOID", "source_table": "national-census-tract-table", "domain": "geography", "attribution_method": "shared-backbone"},
            {"column_name": "AWATER", "source_table": "national-census-tract-table", "domain": "geography", "attribution_method": "shared-backbone"},
        ]
    )
    null_profile = pd.DataFrame(
        [
            {"scope": "national", "column_name": "GEOID", "n_null": 0, "pct_null": 0.0, "n_distinct": 2, "min": None, "max": None, "mean": None, "sentinel_note": None},
            {"scope": "national", "column_name": "AWATER", "n_null": 0, "pct_null": 0.0, "n_distinct": 2, "min": 0.0, "max": 100.0, "mean": 50.0, "sentinel_note": None},
            {"scope": "eastern-ok", "column_name": "GEOID", "n_null": 0, "pct_null": 0.0, "n_distinct": 2, "min": None, "max": None, "mean": None, "sentinel_note": None},
        ]
    )
    classification = pd.DataFrame(
        [
            {"column_name": "GEOID", "role": "identifier", "allowed_for_scoring": False, "scoring_reason": "r1", "allowed_for_bias": False, "bias_reason": "b1"},
            {"column_name": "AWATER", "role": "geometry_measure", "allowed_for_scoring": False, "scoring_reason": "r1", "allowed_for_bias": True, "bias_reason": "b2"},
        ]
    )
    candidate_hypotheses = pd.DataFrame(
        [
            {"column_name": "GEOID", "candidate_hypotheses": "", "candidate_hypotheses_reason": "n/a"},
            {"column_name": "AWATER", "candidate_hypotheses": "Tribal Sub-type + Edge Effect", "candidate_hypotheses_reason": "geometry"},
        ]
    )
    region_presence = pd.DataFrame(
        [
            {"column_name": "GEOID", "present_in_regions": "a;b;c;d", "missing_from_regions": "", "present_in_all_four_regions": True},
            {"column_name": "AWATER", "present_in_regions": "", "missing_from_regions": "a;b;c;d", "present_in_all_four_regions": False},
        ]
    )
    return national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence


def test_build_catalog_merges_everything_and_appends_the_extra_row():
    national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence = _minimal_inputs()
    extra_row = {
        "column_name": "frac_inside_aoi", "national_position": pd.NA, "dtype": "double",
        "source_table": "strata-tract-table (region-only)", "domain": "geography", "attribution_method": "x",
        "n_null": 0, "pct_null": 0.0, "n_distinct": 1, "min": 0.0, "max": 1.0, "mean": 0.5, "sentinel_note": "",
        "role": "geometry_measure", "allowed_for_scoring": False, "scoring_reason": "x", "allowed_for_bias": True, "bias_reason": "x",
        "candidate_hypotheses": "Tribal Sub-type + Edge Effect", "candidate_hypotheses_reason": "x",
        "present_in_regions": "a;b;c;d", "missing_from_regions": "", "present_in_all_four_regions": True,
        "region_only": True, "profile_scope": "region-combined", "vintage_status": "not_applicable", "vintage_note": "x",
    }
    catalog = mod.build_catalog(national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence, extra_row)
    assert len(catalog) == 3
    assert catalog["column_name"].tolist() == ["GEOID", "AWATER", "frac_inside_aoi"]
    awater = catalog.loc[catalog["column_name"] == "AWATER"].iloc[0]
    assert awater["allowed_for_bias"] == True  # noqa: E712
    assert awater["present_in_all_four_regions"] == False  # noqa: E712
    assert awater["vintage_status"] == "confirmed"  # national-census-tract-table
    geoid = catalog.loc[catalog["column_name"] == "GEOID"].iloc[0]
    assert geoid["n_distinct"] == 2
    assert catalog["region_only"].tolist() == [False, False, True]


def test_build_catalog_raises_on_a_duplicated_upstream_row_instead_of_silently_fanning_out():
    national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence = _minimal_inputs()
    # Simulate an upstream file (e.g. Step 5's classification) having silently grown a duplicate
    # row for one column — this must fail loudly (validate="one_to_one"), not silently double the
    # row count for that column.
    classification = pd.concat([classification, classification.iloc[[0]]], ignore_index=True)
    extra_row = {c: None for c in national_columns.columns}
    extra_row.update({"column_name": "z", "region_only": True})
    with pytest.raises(Exception):  # pandas raises MergeError, a ValueError subclass
        mod.build_catalog(national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence, extra_row)


def _make_extra_row(national_columns):
    return {
        "column_name": "frac_inside_aoi", "national_position": pd.NA, "dtype": "double",
        "source_table": "strata-tract-table (region-only)", "domain": "geography", "attribution_method": "x",
        "n_null": 0, "pct_null": 0.0, "n_distinct": 1, "min": 0.0, "max": 1.0, "mean": 0.5, "sentinel_note": "",
        "role": "geometry_measure", "allowed_for_scoring": False, "scoring_reason": "x", "allowed_for_bias": True, "bias_reason": "x",
        "candidate_hypotheses": "Tribal Sub-type + Edge Effect", "candidate_hypotheses_reason": "x",
        "present_in_regions": "a;b;c;d", "missing_from_regions": "", "present_in_all_four_regions": True,
        "region_only": True, "profile_scope": "region-combined", "vintage_status": "not_applicable", "vintage_note": "x",
    }


def test_build_catalog_raises_loudly_when_a_national_column_has_no_matching_upstream_row():
    # The real failure mode assert_catalog_completeness exists to catch: a `how="left"` merge alone
    # would silently leave AWATER's role/allowed_for_bias/etc. as NaN rather than erroring, if Step
    # 5's classification file were ever missing a row for a real national column.
    national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence = _minimal_inputs()
    classification = classification.loc[classification["column_name"] != "AWATER"]
    extra_row = _make_extra_row(national_columns)
    with pytest.raises(AssertionError, match="AWATER"):
        mod.build_catalog(national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence, extra_row)


def test_build_catalog_raises_loudly_when_a_source_table_has_no_vintage_status_entry():
    national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence = _minimal_inputs()
    domain_map = domain_map.copy()
    domain_map.loc[domain_map["column_name"] == "AWATER", "source_table"] = "national-a-brand-new-table"
    extra_row = _make_extra_row(national_columns)
    with pytest.raises(AssertionError, match="VINTAGE_STATUS_BY_SOURCE_TABLE"):
        mod.build_catalog(national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence, extra_row)


def test_build_catalog_does_not_flag_a_legitimately_blank_candidate_hypotheses_value():
    # candidate_hypotheses (unlike candidate_hypotheses_reason) IS legitimately blank for a column
    # with no matching Bias Discovery candidate (43 of 232 real columns) — assert_catalog_completeness
    # must not treat that as a missing-row failure.
    national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence = _minimal_inputs()
    candidate_hypotheses = candidate_hypotheses.copy()
    candidate_hypotheses.loc[candidate_hypotheses["column_name"] == "GEOID", "candidate_hypotheses"] = None
    extra_row = _make_extra_row(national_columns)
    catalog = mod.build_catalog(national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence, extra_row)
    assert len(catalog) == 3


# --- vintage status hand-typed dict ---------------------------------------------------------------


def test_vintage_status_keys_match_national_strata_source_tables_exactly():
    assert set(mod.VINTAGE_STATUS_BY_SOURCE_TABLE.keys()) == set(NATIONAL_STRATA_SOURCE_TABLES)


def test_every_vintage_status_entry_has_a_non_empty_status_and_note():
    for source_table, (status, note) in mod.VINTAGE_STATUS_BY_SOURCE_TABLE.items():
        assert status, f"{source_table} has an empty status"
        assert note, f"{source_table} has an empty note"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/column_domain_map.csv not present")
def test_every_real_source_table_contributing_columns_has_a_vintage_status_entry():
    domain_map = pd.read_csv(DOCS / "column_domain_map.csv")
    real_source_tables = set(domain_map["source_table"].unique())
    missing = real_source_tables - set(mod.VINTAGE_STATUS_BY_SOURCE_TABLE.keys())
    assert not missing, f"source table(s) with real columns but no vintage_status entry: {missing}"


# --- render_data_dictionary_markdown --------------------------------------------------------------


def test_render_data_dictionary_markdown_includes_missing_and_region_only_sections():
    catalog = pd.DataFrame(
        [
            {
                "column_name": "AWATER", "national_position": 1, "dtype": "double", "source_table": "national-census-tract-table",
                "domain": "geography", "role": "geometry_measure", "allowed_for_scoring": False, "allowed_for_bias": True,
                "candidate_hypotheses": "Tribal Sub-type + Edge Effect", "pct_null": 0.0, "vintage_status": "confirmed",
                "present_in_all_four_regions": False, "region_only": False, "bias_reason": "geometry",
            },
            {
                "column_name": "frac_inside_aoi", "national_position": pd.NA, "dtype": "double", "source_table": "strata-tract-table (region-only)",
                "domain": "geography", "role": "geometry_measure", "allowed_for_scoring": False, "allowed_for_bias": True,
                "candidate_hypotheses": "Tribal Sub-type + Edge Effect", "pct_null": None, "vintage_status": "not_applicable",
                "present_in_all_four_regions": True, "region_only": True, "bias_reason": "edge fraction",
            },
        ]
    )
    markdown = mod.render_data_dictionary_markdown(catalog)
    assert "## Columns absent from every region's own joined table" in markdown
    assert "`AWATER` (role=geometry_measure, allowed_for_bias=True)" in markdown
    assert "## Region-only addition" in markdown
    assert "`frac_inside_aoi`: role=geometry_measure" in markdown
    assert "### geography (1 columns)" in markdown  # only AWATER counted — frac_inside_aoi is region_only, excluded from the by-domain tables
    assert "allowed_for_scoring is False for every single row" in markdown


def test_render_data_dictionary_markdown_region_only_section_is_nan_safe_for_blank_candidate_hypotheses():
    """Direct regression lock for a real bug this project's own Step 9 review pass found: the
    region-only section's candidate_hypotheses formatting had no `pd.notna` guard (unlike the
    domain-table code path just below it, which already had one), so a blank candidate_hypotheses
    — exactly what frac_inside_aoi's own real committed row carries, once its constant-value
    override fires — rendered as the literal string 'nan' instead of '' whenever `catalog` arrived
    here having round-tripped through a plain `pd.read_csv()` (which reads a blank CSV cell back as
    float NaN). `main()`'s own real call path was never affected, since it always renders from the
    fresh in-memory catalog `build_catalog()` returns, where a blank value is a genuine Python ''
    — but any other caller that re-renders from a re-read CSV must get the same, correct '' output.
    Covered with both float NaN and pandas' NA sentinel, since a caller could hit either depending
    on how the CSV was read."""
    for blank_value in (float("nan"), pd.NA):
        catalog = pd.DataFrame(
            [
                {
                    "column_name": "frac_inside_aoi", "national_position": pd.NA, "dtype": "double",
                    "source_table": "strata-tract-table (region-only)", "domain": "geography",
                    "role": "geometry_measure", "allowed_for_scoring": False, "allowed_for_bias": False,
                    "candidate_hypotheses": blank_value, "pct_null": 0.0, "vintage_status": "not_applicable",
                    "present_in_all_four_regions": True, "region_only": True,
                    "bias_reason": "constant across all tracts",
                },
            ]
        )
        markdown = mod.render_data_dictionary_markdown(catalog)
        region_section = markdown.split("## Region-only addition")[1].split("## Columns by domain")[0]
        assert "candidate_hypotheses=''" in region_section, (
            f"blank candidate_hypotheses ({blank_value!r}) rendered incorrectly: {region_section!r}"
        )
        assert "nan" not in region_section.lower()


def test_render_data_dictionary_markdown_sorts_domain_tables_numerically_even_when_national_position_is_string_typed():
    """Direct regression lock for a second real bug this project's own Step 9 review pass found:
    domain-table rows were sorted with a bare `sort_values("national_position")`, which trusts
    whatever dtype the caller's `catalog` happens to carry for that column. `main()`'s own real call
    path always passes the fresh in-memory catalog `build_catalog()` returns, where
    `national_position` is numeric — but a caller that instead reads `schema_catalog.csv` back with
    `keep_default_na=False` (the correct way to preserve a blank candidate_hypotheses cell) gets
    `national_position` back as a STRING column, because frac_inside_aoi's own blank
    `national_position` cell prevents the whole column from being inferred as numeric. Sorted as
    strings, "10" sorts before "9" — silently scrambling every domain table with 10+ columns rather
    than raising any error. This fixture reproduces that exact shape (national_position as Python
    strings, out of numeric order) and checks the rendered table recovers strict numeric order."""
    catalog = pd.DataFrame(
        [
            {
                "column_name": name, "national_position": position, "dtype": "double",
                "source_table": "national-some-table", "domain": "heat", "role": "measurement",
                "allowed_for_scoring": False, "allowed_for_bias": True, "candidate_hypotheses": "",
                "pct_null": 0.0, "vintage_status": "confirmed", "present_in_all_four_regions": True,
                "region_only": False, "bias_reason": "x",
            }
            for name, position in [("col_0", "0"), ("col_9", "9"), ("col_10", "10"), ("col_11", "11")]
        ]
    )
    markdown = mod.render_data_dictionary_markdown(catalog)
    domain_section = markdown.split("### heat")[1]
    rendered_order = re.findall(r"`(col_\d+)`", domain_section)
    assert rendered_order == ["col_0", "col_9", "col_10", "col_11"], (
        f"domain table did not sort national_position numerically: got {rendered_order}"
    )


def test_render_data_dictionary_markdown_handles_no_missing_columns_gracefully():
    catalog = pd.DataFrame(
        [
            {
                "column_name": "GEOID", "national_position": 0, "dtype": "string", "source_table": "national-census-tract-table",
                "domain": "geography", "role": "identifier", "allowed_for_scoring": False, "allowed_for_bias": False,
                "candidate_hypotheses": "", "pct_null": 0.0, "vintage_status": "confirmed",
                "present_in_all_four_regions": True, "region_only": False, "bias_reason": "key",
            },
        ]
    )
    markdown = mod.render_data_dictionary_markdown(catalog)
    assert "## Columns absent from every region's own joined table" not in markdown
    assert "## Region-only addition" not in markdown
    assert "## Possible coded-missing sentinel values" not in markdown


def test_render_data_dictionary_markdown_surfaces_a_sentinel_note_when_present():
    catalog = pd.DataFrame(
        [
            {
                "column_name": "confidence", "national_position": 0, "dtype": "double", "source_table": "national-some-table",
                "domain": "geography", "role": "measurement", "allowed_for_scoring": False, "allowed_for_bias": True,
                "candidate_hypotheses": "", "pct_null": 0.01, "vintage_status": "confirmed",
                "present_in_all_four_regions": True, "region_only": False, "bias_reason": "x",
                "sentinel_note": "possible coded-missing sentinel(s): -1.0 in 3.2% of non-null rows",
            },
            {
                "column_name": "GEOID", "national_position": 1, "dtype": "string", "source_table": "national-census-tract-table",
                "domain": "geography", "role": "identifier", "allowed_for_scoring": False, "allowed_for_bias": False,
                "candidate_hypotheses": "", "pct_null": 0.0, "vintage_status": "confirmed",
                "present_in_all_four_regions": True, "region_only": False, "bias_reason": "key",
                "sentinel_note": None,
            },
        ]
    )
    markdown = mod.render_data_dictionary_markdown(catalog)
    assert "## Possible coded-missing sentinel values" in markdown
    assert "`confidence`" in markdown
    assert "-1.0 in 3.2%" in markdown
    # GEOID has no sentinel note and must not appear in that section's bullet list.
    sentinel_section = markdown.split("## Possible coded-missing sentinel values")[1].split("## Columns by domain")[0]
    assert "`GEOID`" not in sentinel_section


# --- read_frac_inside_aoi_column (thin live-touching wrapper, tested via LocalFileSystem) --------


def test_read_frac_inside_aoi_column_reads_only_the_requested_columns(tmp_path):
    table = pa.table(
        {
            "GEOID": pa.array(["1", "2", "3"], type=pa.string()),
            "frac_inside_aoi": pa.array([1.0, 0.5, None], type=pa.float64()),
            "some_other_column": pa.array([1, 2, 3], type=pa.int64()),
        }
    )
    fixture_path = tmp_path / "eastern-ok-strata-tract-table.parquet"
    _write_parquet(fixture_path, table)

    def fake_path_fn(region, table_name):
        assert region == "eastern-ok"
        assert table_name == mod.STRATA_REGION_JOINED_TABLE
        return str(fixture_path)

    fs = LocalFileSystem()
    series = mod.read_frac_inside_aoi_column(fs, "eastern-ok", path_fn=fake_path_fn)
    assert series.tolist()[:2] == [1.0, 0.5]
    assert pd.isna(series.tolist()[2])
    assert len(series) == 3


def test_read_frac_inside_aoi_column_early_binding_note_omitting_path_fn_uses_the_real_one(tmp_path, monkeypatch):
    # Mirrors the early-binding regression test every other wrapper in this project carries: a
    # monkeypatch of the imported `strata_s3_path` name after this module loads must NOT affect a
    # call that omits `path_fn=`, because the default was already bound at function-definition time.
    monkeypatch.setattr(mod, "strata_s3_path", lambda region, table: str(tmp_path / "should-not-be-used.parquet"))
    fs = LocalFileSystem()
    with pytest.raises(FileNotFoundError):
        # Omitting path_fn= should still attempt the REAL strata_s3_path (an s3:// path), which
        # LocalFileSystem cannot resolve — proving the monkeypatch above had no effect.
        mod.read_frac_inside_aoi_column(fs, "eastern-ok")


# --- main(), offline smoke test against the real committed inputs --------------------------------


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/*.csv not present")
def test_main_skip_live_read_runs_end_to_end_against_real_committed_inputs(tmp_path):
    catalog_output = tmp_path / "schema_catalog.csv"
    dictionary_output = tmp_path / "DATA_DICTIONARY.md"
    exit_code = mod.main(
        [
            "--skip-live-read",
            "--catalog-output", str(catalog_output),
            "--dictionary-output", str(dictionary_output),
        ]
    )
    assert exit_code == 0
    catalog = pd.read_csv(catalog_output)
    assert len(catalog) == 233
    assert catalog["column_name"].tolist().count("frac_inside_aoi") == 1
    assert not catalog["column_name"].duplicated().any()
    assert dictionary_output.exists()
    markdown = dictionary_output.read_text(encoding="utf-8")
    assert "frac_inside_aoi" in markdown
    assert "AWATER" in markdown

    # Regression guard for the "1.0"-style integer-as-float CSV corruption this project has hit
    # three times before (Steps 1, 2, and 7): appending one row (frac_inside_aoi) whose
    # national_position is pd.NA must not silently upcast the other 232 real integer positions to
    # floats in the WRITTEN FILE. Checked against the raw text, not a re-parsed DataFrame — reading
    # the CSV back with plain pd.read_csv() would itself upcast a column with any NaN to float64,
    # which would mask exactly the bug this test exists to catch.
    raw_lines = catalog_output.read_text(encoding="utf-8").splitlines()
    header = raw_lines[0].split(",")
    position_idx = header.index("national_position")
    for line in raw_lines[1:]:
        # column_name is always the first field and never contains a comma, so this simple split
        # is safe for locating the national_position field specifically, even though several other
        # fields on the same line legitimately contain commas inside quoted text.
        value = line.split(",")[position_idx]
        assert not value.endswith(".0"), f"national_position round-tripped as a float: {line!r}"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/*.csv not present")
def test_main_missing_input_file_exits_loudly_not_silently(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "DEFAULT_DOMAIN_MAP_PATH", tmp_path / "does_not_exist.csv")
    with pytest.raises(SystemExit) as exc_info:
        mod.main(["--skip-live-read"])
    assert exc_info.value.code == 2


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/*.csv not present")
def test_main_creates_the_dictionary_output_parent_directory_if_missing(tmp_path):
    # Regression guard: catalog_output's parent was already created before this review; dictionary_
    # output's was not, and would have raised FileNotFoundError on write_text for a --dictionary-
    # output pointing at a not-yet-created subdirectory (docs/ existing by default masked this).
    catalog_output = tmp_path / "schema_catalog.csv"
    dictionary_output = tmp_path / "brand_new_subdir" / "DATA_DICTIONARY.md"
    assert not dictionary_output.parent.exists()
    exit_code = mod.main(
        ["--skip-live-read", "--catalog-output", str(catalog_output), "--dictionary-output", str(dictionary_output)]
    )
    assert exit_code == 0
    assert dictionary_output.exists()


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/*.csv not present")
def test_main_isolates_a_single_region_read_failure_instead_of_crashing(tmp_path, monkeypatch):
    # Mirrors main()'s real per-region isolation: one region's live read raising must not crash the
    # whole run or lose the other three regions' contribution to the combined profile.
    def fake_read(filesystem, region, *, path_fn=None):
        if region == "northern-ca":
            raise RuntimeError("simulated network failure")
        return pd.Series([0.5, 1.0, None])

    monkeypatch.setattr(mod, "read_frac_inside_aoi_column", fake_read)
    monkeypatch.setattr(mod, "S3FileSystem", lambda **kwargs: object())

    catalog_output = tmp_path / "schema_catalog.csv"
    dictionary_output = tmp_path / "DATA_DICTIONARY.md"
    exit_code = mod.main(["--catalog-output", str(catalog_output), "--dictionary-output", str(dictionary_output)])
    assert exit_code == 0

    catalog = pd.read_csv(catalog_output)
    row = catalog.loc[catalog["column_name"] == "frac_inside_aoi"].iloc[0]
    assert "northern-ca" not in row["profile_scope"]
    assert "3 region(s)" in row["profile_scope"]
    assert "9 tracts" in row["profile_scope"]  # 3 successful regions x 3 rows each
    assert row["n_distinct"] == 2  # {0.5, 1.0} — the None in each region's series is dropped


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="docs/*.csv not present")
def test_main_aborts_without_writing_output_if_every_region_fails(tmp_path, monkeypatch):
    def fake_read(filesystem, region, *, path_fn=None):
        raise RuntimeError("simulated total outage")

    monkeypatch.setattr(mod, "read_frac_inside_aoi_column", fake_read)
    monkeypatch.setattr(mod, "S3FileSystem", lambda **kwargs: object())

    catalog_output = tmp_path / "schema_catalog.csv"
    dictionary_output = tmp_path / "DATA_DICTIONARY.md"
    exit_code = mod.main(["--catalog-output", str(catalog_output), "--dictionary-output", str(dictionary_output)])
    assert exit_code == 1
    assert not catalog_output.exists()
    assert not dictionary_output.exists()
