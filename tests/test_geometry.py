"""
tests/test_geometry.py — Stage 2, Step 2.

Per PROJECT_BLUEPRINT.md's Gate A exit criteria, `src/geometry.py`'s CRS-handling half must have
its own passing unit test before any other geometry code is written against it. This file is that
test — and it is deliberately more than a shape check: it reproduces the actual CRS84-vs-EPSG:4326
axis-order bug (`POINT(inf inf)`, docs/risk_register.md R-004) with real coordinates and proves
`src.geometry`'s functions avoid it, rather than only asserting that no exception was raised.

Two tiers:
  - Pure pyproj/geopandas tests (no network) — always run, everywhere, including CI.
  - A DuckDB `spatial`-extension integration test — skipped automatically if the extension cannot
    be downloaded (e.g. a network-restricted sandbox), but runs for real on a normal developer
    machine and proves the DuckDB-specific half of the fix end-to-end, not just the SQL string.
"""

from __future__ import annotations

import math

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from src.geometry import (
    EQUAL_AREA_CRS,
    GEOGRAPHIC_CRS,
    assert_crs84,
    assert_no_forbidden_crs_literal,
    configure_duckdb_spatial,
    duckdb_transform_sql,
    geodesic_area_m2,
    geodesic_length_m,
    is_crs84,
    normalize_geographic_crs,
    to_equal_area,
)


class _FakeDuckDBConnection:
    """A network-free stand-in for a duckdb connection, just enough to verify
    configure_duckdb_spatial's contract (exact statements issued, in order; returns the same
    connection for chaining) without needing the real spatial extension downloaded."""

    def __init__(self) -> None:
        self.executed: list[str] = []

    def execute(self, sql: str) -> "_FakeDuckDBConnection":
        self.executed.append(sql)
        return self

# Phoenix, AZ (lon, lat) — inside the Maricopa study region. Ground-truth projected coordinates
# below were computed independently with pyproj.Transformer(always_xy=True), matching how
# geopandas' own .to_crs() operates internally — see the module docstring in src/geometry.py.
PHOENIX_LONLAT = (-112.0740, 33.4484)
PHOENIX_5070_XY = (-1477242.845010892, 1278582.822713835)
COORD_TOLERANCE_M = 1.0  # meters — generous given PHOENIX_5070_XY's own precision


# -------------------------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------------------------


@pytest.fixture
def point_crs84() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(*PHOENIX_LONLAT)], crs=GEOGRAPHIC_CRS
    )


@pytest.fixture
def point_epsg4326_label() -> gpd.GeoDataFrame:
    """Same point, same coordinate order, but tagged with the EPSG:4326 string instead of
    OGC:CRS84 — the ambiguous-but-common case `normalize_geographic_crs` exists to absorb."""
    return gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(*PHOENIX_LONLAT)], crs="EPSG:4326"
    )


@pytest.fixture
def point_no_crs() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"id": [1]}, geometry=[Point(*PHOENIX_LONLAT)], crs=None)


@pytest.fixture
def point_wrong_crs() -> gpd.GeoDataFrame:
    """Tagged with the equal-area CRS itself — a genuinely different, non-CRS84 case that must
    never be silently accepted by normalize_geographic_crs."""
    return gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(-1_477_242.8, 1_278_582.8)], crs=EQUAL_AREA_CRS
    )


@pytest.fixture
def small_square_crs84() -> gpd.GeoDataFrame:
    """A ~0.01deg x 0.01deg square near Phoenix — small enough that its equal-area-CRS area is a
    useful, checkable order-of-magnitude sanity value (roughly 1 sq km at this latitude), not an
    exact-shape assertion (Albers is not conformal, per EQUAL_AREA_CRS's own docstring)."""
    lon, lat = PHOENIX_LONLAT
    d = 0.01
    square = Polygon(
        [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d), (lon, lat)]
    )
    return gpd.GeoDataFrame({"id": [1]}, geometry=[square], crs=GEOGRAPHIC_CRS)


@pytest.fixture
def short_line_crs84() -> gpd.GeoDataFrame:
    """A short line near Phoenix, ~0.01deg long, for a length-sanity check."""
    lon, lat = PHOENIX_LONLAT
    line = LineString([(lon, lat), (lon + 0.01, lat)])
    return gpd.GeoDataFrame({"id": [1]}, geometry=[line], crs=GEOGRAPHIC_CRS)


@pytest.fixture
def plain_dataframe() -> pd.DataFrame:
    """Not a GeoDataFrame at all — the most common real-world misuse (a geometry-bearing
    GeoDataFrame that got demoted to a plain DataFrame by an upstream pandas operation)."""
    return pd.DataFrame({"id": [1], "geometry": [Point(*PHOENIX_LONLAT)]})


# -------------------------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------------------------


