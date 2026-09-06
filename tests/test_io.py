"""
tests/test_io.py — Stage 2, Step 4.

Tests src/io.py entirely against local fixture files (pyarrow.fs.LocalFileSystem, or a plain local
path for the CSV loader) — no network access required, matching this project's established
testable-core / thin-real-path-wrapper pattern (see scripts/inspect_overture_sources.py). Each
public loader is tested for its full composed behavior (read -> CRS normalize -> validate/guard),
not just that "it runs" — including that a schema violation genuinely propagates end-to-end through
the public function, not just through the lower-level pieces already tested in
tests/test_geometry.py and tests/test_schemas.py individually.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pyarrow.fs import LocalFileSystem
from shapely.geometry import Polygon

import src.io as io_module
from src.geometry import GEOGRAPHIC_CRS
from src.io import (
    EXPECTED_SAMPLE_SUBMISSION_COLUMNS,
    _assert_geoid_is_string,
    _read_geoparquet,
    load_national_strata_attribute_table,
    load_reference_layer,
    load_sample_submission,
    load_strata_national_table,
    load_strata_table,
)
from src.schemas import SchemaValidationError

SAMPLE_POLYGON = Polygon([(-112.08, 33.44), (-112.07, 33.44), (-112.07, 33.45), (-112.08, 33.45)])
LOCAL_FS = LocalFileSystem()


def _write_geoparquet(tmp_path, name: str, gdf: gpd.GeoDataFrame) -> str:
    path = str(tmp_path / name)
    gdf.to_parquet(path)
    return path


@pytest.fixture
def valid_microsoft_buildings_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "height": [12.5],
            "confidence": [0.9],
            "bbox": [{"minx": -112.08, "miny": 33.44, "maxx": -112.07, "maxy": 33.45}],
        },
        geometry=[SAMPLE_POLYGON],
        crs=GEOGRAPHIC_CRS,
    )


# -------------------------------------------------------------------------------------------
# _read_geoparquet
# -------------------------------------------------------------------------------------------


def test_read_geoparquet_reads_a_valid_local_file(tmp_path, valid_microsoft_buildings_gdf):
    path = _write_geoparquet(tmp_path, "layer.parquet", valid_microsoft_buildings_gdf)
    result = _read_geoparquet(LOCAL_FS, path, context="test")
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 1


def test_read_geoparquet_missing_file_raises_filenotfounderror_with_context(tmp_path):
    missing_path = str(tmp_path / "does-not-exist.parquet")
    with pytest.raises(FileNotFoundError, match="my-test-context"):
        _read_geoparquet(LOCAL_FS, missing_path, context="my-test-context")


def test_read_geoparquet_wraps_other_failures_with_context(tmp_path):
    """A file that exists but isn't valid parquet at all should still be wrapped with context,
    not surfaced as a bare, unattributed pyarrow exception."""
    garbage_path = tmp_path / "not-actually-parquet.parquet"
    garbage_path.write_text("this is not parquet data")
    with pytest.raises(RuntimeError, match="my-garbage-context"):
        _read_geoparquet(LOCAL_FS, str(garbage_path), context="my-garbage-context")


# -------------------------------------------------------------------------------------------
# _assert_geoid_is_string
# -------------------------------------------------------------------------------------------


def test_assert_geoid_is_string_rejects_int64():
    df = pd.DataFrame({"GEOID": [4023970000]})
    with pytest.raises(ValueError, match="expected a string dtype"):
        _assert_geoid_is_string(df, context="ctx")


def test_assert_geoid_is_string_accepts_string_dtype():
    df = pd.DataFrame({"GEOID": ["04023970000"]})
    _assert_geoid_is_string(df, context="ctx")  # must not raise


def test_assert_geoid_is_string_is_a_noop_when_geoid_column_absent():
    df = pd.DataFrame({"other_column": [1, 2, 3]})
    _assert_geoid_is_string(df, context="ctx")  # must not raise


def test_assert_geoid_is_string_accepts_string_column_with_a_null_value():
    # Regression test: an object-dtype GEOID column that is a legitimate mix of real string GEOIDs
    # and a missing value (None/NaN) must NOT be misdiagnosed as an integer-coerced GEOID. Before
    # this fix, `pd.api.types.is_string_dtype` fell through to `is_all_strings`, which inspects
    # every element including nulls and returned False here — firing this guard's "integer GEOID"
    # ValueError on data that never went through integer coercion at all, purely because one row's
    # GEOID happened to be missing. `pd.api.types.infer_dtype(..., skipna=True)` (the fixed
    # implementation) correctly ignores the null when classifying the non-null values as "string".
    df = pd.DataFrame({"GEOID": ["04013010101", None, "04013010102"]})
    _assert_geoid_is_string(df, context="ctx")  # must not raise


def test_assert_geoid_is_string_still_rejects_int64_with_a_null_value():
    # Companion to the test above: a null value must not accidentally make the guard permissive for
    # the real failure mode either. A float64 column (pandas' upcast of an all-int column once a
    # NaN is introduced) must still be rejected.
    df = pd.DataFrame({"GEOID": [4023970000, None, 4023970001]})
    with pytest.raises(ValueError, match="expected a string dtype"):
        _assert_geoid_is_string(df, context="ctx")


def test_assert_geoid_is_string_is_a_noop_when_geoid_column_is_all_null():
    # Edge case for the fix: infer_dtype(skipna=True) on an all-null column returns "empty", not
    # "string" — explicitly allowed as a no-op (an all-null column is a presence/completeness
    # question for the caller, not a dtype-corruption question for this guard).
    df = pd.DataFrame({"GEOID": [None, None]})
    _assert_geoid_is_string(df, context="ctx")  # must not raise


# -------------------------------------------------------------------------------------------
# load_reference_layer
# -------------------------------------------------------------------------------------------


def test_load_reference_layer_full_pipeline(tmp_path, monkeypatch, valid_microsoft_buildings_gdf):
    """The real end-to-end proof: read -> CRS-normalize -> schema-validate, composed exactly as
    load_reference_layer is supposed to do it, using the public function itself (not its pieces
    individually)."""
    path = _write_geoparquet(tmp_path, "maricopa-az-microsoft-buildings.parquet", valid_microsoft_buildings_gdf)
    monkeypatch.setattr(io_module, "reference_s3_path", lambda region, layer: path)

    result = load_reference_layer("maricopa-az", "microsoft-buildings", filesystem=LOCAL_FS)
    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs is not None
    from src.geometry import is_crs84

    assert is_crs84(result.crs)


def test_load_reference_layer_rejects_unknown_region():
    with pytest.raises(ValueError, match="Unknown region"):
        load_reference_layer("not-a-real-region", "microsoft-buildings")


def test_load_reference_layer_propagates_schema_violation(tmp_path, monkeypatch):
    """The failure-mode proof this test suite exists for: a layer whose real data violates its
    pandera contract (an out-of-range confidence value here) must fail loudly all the way through
    the public load_reference_layer function, not just when src.schemas is called directly."""
    bad_gdf = gpd.GeoDataFrame(
        {"height": [12.5], "confidence": [-5.0], "bbox": [{"minx": 0.0}]},
        geometry=[SAMPLE_POLYGON],
        crs=GEOGRAPHIC_CRS,
    )
    path = _write_geoparquet(tmp_path, "bad-microsoft-buildings.parquet", bad_gdf)
    monkeypatch.setattr(io_module, "reference_s3_path", lambda region, layer: path)

    with pytest.raises(SchemaValidationError):
        load_reference_layer("maricopa-az", "microsoft-buildings", filesystem=LOCAL_FS)


def test_load_reference_layer_propagates_not_implemented_for_unregistered_layer(tmp_path, monkeypatch):
    """A layer read must still fail loudly (not silently skip validation) even when the read
    itself succeeds -- consistent with src.schemas.validate_layer's own documented behavior."""
    gdf = gpd.GeoDataFrame({"some_col": [1]}, geometry=[SAMPLE_POLYGON], crs=GEOGRAPHIC_CRS)
    path = _write_geoparquet(tmp_path, "overture-rail.parquet", gdf)
    monkeypatch.setattr(io_module, "reference_s3_path", lambda region, layer: path)

    with pytest.raises(NotImplementedError, match="no pandera schema registered"):
        load_reference_layer("maricopa-az", "overture-rail", filesystem=LOCAL_FS)


