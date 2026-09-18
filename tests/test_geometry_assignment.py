"""
tests/test_geometry_assignment.py — Stage 7 Step 2 golden-case fixture suite (tier 2 of 2).

Hand-fabricated micro-tracts exercising the exact cases where the spatial-assignment candidates
disagree or a real edge case bites: centroid-vs-intersection for a boundary-straddling building, a
boundary-crossing road (clipped length), a road that only touches a corner (the R-008 vertex-touch
regression, docs/data_manifest.md Section 4.22), and a facility point sitting exactly on a tract
boundary. This promotes src/geometry.py's own `__main__` self-check into a permanent pytest suite
Stage 7 tests and freezes against (per Step 0: these primitives are already built and unit-tested in
Stage 6 — this file does not re-author them), and adds the boundary-point case that self-check
didn't cover.

Toy lon/lat coordinates (not real geography) — fine for pure geometry-logic checks; EQUAL_AREA_CRS
still reprojects them validly. Two adjacent unit-ish squares sharing the boundary at x=10:
T1 = [0,10]x[0,10], T2 = [10,20]x[0,10].
"""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from src.geometry import (
    GEOGRAPHIC_CRS,
    assign_and_clip_lines,
    assign_buildings_by_centroid,
    assign_buildings_by_intersection,
    assign_points_to_tracts,
    geodesic_length_m,
)


@pytest.fixture
def tracts() -> gpd.GeoDataFrame:
    t1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    t2 = Polygon([(10, 0), (20, 0), (20, 10), (10, 10)])
    return gpd.GeoDataFrame({"GEOID": ["T1", "T2"]}, geometry=[t1, t2], crs=GEOGRAPHIC_CRS)


def test_facility_point_strictly_inside_assigns_to_one_tract(tracts):
    points = gpd.GeoDataFrame({"name": ["inside_t1"]}, geometry=[Point(5, 5)], crs=GEOGRAPHIC_CRS)
    result = assign_points_to_tracts(points, tracts)
    assert len(result) == 1
    assert result.iloc[0]["GEOID"] == "T1"


def test_facility_point_exactly_on_shared_boundary_is_dropped(tracts):
    # x=10 is the shared edge. predicate="within" requires the point's interior to lie in the
    # tract polygon's interior -- a point sitting exactly on the boundary "touches" but is not
    # "within" either polygon. Documented, asserted behavior (not assumed): this point is dropped,
    # contributing to no tract's facility count. If a future GeoPandas/GEOS version changes this,
    # this test fails loudly instead of the change slipping silently into a real submission.
    points = gpd.GeoDataFrame({"name": ["on_boundary"]}, geometry=[Point(10, 5)], crs=GEOGRAPHIC_CRS)
    result = assign_points_to_tracts(points, tracts)
    assert len(result) == 0, (
        f"expected the boundary-sitting point dropped by predicate='within', got {len(result)} "
        f"row(s) -- GeoPandas/GEOS boundary behavior changed; update this test's documented "
        f"expectation deliberately, don't just relax the assertion"
    )


def test_building_straddling_boundary_centroid_vs_intersection_disagree(tracts):
    # Footprint spans x=[7,11] (crosses the T1/T2 boundary at x=10); centroid at x=9 falls in T1
    # only. This is the exact case where the two candidate rules diverge.
    b_straddle = Polygon([(7, 2), (11, 2), (11, 4), (7, 4)])
    buildings = gpd.GeoDataFrame({"bid": ["b_straddle"]}, geometry=[b_straddle], crs=GEOGRAPHIC_CRS)

    centroid_result = assign_buildings_by_centroid(buildings, tracts)
    assert list(centroid_result["GEOID"]) == ["T1"], (
        "centroid rule: exactly one tract, the one containing the centroid (x=9 -> T1)"
    )

    intersection_result = assign_buildings_by_intersection(buildings, tracts)
    assert set(intersection_result["GEOID"]) == {"T1", "T2"}, (
        "intersection rule: every tract the footprint touches at all -> both T1 and T2 -- this "
        "is the exact disagreement Stage 7's Tier A calibration exists to resolve"
    )


def test_road_crossing_boundary_clips_to_matching_symmetric_lengths(tracts):
    # A straight horizontal segment from (0,5) to (20,5) crosses the shared boundary at x=10 and
    # is clipped into T1's portion (x=[0,10]) and T2's portion (x=[10,20]). Both halves are
    # symmetric about x=10 at the same constant y=5, so their geodesic lengths must match exactly
    # -- hand-verified from the geometry, not just "both are positive".
    full_line = LineString([(0, 5), (20, 5)])
    lines = gpd.GeoDataFrame({"lid": ["crossing"]}, geometry=[full_line], crs=GEOGRAPHIC_CRS)

    result = assign_and_clip_lines(lines, tracts)
    assert set(result["GEOID"]) == {"T1", "T2"}

    lengths = geodesic_length_m(result)
    t1_len = lengths[result["GEOID"] == "T1"].iloc[0]
    t2_len = lengths[result["GEOID"] == "T2"].iloc[0]
    assert t1_len > 0 and t2_len > 0
    assert t1_len == pytest.approx(t2_len, rel=1e-9)


def test_road_touching_boundary_at_single_vertex_produces_no_row(tracts):
    # Repeats the R-008 regression (docs/data_manifest.md Section 4.22): a line that only touches
    # a tract's corner intersects as a Point, which keep_geom_type=True must drop -- real clipped
    # length 0, not a spurious "this road is in this tract" row.
    vertex_touch_line = LineString([(10, 10), (15, 15)])
    lines = gpd.GeoDataFrame(
        {"lid": ["vertex_touch"]}, geometry=[vertex_touch_line], crs=GEOGRAPHIC_CRS
    )
    result = assign_and_clip_lines(lines, tracts)
    assert len(result) == 0, "vertex-touch line must yield zero clipped rows (Point dropped)"