def test_geographic_crs_is_crs84_not_epsg4326():
    assert GEOGRAPHIC_CRS == "OGC:CRS84"
    assert GEOGRAPHIC_CRS.upper() != "EPSG:4326"


def test_equal_area_crs_is_conus_albers():
    assert EQUAL_AREA_CRS == "EPSG:5070"


# -------------------------------------------------------------------------------------------
# is_crs84 / assert_crs84
# -------------------------------------------------------------------------------------------


def test_is_crs84_true_for_crs84(point_crs84):
    assert is_crs84(point_crs84.crs) is True


def test_is_crs84_false_for_epsg4326_label():
    """The core distinction this whole module exists to enforce: EPSG:4326 is NOT treated as
    equal to OGC:CRS84 by strict CRS identity, even though geopandas coordinates behave the same
    way under both labels. is_crs84 is the strict check; normalize_geographic_crs is the tolerant
    entry point — they are deliberately different, see src/geometry.py's module docstring."""
    assert is_crs84("EPSG:4326") is False


def test_is_crs84_false_for_none_and_other_crs():
    assert is_crs84(None) is False
    assert is_crs84(EQUAL_AREA_CRS) is False


def test_assert_crs84_passes_silently_for_crs84(point_crs84):
    assert_crs84(point_crs84)  # must not raise


def test_assert_crs84_raises_for_epsg4326_label(point_epsg4326_label):
    with pytest.raises(ValueError, match="OGC:CRS84"):
        assert_crs84(point_epsg4326_label)


def test_assert_crs84_raises_for_plain_dataframe(plain_dataframe):
    with pytest.raises(TypeError, match="GeoDataFrame or GeoSeries"):
        assert_crs84(plain_dataframe)


def test_assert_crs84_error_includes_context(point_epsg4326_label):
    with pytest.raises(ValueError, match="my-test-layer"):
        assert_crs84(point_epsg4326_label, context="my-test-layer")


# -------------------------------------------------------------------------------------------
# normalize_geographic_crs
# -------------------------------------------------------------------------------------------


def test_normalize_raises_on_unset_crs(point_no_crs):
    with pytest.raises(ValueError, match="no CRS set"):
        normalize_geographic_crs(point_no_crs)


def test_normalize_raises_on_unrelated_crs(point_wrong_crs):
    with pytest.raises(ValueError, match="is not"):
        normalize_geographic_crs(point_wrong_crs)


def test_normalize_raises_on_plain_dataframe(plain_dataframe):
    with pytest.raises(TypeError, match="GeoDataFrame or GeoSeries"):
        normalize_geographic_crs(plain_dataframe)


def test_normalize_is_noop_for_already_crs84(point_crs84):
    result = normalize_geographic_crs(point_crs84)
    assert is_crs84(result.crs)
    assert result.geometry.iloc[0].equals(point_crs84.geometry.iloc[0])


def test_normalize_retags_epsg4326_label_to_crs84(point_epsg4326_label):
    result = normalize_geographic_crs(point_epsg4326_label)
    assert is_crs84(result.crs)
    # Coordinates must be numerically unchanged — only the CRS label changes, since geopandas
    # coordinate order does not depend on which of the two labels was attached.
    original_point = point_epsg4326_label.geometry.iloc[0]
    result_point = result.geometry.iloc[0]
    assert result_point.x == pytest.approx(original_point.x)
    assert result_point.y == pytest.approx(original_point.y)


def test_normalize_works_on_geoseries(point_crs84):
    series = point_crs84.geometry
    result = normalize_geographic_crs(series)
    assert is_crs84(result.crs)


# -------------------------------------------------------------------------------------------
# to_equal_area / geodesic_area_m2 / geodesic_length_m
# -------------------------------------------------------------------------------------------


def test_to_equal_area_requires_crs84(point_epsg4326_label):
    """to_equal_area is strict, not tolerant — it will not silently normalize an EPSG:4326-labeled
    input for you; callers must go through normalize_geographic_crs explicitly first."""
    with pytest.raises(ValueError, match="OGC:CRS84"):
        to_equal_area(point_epsg4326_label)


def test_to_equal_area_matches_independent_pyproj_ground_truth(point_crs84):
    """The real regression test: transforms a known point and checks the result against
    coordinates computed independently (outside src/geometry.py) with
    pyproj.Transformer(always_xy=True) — not just "no exception raised"."""
    result = to_equal_area(point_crs84)
    assert result.crs.to_authority() == ("EPSG", "5070")
    x, y = result.geometry.iloc[0].x, result.geometry.iloc[0].y
    assert math.isfinite(x) and math.isfinite(y)
    expected_x, expected_y = PHOENIX_5070_XY
    assert x == pytest.approx(expected_x, abs=COORD_TOLERANCE_M)
    assert y == pytest.approx(expected_y, abs=COORD_TOLERANCE_M)