def test_load_reference_layer_wraps_missing_file(tmp_path, monkeypatch):
    missing_path = str(tmp_path / "does-not-exist.parquet")
    monkeypatch.setattr(io_module, "reference_s3_path", lambda region, layer: missing_path)
    with pytest.raises(FileNotFoundError, match="load_reference_layer"):
        load_reference_layer("maricopa-az", "microsoft-buildings", filesystem=LOCAL_FS)


def test_load_reference_layer_normalizes_epsg4326_label_to_crs84(tmp_path, monkeypatch):
    """Confirms the CRS-normalization step is genuinely wired in, not just present in the source
    -- a layer tagged with the EPSG:4326 label (which real bucket data might carry, per
    src/geometry.py's module docstring) must come out of load_reference_layer as exactly CRS84."""
    gdf = gpd.GeoDataFrame(
        {"height": [12.5], "confidence": [0.9], "bbox": [{"minx": 0.0}]},
        geometry=[SAMPLE_POLYGON],
        crs="EPSG:4326",
    )
    path = _write_geoparquet(tmp_path, "microsoft-buildings.parquet", gdf)
    monkeypatch.setattr(io_module, "reference_s3_path", lambda region, layer: path)

    result = load_reference_layer("maricopa-az", "microsoft-buildings", filesystem=LOCAL_FS)
    from src.geometry import is_crs84

    assert is_crs84(result.crs)


