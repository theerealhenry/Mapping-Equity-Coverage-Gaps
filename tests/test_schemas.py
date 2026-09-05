"""
tests/test_schemas.py — Stage 2, Step 3.

Tests src/schemas.py's pandera contracts against hand-built fixture rows modeled on the real,
directly-confirmed column shapes recorded in docs/data_manifest.md Section 4.3 (not against the
live bucket — that is Stage 2 Step 5's job, scripts/audit/audit_bucket.py, run against all four
regions for real). Each schema gets both a positive case (a realistic valid row passes) and at
least one negative case chosen to catch a real, documented risk — GEOID-as-integer
(docs/risk_register.md), a drifted/unexpected column on a strict schema, a malformed MTFCC code —
rather than only checking "does .validate() run without crashing."
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from src.config import (
    LAYER_CENSUS_CBP,
    LAYER_CENSUS_TIGER_ROADS,
    LAYER_HIFLD_EMS_STATIONS,
    LAYER_HIFLD_FIRE_STATIONS,
    LAYER_HIFLD_HOSPITALS,
    LAYER_HIFLD_SCHOOLS,
    LAYER_MICROSOFT_BUILDINGS,
    LAYER_OVERTURE_BUILDINGS,
    LAYER_OVERTURE_INFRASTRUCTURE,
    LAYER_OVERTURE_POIS,
    LAYER_OVERTURE_RAIL,
    LAYER_OVERTURE_ROADS,
)
from src.geometry import GEOGRAPHIC_CRS, normalize_geographic_crs
from src.schemas import (
    CENSUS_CBP_SCHEMA,
    CENSUS_TIGER_ROADS_SCHEMA,
    HIFLD_FACILITY_SCHEMA,
    LAYER_SCHEMAS,
    MICROSOFT_BUILDINGS_SCHEMA,
    OVERTURE_BUILDINGS_SCHEMA,
    OVERTURE_POIS_SCHEMA,
    OVERTURE_ROADS_SCHEMA,
    SchemaValidationError,
    validate_layer,
)

SAMPLE_POLYGON = Polygon([(-112.08, 33.44), (-112.07, 33.44), (-112.07, 33.45), (-112.08, 33.45)])
SAMPLE_LINE = LineString([(-112.08, 33.44), (-112.07, 33.44)])
SAMPLE_POINT = Point(-112.074, 33.4484)
VALID_GEOID = "04023970000"  # matches MARICOPA_NM_TRACT_GEOID's format, an AZ tract this time


# -------------------------------------------------------------------------------------------
# Registry / dispatch
# -------------------------------------------------------------------------------------------


def test_registry_covers_exactly_the_seven_blueprint_layer_types():
    """PROJECT_BLUEPRINT.md's Stage 2 deliverables name seven layer types (the four HIFLD files
    share one schema) — this pins the registry to exactly that set so a silently-added or
    silently-missing layer schema is caught here, not discovered later in io.py."""
    expected = {
        LAYER_OVERTURE_BUILDINGS,
        LAYER_OVERTURE_ROADS,
        LAYER_OVERTURE_POIS,
        LAYER_MICROSOFT_BUILDINGS,
        LAYER_CENSUS_TIGER_ROADS,
        LAYER_HIFLD_FIRE_STATIONS,
        LAYER_HIFLD_EMS_STATIONS,
        LAYER_HIFLD_SCHOOLS,
        LAYER_HIFLD_HOSPITALS,
        LAYER_CENSUS_CBP,
    }
    assert set(LAYER_SCHEMAS) == expected


def test_all_four_hifld_layers_share_the_identical_schema_object():
    """docs/data_manifest.md 4.3 confirms all four HIFLD files share one schema exactly — this
    checks the registry actually reuses one schema object rather than four independently-drifting
    copies of the same definition."""
    hifld_layers = [
        LAYER_HIFLD_FIRE_STATIONS,
        LAYER_HIFLD_EMS_STATIONS,
        LAYER_HIFLD_SCHOOLS,
        LAYER_HIFLD_HOSPITALS,
    ]
    schemas = {id(LAYER_SCHEMAS[layer]) for layer in hifld_layers}
    assert len(schemas) == 1


def test_validate_layer_dispatches_to_the_registered_schema():
    gdf = gpd.GeoDataFrame(
        {"subtype": ["building"], "class": ["residential"], "sources": [[]], "geometry": [SAMPLE_POLYGON]}
    )
    result = validate_layer(gdf, LAYER_OVERTURE_BUILDINGS)
    assert isinstance(result, gpd.GeoDataFrame)


@pytest.mark.parametrize(
    "unregistered_layer", [LAYER_OVERTURE_RAIL, LAYER_OVERTURE_INFRASTRUCTURE]
)
def test_validate_layer_raises_not_implemented_for_unregistered_layers(unregistered_layer):
    """A layer this project reads but hasn't scoped a schema for (out of Stage 2 Step 3's seven-
    type scope) must fail loudly, not silently skip validation."""
    gdf = gpd.GeoDataFrame({"geometry": [SAMPLE_POINT]})
    with pytest.raises(NotImplementedError, match="no pandera schema registered"):
        validate_layer(gdf, unregistered_layer)


def test_validate_layer_surfaces_multiple_independent_violations_in_one_pass():
    """The real payoff of validate_layer's lazy=True (added during Step 5's review pass, after
    the live-bucket audit run hit exactly this problem): pandera's default, non-lazy validate()
    stops at the FIRST failing check -- confirmed directly that two independently missing required
    columns only ever surface one at a time under the default, forcing a "fix one, re-run, discover
    the next" cycle. This dataframe has TWO independent violations at once for TIGER roads: RTTYP
    missing entirely, and an invalid (4-character) MTFCC length -- both must appear in the single
    raised error, not just one of them.

    The assertion is deliberately narrow: a naive `"MTFCC" in message` check would be a FALSE
    POSITIVE here, because pandera's own missing-column error text for RTTYP includes "Columns in
    dataframe: [..., 'MTFCC', ...]" -- the bare column name appears in that listing whether or not
    MTFCC's own content check ever actually ran. `str_length(5, 5)` is the specific check name
    pandera only emits when it has actually evaluated (and failed) MTFCC's length constraint --
    that is the real proof the second violation was reported, not just incidentally named."""
    gdf = gpd.GeoDataFrame(
        {
            "LINEARID": ["1104481629976"],
            "FULLNAME": ["Main St"],
            # RTTYP omitted entirely -- one independent violation
            "MTFCC": ["S110"],  # 4 characters, not 5 -- a second, independent violation
            "geometry": [SAMPLE_LINE],
        }
    )
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_layer(gdf, LAYER_CENSUS_TIGER_ROADS)
    message = str(exc_info.value)
    assert "RTTYP" in message and "column_in_dataframe" in message  # the missing-column violation
    assert "str_length(5, 5)" in message  # MTFCC's content check, actually evaluated and failed


def test_validate_layer_preserves_geodataframe_type():
    """A validated result must stay a GeoDataFrame, not get silently downgraded to a plain
    DataFrame — confirmed empirically before writing this schema, since downstream src.geometry
    functions require a real GeoDataFrame/GeoSeries."""
    gdf = gpd.GeoDataFrame(
        {"height": [10.0], "confidence": [0.8], "bbox": [{}], "geometry": [SAMPLE_POLYGON]}
    )
    result = validate_layer(gdf, LAYER_MICROSOFT_BUILDINGS)
    assert isinstance(result, gpd.GeoDataFrame)


# -------------------------------------------------------------------------------------------
# Integration with src.geometry -- the Step 4 handoff (io.py chains schemas.validate_layer then
# geometry.normalize_geographic_crs on every load). This is the single most important thing to
# get right in this module: if pandera validation ever silently stripped the CRS or downgraded
# the geometry column, io.py would appear to work but every downstream spatial operation would be
# wrong or crash confusingly two modules away from the actual cause.
# -------------------------------------------------------------------------------------------


def test_validated_geodataframe_keeps_its_crs_intact_for_src_geometry():
    gdf = gpd.GeoDataFrame(
        {"height": [12.5], "confidence": [0.9], "bbox": [{}]},
        geometry=[SAMPLE_POLYGON],
        crs=GEOGRAPHIC_CRS,
    )
    validated = validate_layer(gdf, LAYER_MICROSOFT_BUILDINGS)
    assert validated.crs is not None
    normalized = normalize_geographic_crs(validated)  # must not raise
    assert normalized.crs == GEOGRAPHIC_CRS


# -------------------------------------------------------------------------------------------
# Overture buildings (strict=False)
# -------------------------------------------------------------------------------------------


def test_overture_buildings_valid_row_passes():
    gdf = gpd.GeoDataFrame(
        {
            "subtype": ["building"],
            "class": [None],  # nullable class is expected -- many real buildings lack one
            "sources": [[{"dataset": "Microsoft ML Buildings"}]],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    OVERTURE_BUILDINGS_SCHEMA.validate(gdf)  # must not raise


def test_overture_buildings_null_subtype_permitted():
    """Regression test for the real Stage 2 Step 5 audit finding: the schema originally declared
    subtype non-nullable on the (wrong) assumption that every Overture buildings-theme feature
    carries one. A real run against all four regions failed with "non-nullable series 'subtype'
    contains null values" in every region -- directly disproving that assumption. Corrected to
    nullable=True; this test pins the corrected behavior down, mirroring
    test_overture_pois_null_categories_permitted's same pattern for the same class of finding."""
    gdf = gpd.GeoDataFrame(
        {"subtype": [None], "class": ["residential"], "sources": [[]], "geometry": [SAMPLE_POLYGON]}
    )
    OVERTURE_BUILDINGS_SCHEMA.validate(gdf)  # must not raise