def test_to_equal_area_does_not_reproduce_the_axis_order_bug(point_crs84):
    """Directly proves the failure mode this module exists to prevent (docs/risk_register.md
    R-004) does NOT occur here: feeding (lon, lat) into a transformer that expects EPSG:4326's
    official (lat, lon) order produces POINT(inf inf) — confirmed independently below. This test
    asserts src.geometry's real output is nothing like that."""
    from pyproj import Transformer

    buggy_transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=False)
    lon, lat = PHOENIX_LONLAT
    buggy_x, buggy_y = buggy_transformer.transform(lon, lat)
    assert not math.isfinite(buggy_x)  # sanity: confirms the bug is real and reproducible

    result = to_equal_area(point_crs84)
    x, y = result.geometry.iloc[0].x, result.geometry.iloc[0].y
    assert math.isfinite(x) and math.isfinite(y)
    assert x != pytest.approx(buggy_x) if math.isfinite(buggy_x) else True


def test_geodesic_area_m2_is_positive_and_plausible(small_square_crs84):
    """A ~0.01deg x 0.01deg square near Phoenix's latitude should be on the order of ~1 sq km —
    order-of-magnitude sanity, not an exact-shape assertion (Albers is not conformal)."""
    area = geodesic_area_m2(small_square_crs84).iloc[0]
    assert math.isfinite(area)
    assert area > 0
    assert 500_000 < area < 2_000_000  # ~0.5-2 sq km


def test_geodesic_length_m_is_positive_and_plausible(short_line_crs84):
    """A ~0.01deg east-west line near Phoenix's latitude should be roughly ~0.9 km (1 degree of
    longitude at ~33.4deg N is about 93 km)."""
    length = geodesic_length_m(short_line_crs84).iloc[0]
    assert math.isfinite(length)
    assert 700 < length < 1_100


def test_geodesic_area_m2_raises_on_plain_dataframe(plain_dataframe):
    with pytest.raises(TypeError, match="GeoDataFrame or GeoSeries"):
        geodesic_area_m2(plain_dataframe)


def test_geodesic_area_m2_rejects_lines(short_line_crs84):
    """The regression this check exists for: shapely's own .area on a LineString silently
    returns 0.0 instead of erroring — geodesic_area_m2 must not pass that silence along."""
    with pytest.raises(ValueError, match="unexpected"):
        geodesic_area_m2(short_line_crs84)


def test_geodesic_area_m2_rejects_points(point_crs84):
    with pytest.raises(ValueError, match="unexpected"):
        geodesic_area_m2(point_crs84)


def test_geodesic_length_m_rejects_polygons(small_square_crs84):
    """The regression this check exists for: shapely's own .length on a Polygon silently returns
    its PERIMETER — a plausible-looking wrong number — instead of erroring."""
    with pytest.raises(ValueError, match="unexpected"):
        geodesic_length_m(small_square_crs84)


def test_geometry_type_check_ignores_null_geometries():
    """A null geometry alongside a valid one must not trip the type check by itself — missing-
    geometry handling is a separate, deliberate concern (see geodesic_area_m2's docstring), not a
    type error."""
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[Polygon([(-112.08, 33.44), (-112.07, 33.44), (-112.07, 33.45)]), None],
        crs=GEOGRAPHIC_CRS,
    )
    result = geodesic_area_m2(gdf)  # must not raise
    assert result.iloc[0] > 0
    assert math.isnan(result.iloc[1])


def test_empty_geodataframe_does_not_crash(point_crs84):
    empty = point_crs84.iloc[0:0]
    assert is_crs84(normalize_geographic_crs(empty).crs)
    result = geodesic_area_m2(empty)
    assert len(result) == 0


# -------------------------------------------------------------------------------------------
# SQL-side helpers
# -------------------------------------------------------------------------------------------


def test_assert_no_forbidden_crs_literal_passes_clean_sql():
    assert_no_forbidden_crs_literal("ST_Transform(geometry, 'OGC:CRS84', 'EPSG:5070')")  # no raise


@pytest.mark.parametrize(
    "bad_sql",
    [
        "ST_Transform(geometry, 'EPSG:4326', 'EPSG:5070')",
        "ST_Transform(geometry, 'epsg:4326', 'EPSG:5070')",
        "SELECT ST_SetSRID(geometry, 4326)",
    ],
)
def test_assert_no_forbidden_crs_literal_catches_forbidden_tokens(bad_sql):
    with pytest.raises(ValueError, match="forbidden CRS token"):
        assert_no_forbidden_crs_literal(bad_sql)


def test_duckdb_transform_sql_default_args():
    sql = duckdb_transform_sql("geometry")
    assert sql == "ST_Transform(geometry, 'OGC:CRS84', 'EPSG:5070', always_xy := true)"