# -------------------------------------------------------------------------------------------
# load_strata_table / load_strata_national_table
# -------------------------------------------------------------------------------------------


def test_load_strata_table_full_pipeline(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame({"GEOID": ["04013010101"]}, geometry=[SAMPLE_POLYGON], crs=GEOGRAPHIC_CRS)
    path = _write_geoparquet(tmp_path, "maricopa-az-census-tracts.parquet", gdf)
    monkeypatch.setattr(io_module, "strata_s3_path", lambda region, table: path)

    result = load_strata_table("maricopa-az", "census-tracts", filesystem=LOCAL_FS)
    assert isinstance(result, gpd.GeoDataFrame)
    assert result["GEOID"].dtype == object


def test_load_strata_table_rejects_integer_geoid(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame({"GEOID": [4013010101]}, geometry=[SAMPLE_POLYGON], crs=GEOGRAPHIC_CRS)
    path = _write_geoparquet(tmp_path, "maricopa-az-census-tracts-bad.parquet", gdf)
    monkeypatch.setattr(io_module, "strata_s3_path", lambda region, table: path)

    with pytest.raises(ValueError, match="expected a string dtype"):
        load_strata_table("maricopa-az", "census-tracts", filesystem=LOCAL_FS)


def test_load_strata_table_propagates_missing_file():
    """The documented, already-confirmed real case: south-central-tx genuinely lacks
    census-tribal-subdivisions.parquet (docs/data_manifest.md Section 3) -- callers must see a
    real FileNotFoundError, not a silently-empty result, so they can apply the documented
    per-region file-existence check themselves."""
    with pytest.raises(FileNotFoundError):
        load_strata_table("south-central-tx", "definitely-does-not-exist-anywhere", filesystem=LOCAL_FS)


def test_load_strata_national_table_full_pipeline(tmp_path, monkeypatch):
    """Fixture uses one of the 5 national tables genuinely confirmed to carry geometry
    (docs/national_strata_schema_raw.csv) — national-census-tracts, not national-strata-tract-table.
    The previous version of this test built its fixture with a synthetic geometry column attached
    to a file named national-strata-tract-table.parquet, which passed but was never representative
    of the real file (confirmed, Stage 3 Step 1, to have zero geometry column) — see
    load_national_strata_attribute_table's docstring and the two tests immediately below, which
    replace that misleading coverage with an honest one."""
    gdf = gpd.GeoDataFrame({"GEOID": ["04013010101"]}, geometry=[SAMPLE_POLYGON], crs=GEOGRAPHIC_CRS)
    path = _write_geoparquet(tmp_path, "national-census-tracts.parquet", gdf)
    monkeypatch.setattr(io_module, "strata_national_s3_path", lambda table: path)

    result = load_strata_national_table("national-census-tracts", filesystem=LOCAL_FS)
    assert isinstance(result, gpd.GeoDataFrame)


def test_load_strata_national_table_fails_on_a_real_shaped_flat_table(tmp_path, monkeypatch):
    """The bug this whole fix responds to, reproduced directly: national-strata-tract-table (and
    20 of the other 25 national strata tables) have no geometry column at all in real life —
    load_strata_national_table cannot read them, and must fail loudly rather than silently return
    something wrong."""
    df = pd.DataFrame({"GEOID": ["04013010101"], "pop_total": [1000]})
    path = str(tmp_path / "national-strata-tract-table.parquet")
    df.to_parquet(path)
    monkeypatch.setattr(io_module, "strata_national_s3_path", lambda table: path)

    with pytest.raises(RuntimeError, match="Missing geo metadata"):
        load_strata_national_table("national-strata-tract-table", filesystem=LOCAL_FS)


def test_load_national_strata_attribute_table_reads_a_real_shaped_flat_table(tmp_path, monkeypatch):
    """The fix: the same realistic, geometry-less fixture that breaks load_strata_national_table
    above is read correctly by the new flat-table loader."""
    df = pd.DataFrame({"GEOID": ["04013010101"], "pop_total": [1000]})
    path = str(tmp_path / "national-strata-tract-table.parquet")
    df.to_parquet(path)
    monkeypatch.setattr(io_module, "strata_national_s3_path", lambda table: path)

    result = load_national_strata_attribute_table("national-strata-tract-table", filesystem=LOCAL_FS)
    assert isinstance(result, pd.DataFrame)
    assert not isinstance(result, gpd.GeoDataFrame)
    assert result["GEOID"].dtype == object
    assert result["pop_total"].iloc[0] == 1000


def test_load_national_strata_attribute_table_rejects_integer_geoid(tmp_path, monkeypatch):
    df = pd.DataFrame({"GEOID": [4013010101], "pop_total": [1000]})
    path = str(tmp_path / "national-strata-tract-table-bad.parquet")
    df.to_parquet(path)
    monkeypatch.setattr(io_module, "strata_national_s3_path", lambda table: path)

    with pytest.raises(ValueError, match="expected a string dtype"):
        load_national_strata_attribute_table("national-strata-tract-table", filesystem=LOCAL_FS)


def test_load_national_strata_attribute_table_tolerates_a_table_with_no_geoid_column(tmp_path, monkeypatch):
    """national-cdc-wonder-heat-mortality has no GEOID column at all (docs/data_manifest.md
    Section 4.11) — a legitimate, documented case, not a defect. _assert_geoid_is_string is a no-op
    when GEOID is absent; this must not raise."""
    df = pd.DataFrame({"series": ["Adults 65+"], "deaths": [120]})
    path = str(tmp_path / "national-cdc-wonder-heat-mortality.parquet")
    df.to_parquet(path)
    monkeypatch.setattr(io_module, "strata_national_s3_path", lambda table: path)

    result = load_national_strata_attribute_table("national-cdc-wonder-heat-mortality", filesystem=LOCAL_FS)
    assert list(result.columns) == ["series", "deaths"]


def test_load_national_strata_attribute_table_propagates_missing_file():
    with pytest.raises(FileNotFoundError):
        load_national_strata_attribute_table("definitely-does-not-exist-anywhere", filesystem=LOCAL_FS)


def test_load_national_strata_attribute_table_matches_the_documented_dtype_behavior_with_no_pandas_metadata(
    tmp_path, monkeypatch
):
    """The real bucket's files were not produced via pandas.DataFrame.to_parquet, so they carry no
    embedded pandas metadata — writing this fixture with plain pyarrow (not gdf/df.to_parquet, which
    IS how every other fixture in this file is built) reproduces that real shape. Locks in the
    dtype note added to this function's docstring: an int column with nulls comes back float64, a
    bool column with nulls comes back object-dtype, and a column with no nulls at all is unaffected."""
    arrow_table = pa.table(
        {
            "GEOID": pa.array(["04013010101", "04013010102"], type=pa.string()),
            "some_int_with_nulls": pa.array([1, None], type=pa.int32()),
            "some_bool_with_nulls": pa.array([True, None], type=pa.bool_()),
            "some_bool_no_nulls": pa.array([True, False], type=pa.bool_()),
        }
    )
    path = str(tmp_path / "national-strata-tract-table.parquet")
    pq.write_table(arrow_table, path)
    monkeypatch.setattr(io_module, "strata_national_s3_path", lambda table: path)

    result = load_national_strata_attribute_table("national-strata-tract-table", filesystem=LOCAL_FS)

    assert result["some_int_with_nulls"].dtype == np.float64
    assert result["some_int_with_nulls"].tolist()[0] == 1.0
    assert pd.isna(result["some_int_with_nulls"].tolist()[1])
    assert result["some_bool_with_nulls"].dtype == object
    assert result["some_bool_with_nulls"].tolist() == [True, None]
    assert result["some_bool_no_nulls"].dtype == bool
    assert result["GEOID"].dtype == object  # confirms _assert_geoid_is_string's check still applies


# -------------------------------------------------------------------------------------------
# load_sample_submission
# -------------------------------------------------------------------------------------------


def test_load_sample_submission_valid_csv(tmp_path):
    csv_path = tmp_path / "eastern-ok-sample-submission.csv"
    pd.DataFrame(
        {
            "GEOID": ["40001960100"],
            "transport_gap": [0.1],
            "building_gap": [0.2],
            "poi_gap": [0.3],
            "coverage_gap_score": [0.2],
        }
    ).to_csv(csv_path, index=False)

    result = load_sample_submission("eastern-ok", url=str(csv_path))
    assert set(EXPECTED_SAMPLE_SUBMISSION_COLUMNS).issubset(result.columns)
    assert result["GEOID"].dtype == object
    assert result["GEOID"].iloc[0] == "40001960100"


def test_load_sample_submission_geoid_column_entirely_absent_is_rejected(tmp_path):
    """Confirmed directly (not assumed) that pandas.read_csv's dtype={"GEOID": str} silently
    no-ops when the CSV has no GEOID column at all -- it does not raise on its own. This test
    pins that the EXPECTED_SAMPLE_SUBMISSION_COLUMNS presence check is what actually catches this
    case, since the dtype= argument alone would let it through silently."""
    csv_path = tmp_path / "no-geoid-sample-submission.csv"
    pd.DataFrame(
        {
            "transport_gap": [0.1],
            "building_gap": [0.2],
            "poi_gap": [0.3],
            "coverage_gap_score": [0.2],
        }
    ).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="missing expected column"):
        load_sample_submission("eastern-ok", url=str(csv_path))


def test_load_sample_submission_preserves_leading_zero_geoid(tmp_path):
    """The concrete regression this function's dtype= argument exists for: pandas.read_csv
    infers an all-digit GEOID column as int64 by default, silently dropping a leading zero.
    Maricopa's real GEOIDs start with "04" (Arizona's FIPS code)."""
    csv_path = tmp_path / "maricopa-az-sample-submission.csv"
    pd.DataFrame(
        {
            "GEOID": ["04013010101"],
            "transport_gap": [0.1],
            "building_gap": [0.2],
            "poi_gap": [0.3],
            "coverage_gap_score": [0.2],
        }
    ).to_csv(csv_path, index=False)

    result = load_sample_submission("maricopa-az", url=str(csv_path))
    assert result["GEOID"].iloc[0] == "04013010101"  # leading zero intact


def test_load_sample_submission_missing_expected_column_rejected(tmp_path):
    csv_path = tmp_path / "incomplete-sample-submission.csv"
    pd.DataFrame({"GEOID": ["40001960100"], "transport_gap": [0.1]}).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="missing expected column"):
        load_sample_submission("eastern-ok", url=str(csv_path))