def test_overture_buildings_missing_sources_column_entirely_is_rejected():
    """sources is nullable at the row level (a building can lack source metadata) but the column
    itself is still required=True by default -- missing entirely signals real schema drift."""
    gdf = gpd.GeoDataFrame({"subtype": ["building"], "class": ["residential"], "geometry": [SAMPLE_POLYGON]})
    with pytest.raises(SchemaValidationError):
        OVERTURE_BUILDINGS_SCHEMA.validate(gdf)


def test_overture_buildings_allows_unrelated_extra_columns():
    """strict=False is deliberate here -- Overture's real schema carries many more columns this
    project never reads; an unrelated extra column must NOT fail validation."""
    gdf = gpd.GeoDataFrame(
        {
            "subtype": ["building"],
            "class": ["residential"],
            "sources": [[]],
            "some_other_overture_column": ["irrelevant"],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    OVERTURE_BUILDINGS_SCHEMA.validate(gdf)  # must not raise


# -------------------------------------------------------------------------------------------
# Overture roads (strict=False)
# -------------------------------------------------------------------------------------------


def test_overture_roads_valid_row_passes_with_any_class_value():
    """class is NOT restricted to the four named-highway classes -- the raw layer carries every
    road class; the motorway/trunk/primary/secondary filter is Stage 6 gaps.py logic, not a
    property of this schema."""
    gdf = gpd.GeoDataFrame({"subtype": ["road"], "class": ["residential"], "geometry": [SAMPLE_LINE]})
    OVERTURE_ROADS_SCHEMA.validate(gdf)  # must not raise


def test_overture_roads_null_subtype_rejected():
    gdf = gpd.GeoDataFrame({"subtype": [None], "class": ["motorway"], "geometry": [SAMPLE_LINE]})
    with pytest.raises(SchemaValidationError):
        OVERTURE_ROADS_SCHEMA.validate(gdf)


# -------------------------------------------------------------------------------------------
# Overture POIs (strict=False)
# -------------------------------------------------------------------------------------------


def test_overture_pois_valid_row_passes():
    gdf = gpd.GeoDataFrame(
        {
            "categories": [{"primary": "fire_department", "alternate": []}],
            "confidence": [0.95],
            "geometry": [SAMPLE_POINT],
        }
    )
    OVERTURE_POIS_SCHEMA.validate(gdf)  # must not raise


def test_overture_pois_confidence_out_of_range_rejected():
    gdf = gpd.GeoDataFrame(
        {
            "categories": [{"primary": "school", "alternate": []}],
            "confidence": [1.5],  # out of [0, 1]
            "geometry": [SAMPLE_POINT],
        }
    )
    with pytest.raises(SchemaValidationError):
        OVERTURE_POIS_SCHEMA.validate(gdf)


def test_overture_pois_null_categories_permitted():
    """Deliberate, not an oversight: Overture's own POI schema allows a place with no known
    category, and this project has not directly confirmed a zero-null count for `categories`
    against the live bucket (that is Stage 2 Step 5's job). nullable=False here would crash this
    layer's ENTIRE load the first time one real row lacks a category -- a plausible failure mode,
    not a hypothetical one, so this schema stays permissive on this specific column."""
    gdf = gpd.GeoDataFrame(
        {"categories": [{"primary": "school"}, None], "confidence": [0.9, 0.5], "geometry": [SAMPLE_POINT, SAMPLE_POINT]}
    )
    OVERTURE_POIS_SCHEMA.validate(gdf)  # must not raise


def test_overture_pois_missing_categories_column_entirely_is_rejected():
    """Permissive about NULL values within the column, but the column itself is still required --
    a POI layer read with `categories` missing entirely is a real schema drift, not a data-quality
    nuance, and must still fail loudly."""
    gdf = gpd.GeoDataFrame({"confidence": [0.9], "geometry": [SAMPLE_POINT]})
    with pytest.raises(SchemaValidationError):
        OVERTURE_POIS_SCHEMA.validate(gdf)


# -------------------------------------------------------------------------------------------
# Microsoft buildings (strict=True, fully-documented schema)
# -------------------------------------------------------------------------------------------


def test_microsoft_buildings_valid_row_passes():
    gdf = gpd.GeoDataFrame(
        {"height": [12.5], "confidence": [0.9], "bbox": [{"minx": 0.0}], "geometry": [SAMPLE_POLYGON]}
    )
    MICROSOFT_BUILDINGS_SCHEMA.validate(gdf)  # must not raise


def test_microsoft_buildings_bbox_absent_is_now_tolerated():
    """Regression test for the real Stage 2 Step 5 audit finding: the real Microsoft buildings
    files across all four regions have NO bbox column at all -- the schema originally required it
    (docs/data_manifest.md 4.3's claim was wrong) and every single load failed with "column 'bbox'
    not in dataframe". bbox is now required=False; this must pass with bbox entirely absent."""
    gdf = gpd.GeoDataFrame({"height": [12.5], "confidence": [0.9], "geometry": [SAMPLE_POLYGON]})
    MICROSOFT_BUILDINGS_SCHEMA.validate(gdf)  # must not raise


def test_microsoft_buildings_rejects_undeclared_extra_column():
    """strict=True is deliberate here -- docs/data_manifest.md 4.3 confirms this is the COMPLETE
    schema ("nothing else"), so an unexpected column is itself worth failing loudly on."""
    gdf = gpd.GeoDataFrame(
        {
            "height": [12.5],
            "confidence": [0.9],
            "bbox": [{}],
            "geometry": [SAMPLE_POLYGON],
            "unexpected_extra_column": ["surprise"],
        }
    )
    with pytest.raises(SchemaValidationError):
        MICROSOFT_BUILDINGS_SCHEMA.validate(gdf)


def test_microsoft_buildings_confidence_out_of_range_rejected():
    gdf = gpd.GeoDataFrame(
        {"height": [12.5], "confidence": [-0.1], "bbox": [{}], "geometry": [SAMPLE_POLYGON]}
    )
    with pytest.raises(SchemaValidationError):
        MICROSOFT_BUILDINGS_SCHEMA.validate(gdf)


def test_microsoft_buildings_confidence_documented_placeholder_negative_one_is_tolerated():
    """Regression test for the real Stage 2 Step 5 audit finding: every region's Microsoft
    buildings file has thousands of rows with confidence == -1.0. Direct external research
    confirmed Microsoft's own GlobalMLBuildingFootprints README documents -1 as a deliberate
    placeholder for structures released before a given update -- not malformed data -- so this
    schema must accept it rather than reject every one of those real rows."""
    gdf = gpd.GeoDataFrame(
        {"height": [12.5], "confidence": [-1.0], "bbox": [{}], "geometry": [SAMPLE_POLYGON]}
    )
    MICROSOFT_BUILDINGS_SCHEMA.validate(gdf)  # must not raise


def test_microsoft_buildings_confidence_still_rejects_values_below_the_placeholder():
    """The -1.0 allowance must not accidentally widen into a full negative range -- a value like
    -0.5 is neither a real confidence score nor Microsoft's documented sentinel, so it must still
    be rejected."""
    gdf = gpd.GeoDataFrame(
        {"height": [12.5], "confidence": [-0.5], "bbox": [{}], "geometry": [SAMPLE_POLYGON]}
    )
    with pytest.raises(SchemaValidationError):
        MICROSOFT_BUILDINGS_SCHEMA.validate(gdf)


def test_overture_pois_confidence_placeholder_negative_one_still_rejected():
    """The Microsoft-specific -1.0 sentinel allowance must be scoped to Microsoft buildings only
    -- Overture POIs' confidence is a different field from a different source, never documented to
    use this convention, and must keep rejecting -1.0 like any other out-of-range value."""
    gdf = gpd.GeoDataFrame(
        {
            "categories": [{"primary": "school", "alternate": []}],
            "confidence": [-1.0],
            "geometry": [SAMPLE_POINT],
        }
    )
    with pytest.raises(SchemaValidationError):
        OVERTURE_POIS_SCHEMA.validate(gdf)


def test_microsoft_buildings_confidence_failure_message_is_bounded_by_n_failure_cases():
    """Regression test for the real Stage 2 Step 5 audit finding: with lazy=True, a single Check
    can list every failing value it finds, unbounded -- a real run showed 1285+ repeated "-1.0"
    (before the placeholder fix) or repeated true violations consuming an entire 8000-character
    truncation budget in scripts/audit/audit_bucket.py, hiding whether any other column also had a
    problem. n_failure_cases must keep the reported example list small regardless of how many rows
    actually fail."""
    n_rows = 500
    gdf = gpd.GeoDataFrame(
        {
            "height": [12.5] * n_rows,
            "confidence": [-0.5] * n_rows,  # genuinely invalid, not the tolerated -1.0 placeholder
            "bbox": [{}] * n_rows,
            "geometry": [SAMPLE_POLYGON] * n_rows,
        }
    )
    with pytest.raises(SchemaValidationError) as exc_info:
        MICROSOFT_BUILDINGS_SCHEMA.validate(gdf, lazy=True)
    message = str(exc_info.value)
    # 500 failing rows, all identical -0.5 values -- if failure-case examples were unbounded, this
    # message would repeat "-0.5" far more than n_failure_cases times.
    assert message.count("-0.5") <= 10


# -------------------------------------------------------------------------------------------
# TIGER roads (strict=True)
# -------------------------------------------------------------------------------------------


def test_tiger_roads_valid_row_passes():
    gdf = gpd.GeoDataFrame(
        {
            "LINEARID": ["1104481629976"],
            "FULLNAME": ["Main St"],
            "RTTYP": [None],
            "MTFCC": ["S1200"],
            "bbox": [{}],
            "geometry": [SAMPLE_LINE],
        }
    )
    CENSUS_TIGER_ROADS_SCHEMA.validate(gdf)  # must not raise


def test_tiger_roads_bbox_absent_is_now_tolerated():
    """Regression test for the real Stage 2 Step 5 audit finding -- see
    test_microsoft_buildings_bbox_absent_is_now_tolerated. Real TIGER roads columns confirmed as
    exactly LINEARID, FULLNAME, RTTYP, MTFCC, geometry -- no bbox."""
    gdf = gpd.GeoDataFrame(
        {
            "LINEARID": ["1104481629976"],
            "FULLNAME": ["Main St"],
            "RTTYP": [None],
            "MTFCC": ["S1200"],
            "geometry": [SAMPLE_LINE],
        }
    )
    CENSUS_TIGER_ROADS_SCHEMA.validate(gdf)  # must not raise


def test_tiger_roads_malformed_mtfcc_length_rejected():
    """MTFCC drives the S1100/S1200 transport_gap filter directly -- a malformed code here is
    exactly the kind of silent-drift bug this schema exists to catch before it reaches Stage 6."""
    gdf = gpd.GeoDataFrame(
        {
            "LINEARID": ["1104481629976"],
            "FULLNAME": ["Main St"],
            "RTTYP": [None],
            "MTFCC": ["S110"],  # 4 characters, not the standard 5
            "bbox": [{}],
            "geometry": [SAMPLE_LINE],
        }
    )
    with pytest.raises(SchemaValidationError):
        CENSUS_TIGER_ROADS_SCHEMA.validate(gdf)


def test_tiger_roads_null_mtfcc_rejected():
    gdf = gpd.GeoDataFrame(
        {
            "LINEARID": ["1104481629976"],
            "FULLNAME": ["Main St"],
            "RTTYP": [None],
            "MTFCC": [None],
            "bbox": [{}],
            "geometry": [SAMPLE_LINE],
        }
    )
    with pytest.raises(SchemaValidationError):
        CENSUS_TIGER_ROADS_SCHEMA.validate(gdf)


# -------------------------------------------------------------------------------------------
# HIFLD facilities (strict=True, shared schema)
# -------------------------------------------------------------------------------------------


def test_hifld_facility_valid_row_passes():
    gdf = gpd.GeoDataFrame(
        {
            "permanent_identifier": ["{ABC-123}"],
            "name": ["Station 1"],
            "ftype": [730],
            "fcode": [73001],
            "admintype": ["Municipal"],
            "address": ["123 Main St"],
            "city": ["Phoenix"],
            "state": ["AZ"],
            "zipcode": ["85001"],
            "gnis_id": [None],
            "bbox": [{}],
            "geometry": [SAMPLE_POINT],
        }
    )
    HIFLD_FACILITY_SCHEMA.validate(gdf)  # must not raise


def test_hifld_facility_bbox_absent_is_now_tolerated():
    """Regression test for the real Stage 2 Step 5 audit finding -- see
    test_microsoft_buildings_bbox_absent_is_now_tolerated. Confirmed identically across all four
    HIFLD facility files in all four regions: no bbox column."""
    gdf = gpd.GeoDataFrame(
        {
            "permanent_identifier": ["{ABC-123}"],
            "name": ["Station 1"],
            "ftype": [730],
            "fcode": [73001],
            "admintype": ["Municipal"],
            "address": ["123 Main St"],
            "city": ["Phoenix"],
            "state": ["AZ"],
            "zipcode": ["85001"],
            "gnis_id": [None],
            "geometry": [SAMPLE_POINT],
        }
    )
    HIFLD_FACILITY_SCHEMA.validate(gdf)  # must not raise


def test_hifld_facility_rejects_undeclared_extra_column():
    gdf = gpd.GeoDataFrame(
        {
            "permanent_identifier": ["{ABC-123}"],
            "name": ["Station 1"],
            "ftype": [730],
            "fcode": [73001],
            "admintype": ["Municipal"],
            "address": ["123 Main St"],
            "city": ["Phoenix"],
            "state": ["AZ"],
            "zipcode": ["85001"],
            "gnis_id": [None],
            "bbox": [{}],
            "geometry": [SAMPLE_POINT],
            "an_unexpected_column": ["surprise"],
        }
    )
    with pytest.raises(SchemaValidationError):
        HIFLD_FACILITY_SCHEMA.validate(gdf)


def test_hifld_facility_missing_required_column_rejected():
    gdf = gpd.GeoDataFrame(
        {
            "permanent_identifier": ["{ABC-123}"],
            "name": ["Station 1"],
            # ftype column omitted entirely
            "fcode": [73001],
            "admintype": ["Municipal"],
            "address": ["123 Main St"],
            "city": ["Phoenix"],
            "state": ["AZ"],
            "zipcode": ["85001"],
            "gnis_id": [None],
            "bbox": [{}],
            "geometry": [SAMPLE_POINT],
        }
    )
    with pytest.raises(SchemaValidationError):
        HIFLD_FACILITY_SCHEMA.validate(gdf)


# -------------------------------------------------------------------------------------------
# CBP (strict=True) — the GEOID-as-integer regression check
# -------------------------------------------------------------------------------------------


def test_cbp_valid_row_passes():
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": [VALID_GEOID],
            "STATEFP": ["04"],
            "COUNTYFP": ["023"],
            "TRACTCE": ["970000"],
            "cbp_estab": [10],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "bbox": [{}],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    CENSUS_CBP_SCHEMA.validate(gdf)  # must not raise


def test_cbp_bbox_absent_is_now_tolerated():
    """Regression test for the real Stage 2 Step 5 audit finding -- see
    test_microsoft_buildings_bbox_absent_is_now_tolerated. Real CBP columns confirmed as exactly
    GEOID, STATEFP, COUNTYFP, TRACTCE, cbp_estab, cbp_estab_res, cbp_estab_bus, geometry -- no
    bbox."""
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": [VALID_GEOID],
            "STATEFP": ["04"],
            "COUNTYFP": ["023"],
            "TRACTCE": ["970000"],
            "cbp_estab": [10],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    CENSUS_CBP_SCHEMA.validate(gdf)  # must not raise


def test_cbp_integer_geoid_is_rejected_not_silently_coerced():
    """The concrete regression this check exists for: Maricopa's real GEOID starts with "04"
    (Arizona's FIPS code) — read as int64, that leading zero silently vanishes and every
    downstream tract join breaks without any error. coerce=False on the GEOID column means this
    must raise, not quietly "fix" the value."""
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": [4023970000],  # int64 -- the leading zero is already gone
            "STATEFP": ["04"],
            "COUNTYFP": ["023"],
            "TRACTCE": ["970000"],
            "cbp_estab": [10],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "bbox": [{}],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    with pytest.raises(SchemaValidationError):
        CENSUS_CBP_SCHEMA.validate(gdf)


def test_cbp_integer_geoid_rejected_even_without_a_leading_zero_to_expose_it():
    """A stronger version of the check above. The Maricopa-leading-zero case is a real, relatable
    example, but it is not a complete proof that `coerce=False` (not `str_length`) is what does
    the rejecting: an int64 GEOID from a state whose FIPS code has no leading zero (Texas is
    "48", used here) stringifies to a valid-looking 11-digit string that WOULD pass the length
    and digit checks if `coerce` were mistakenly flipped to True — confirmed directly: with
    coerce=True this exact input silently passes. This test pins `coerce=False` as the thing
    actually doing the work, independent of which state's GEOID happens to be involved."""
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": [48029000100],  # int64, 11 digits, no leading zero lost -- would look valid
            "STATEFP": ["48"],
            "COUNTYFP": ["029"],
            "TRACTCE": ["000100"],
            "cbp_estab": [10],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "bbox": [{}],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    with pytest.raises(SchemaValidationError):
        CENSUS_CBP_SCHEMA.validate(gdf)


def test_cbp_integer_geoid_rejected_through_the_real_validate_layer_path():
    """Every GEOID-as-integer test above calls the schema object directly (CENSUS_CBP_SCHEMA.
    validate(...)), non-lazily. The REAL production path -- what src/io.py actually calls on every
    load -- is validate_layer(), which now validates with lazy=True (Step 5 review pass). This is
    a direct, end-to-end proof that this project's single most critical regression guard (a leading
    zero silently dropped from a state FIPS code, corrupting every downstream tract join) still
    holds through the actual path production code uses, not just the schema object in isolation.

    Uses a Texas-style GEOID (11 digits, no leading zero to lose), not Maricopa's -- confirmed
    directly (break-it-to-prove-it) that Maricopa's real int GEOID (4023970000, only 10 digits as
    an int) is rejected by the str_length(11, 11) check regardless of coerce, which would make
    this test pass even with coerce mistakenly flipped to True, masking exactly the regression it
    exists to catch. This mirrors test_cbp_integer_geoid_rejected_even_without_a_leading_zero_to_
    expose_it's same reasoning for the direct-schema version of this check."""
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": [48029000100],  # int64, 11 digits, no leading zero lost -- would look valid
            "STATEFP": ["48"],
            "COUNTYFP": ["029"],
            "TRACTCE": ["000100"],
            "cbp_estab": [10],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    with pytest.raises(SchemaValidationError):
        validate_layer(gdf, LAYER_CENSUS_CBP)


def test_cbp_wrong_length_geoid_rejected():
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": ["4023970000"],  # 10 characters, missing the leading zero as a STRING too
            "STATEFP": ["04"],
            "COUNTYFP": ["023"],
            "TRACTCE": ["970000"],
            "cbp_estab": [10],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "bbox": [{}],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    with pytest.raises(SchemaValidationError):
        CENSUS_CBP_SCHEMA.validate(gdf)


def test_cbp_negative_establishment_count_rejected():
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": [VALID_GEOID],
            "STATEFP": ["04"],
            "COUNTYFP": ["023"],
            "TRACTCE": ["970000"],
            "cbp_estab": [-1],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "bbox": [{}],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    with pytest.raises(SchemaValidationError):
        CENSUS_CBP_SCHEMA.validate(gdf)


def test_cbp_null_establishment_count_is_permitted():
    """cbp_estab's nullability is a deliberate, documented ASSUMPTION (not yet audit-confirmed —
    see src/schemas.py's module docstring), left permissive on purpose so this schema cannot
    itself break the pipeline over something Stage 2 Step 5 hasn't checked yet."""
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": [VALID_GEOID],
            "STATEFP": ["04"],
            "COUNTYFP": ["023"],
            "TRACTCE": ["970000"],
            "cbp_estab": [None],
            "cbp_estab_res": [2],
            "cbp_estab_bus": [8],
            "bbox": [{}],
            "geometry": [SAMPLE_POLYGON],
        }
    )
    CENSUS_CBP_SCHEMA.validate(gdf)  # must not raise