def test_duckdb_transform_sql_always_includes_always_xy_true():
    sql = duckdb_transform_sql("some_col", to_crs="EPSG:26912")
    assert "always_xy := true" in sql


def test_duckdb_transform_sql_custom_expression_and_target():
    sql = duckdb_transform_sql("t.geom", to_crs="EPSG:26912", from_crs="OGC:CRS84")
    assert sql.startswith("ST_Transform(t.geom, 'OGC:CRS84', 'EPSG:26912'")


def test_duckdb_transform_sql_rejects_forbidden_from_crs():
    """Proves the self-check inside duckdb_transform_sql is load-bearing, not decorative: passing
    the forbidden literal explicitly must still be caught, not just documented against."""
    with pytest.raises(ValueError, match="forbidden CRS token"):
        duckdb_transform_sql("geometry", from_crs="EPSG:4326")


def test_duckdb_transform_sql_rejects_quote_in_crs_argument():
    """Defensive guard: a stray quote in from_crs/to_crs would otherwise silently break the
    generated SQL string rather than raising a clear error."""
    with pytest.raises(ValueError, match="single-quote"):
        duckdb_transform_sql("geometry", to_crs="EPSG:5070'; DROP TABLE x; --")


def test_assert_crs84_error_message_is_compact_not_a_full_crs_dump(point_epsg4326_label):
    """pyproj.CRS's own repr() is a multi-line, several-hundred-character block (name, axis info,
    area of use, datum...) — regression check that error messages stay short and scannable
    instead of dumping that whole block into a log line."""
    with pytest.raises(ValueError) as excinfo:
        assert_crs84(point_epsg4326_label)
    message = str(excinfo.value)
    assert len(message) < 200
    assert "EPSG:4326" in message
    assert "Axis Info" not in message  # a fragment unique to pyproj.CRS's verbose repr


# -------------------------------------------------------------------------------------------
# configure_duckdb_spatial contract (network-free, via a fake connection)
# -------------------------------------------------------------------------------------------


def test_configure_duckdb_spatial_issues_install_then_load_and_returns_same_connection():
    fake_con = _FakeDuckDBConnection()
    result = configure_duckdb_spatial(fake_con)
    assert result is fake_con
    assert fake_con.executed == ["INSTALL spatial", "LOAD spatial"]


# -------------------------------------------------------------------------------------------
# DuckDB spatial extension integration test — real end-to-end proof, network permitting
# -------------------------------------------------------------------------------------------


def test_duckdb_spatial_transform_matches_ground_truth():
    """Loads the real DuckDB spatial extension and runs the actual ST_Transform this project's
    SQL will use, checking it against the same independently-computed ground truth used above —
    proof the fix works end-to-end in DuckDB itself, not just that our SQL string looks right.

    Skipped (not failed) if the extension cannot be downloaded — e.g. a network-restricted CI
    runner or sandbox. Run this locally / on a normal machine to get the real proof."""
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    try:
        configure_duckdb_spatial(con)
    except Exception as exc:  # noqa: BLE001 — any failure here means "can't verify, don't fail"
        pytest.skip(f"DuckDB spatial extension unavailable in this environment: {exc}")

    lon, lat = PHOENIX_LONLAT
    sql = f"SELECT ST_X(t), ST_Y(t) FROM (SELECT {duckdb_transform_sql(f'ST_Point({lon}, {lat})')} AS t)"
    x, y = con.execute(sql).fetchone()

    assert math.isfinite(x) and math.isfinite(y)
    expected_x, expected_y = PHOENIX_5070_XY
    assert x == pytest.approx(expected_x, abs=1.0)
    assert y == pytest.approx(expected_y, abs=1.0)


def test_duckdb_spatial_reproduces_bug_without_always_xy():
    """The negative control: proves that omitting always_xy (i.e. writing the transform the
    'naive' way this module exists to prevent) really does break on DuckDB's spatial extension,
    the same way it does in raw pyproj — confirming this isn't a theoretical concern specific to
    pyproj but a real DuckDB behaviour this project must guard against."""
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    try:
        configure_duckdb_spatial(con)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"DuckDB spatial extension unavailable in this environment: {exc}")

    lon, lat = PHOENIX_LONLAT
    # Deliberately the buggy form: literal EPSG:4326, no always_xy.
    sql = (
        f"SELECT ST_X(t), ST_Y(t) FROM "
        f"(SELECT ST_Transform(ST_Point({lon}, {lat}), 'EPSG:4326', 'EPSG:5070') AS t)"
    )
    x, y = con.execute(sql).fetchone()
    # This is the actual bug this module exists to prevent: it does not raise, it returns
    # nonsense (inf/nan or a wildly wrong coordinate) instead of erroring.
    assert not math.isfinite(x) or abs(x - PHOENIX_5070_XY[0]) > 1_000