def test_load_sample_submission_rejects_unknown_region():
    with pytest.raises(ValueError, match="Unknown region"):
        load_sample_submission("not-a-real-region")


def test_load_sample_submission_wraps_read_failure():
    with pytest.raises(RuntimeError, match="load_sample_submission"):
        load_sample_submission("eastern-ok", url="/tmp/definitely-does-not-exist-anywhere.csv")


def test_load_sample_submission_sends_a_custom_user_agent_for_a_real_http_url(monkeypatch):
    """Regression test for a real failure against the live bucket: pandas.read_csv's default
    plain-urllib User-Agent ("Python-urllib/x.y") was rejected by this bucket's HTTPS front end
    with a genuine HTTP 403 Forbidden, while the identical URL fetched with an ordinary
    browser-like User-Agent returned the CSV normally -- confirmed directly, not assumed, before
    this fix. This is a front-end/CDN policy against the default urllib client identity, not a
    broken URL or a real access restriction (load_reference_layer/load_strata_table are unaffected
    because they read via anonymous S3, never urllib). Captures the kwargs pandas.read_csv is
    actually called with, rather than hitting the network, since this project's test suite has no
    network access."""
    captured_kwargs = {}

    def fake_read_csv(url, **kwargs):
        captured_kwargs["url"] = url
        captured_kwargs.update(kwargs)
        return pd.DataFrame(
            {
                "GEOID": ["40001960100"],
                "transport_gap": [0.1],
                "building_gap": [0.2],
                "poi_gap": [0.3],
                "coverage_gap_score": [0.2],
            }
        )

    monkeypatch.setattr(io_module.pd, "read_csv", fake_read_csv)
    load_sample_submission("eastern-ok", url="https://example.invalid/eastern-ok-sample-submission.csv")

    assert "storage_options" in captured_kwargs, (
        "expected a real http(s) URL read to pass storage_options with a custom User-Agent; none "
        "was passed — the 403 Forbidden this fix addresses would resurface against the real bucket"
    )
    assert "User-Agent" in captured_kwargs["storage_options"]
    assert "python-urllib" not in captured_kwargs["storage_options"]["User-Agent"].lower()


def test_load_sample_submission_does_not_send_storage_options_for_a_local_path(monkeypatch, tmp_path):
    """The User-Agent fix must be scoped to real http(s) URLs only -- confirmed directly (not
    assumed) that pandas.read_csv raises `ValueError: storage_options passed with file object or
    non-fsspec file path` for a local path in this project's pinned pandas version. Every other
    test in this file already exercises a local-path read end-to-end and would fail loudly if this
    regressed; this test additionally pins the exact mechanism (storage_options must be absent
    from the kwargs pandas.read_csv receives for a local path), not just the visible symptom."""
    captured_kwargs = {}

    def fake_read_csv(url, **kwargs):
        captured_kwargs["url"] = url
        captured_kwargs.update(kwargs)
        return pd.DataFrame(
            {
                "GEOID": ["40001960100"],
                "transport_gap": [0.1],
                "building_gap": [0.2],
                "poi_gap": [0.3],
                "coverage_gap_score": [0.2],
            }
        )

    monkeypatch.setattr(io_module.pd, "read_csv", fake_read_csv)
    csv_path = tmp_path / "eastern-ok-sample-submission.csv"
    load_sample_submission("eastern-ok", url=str(csv_path))

    assert "storage_options" not in captured_kwargs
