"""
src/geometry.py — Stage 2, Step 2 (CRS utility) and Stage 6 (spatial-assignment logic).

This module is the SOLE place in the project that:

  1. Declares and validates the project's canonical geographic CRS (`OGC:CRS84` — WGS84 with
     explicit longitude/latitude axis order).
  2. Declares the project's canonical projected, equal-area CRS (`EPSG:5070` — NAD83 / Conus
     Albers Equal Area), used for every area and length computation.
  3. Provides the only sanctioned way to move geometry between the two — in geopandas code (via
     `.to_crs()`, which pyproj/geopandas already handle safely — see below) and in hand-written
     DuckDB SQL (via `duckdb_transform_sql()`, which hard-codes `always_xy := true`) — so the
     axis-order pitfall documented below cannot be silently reintroduced by a script written later.

Per PROJECT_BLUEPRINT.md, this file is also the designated sole home for the project's
spatial-assignment logic (point-in-polygon for facility counts, centroid-in-polygon vs.
geometric-intersection for buildings, line-clip-and-sum for roads) — but that logic is Stage 6
work and is added to this same file then, not now. Stage 2 Step 2 delivers only the CRS-handling
half (this file as it stands, plus tests/test_geometry.py): per the blueprint's Gate A exit
criteria, this half must have its own passing unit test before any other geometry code is written
against it.

--- The pitfall this module exists to prevent --------------------------------------------------

DuckDB's `spatial` extension resolves `ST_Transform`'s CRS string arguments through the PROJ/EPSG
authority database, which honours each authority's OFFICIAL axis order. For `EPSG:4326`, that
official order is (latitude, longitude) — the opposite of the (longitude, latitude) order every
other tool in this stack uses by convention (geopandas, shapely, GeoParquet — and the raw bucket
data itself, which follows the GeoParquet spec's implied CRS, `OGC:CRS84`, when no CRS is embedded
in a file's metadata). Pass the literal string `"EPSG:4326"` into a DuckDB `ST_Transform` call
without `always_xy := true`, and every coordinate pair is silently swapped: the result is not an
error, it can come back as `POINT(inf inf)` / NaN after a subsequent projected calculation, or as a
geometry that "looks" plausible but is mirrored across the equator/prime meridian. This is
`docs/risk_register.md`'s `R-004` (Probability: High, Impact: Critical) precisely because it fails
silently rather than raising.

geopandas' `.to_crs()` is NOT vulnerable to this specific footgun — it builds a `pyproj.Transformer`
directly from `pyproj.CRS` objects with `always_xy=True` hard-coded internally, so shapely's fixed
(x, y) coordinate order is preserved regardless of which authority label was attached. The danger is
specifically in hand-written SQL strings (DuckDB, or any other spatial SQL engine) where a bare
`"EPSG:4326"` literal is common, easy to write by habit, and wrong here. This module still
centralizes the geopandas-side handling (`normalize_geographic_crs`, `assert_crs84`,
`to_equal_area`) alongside the SQL-side handling (`duckdb_transform_sql`,
`assert_no_forbidden_crs_literal`), so there is exactly one place in the codebase that knows about
CRS strings at all, and every other module imports from here rather than writing a CRS literal
itself.

The fix used throughout this project: never write the literal string `"EPSG:4326"` anywhere in the
codebase, in a script, or in a notebook. Use `GEOGRAPHIC_CRS` (`"OGC:CRS84"`, this module) for every
geographic-CRS reference instead, and route every transform through the functions below.

Run this module's tests with: pytest tests/test_geometry.py -v
"""

from __future__ import annotations

from typing import Union

import geopandas as gpd
import pandas as pd
import pyproj

GeoFrameOrSeries = Union[gpd.GeoDataFrame, gpd.GeoSeries]

# -------------------------------------------------------------------------------------------
# Canonical CRS constants — the only place these strings should ever be written literally.
# -------------------------------------------------------------------------------------------

GEOGRAPHIC_CRS = "OGC:CRS84"
"""Canonical geographic CRS for every geometry in this project once it has passed through
`normalize_geographic_crs`: WGS84, explicit longitude/latitude axis order. Every layer in the
challenge bucket is natively in this CRS (GeoParquet's implied default when no CRS is embedded)."""

EQUAL_AREA_CRS = "EPSG:5070"
"""Canonical projected CRS for area and length computation: NAD83 / Conus Albers Equal Area — the
standard equal-area projection for CONUS-scale analysis (used by the Census Bureau and USGS for
national work), appropriate here because all four study regions fall entirely within the
contiguous United States.

Equal-area by construction, so every AREA figure this project computes from it (building
footprints, tract areas, the `building_gap` denominator) is exact. It is NOT conformal — it does
not exactly preserve length/shape — so every LENGTH figure (road-segment sums feeding
`transport_gap`) carries a small, known distortion. At the metropolitan/county extent of this
project's regions that distortion is on the order of a few tenths of a percent, well under any
threshold that would change a tract's relative coverage-gap ranking. Using a single CONUS-wide
equal-area CRS for both area AND length is a deliberate, documented trade-off against the
alternative (a different, more locally-accurate CRS such as a UTM zone per region), chosen for
simplicity and cross-region comparability of the underlying projection — not an oversight. See
`docs/risk_register.md` R-004 and `docs/scoring_assumptions.md`."""

_FORBIDDEN_CRS_TOKENS = ("epsg:4326", "4326")
"""Lower-cased substrings that must never appear as a literal CRS argument anywhere in this
project's SQL or config — see the module docstring. Checked against raw strings, not parsed CRS
objects, because the whole point is to catch the literal token before it ever reaches DuckDB/PROJ.
Note this also flags a bare "4326" (e.g. inside an `SRID=4326` literal) — deliberately broad, since
any code path constructing that literal is the exact pattern this module exists to prevent."""

_CRS84_AUTHORITY = ("OGC", "CRS84")
_WGS84_LONLAT_COMPATIBLE_AUTHORITIES = {("OGC", "CRS84"), ("EPSG", "4326")}
"""Authority codes this project treats as coordinate-order-compatible with CRS84 when NORMALIZING
data just read off disk/the bucket. geopandas/shapely never reorder coordinates based on axis
order — a GeoDataFrame tagged "EPSG:4326" by geopandas holds exactly the same (lon, lat) shapely
coordinates as one tagged "OGC:CRS84". So a freshly-read layer carrying either label is safe to
re-tag as CRS84 outright (see `normalize_geographic_crs`). This tolerance is intentionally narrow:
it exists only to absorb the ambiguity at the point data enters the project, not to make the two
strings interchangeable everywhere — `assert_crs84` downstream still requires the EXACT CRS84
label, and no SQL-building function in this module accepts anything but `GEOGRAPHIC_CRS`."""


# -------------------------------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------------------------------


def _crs_authority(crs: object) -> tuple[str, str] | None:
    """Resolves any CRS-like input (string, pyproj.CRS, or None) to its (authority, code) tuple,
    or None if it cannot be resolved / is None. Never raises — callers decide what a None means."""
    if crs is None:
        return None
    try:
        resolved = pyproj.CRS.from_user_input(crs)
    except pyproj.exceptions.CRSError:
        return None
    return resolved.to_authority()


def _require_geo(obj: GeoFrameOrSeries, fn_name: str) -> None:
    """Fails fast, with a clear message, if `obj` is not a GeoDataFrame/GeoSeries — the most
    common misuse of every function below is accidentally passing a plain (non-geo) DataFrame
    whose geometry column lost its GeoDataFrame-ness upstream (e.g. after a plain pandas merge)."""
    if not isinstance(obj, (gpd.GeoDataFrame, gpd.GeoSeries)):
        raise TypeError(
            f"{fn_name}() requires a GeoDataFrame or GeoSeries, got {type(obj).__name__}. "
            "This usually means a plain pandas operation (merge, concat, groupby.apply) dropped "
            "the GeoDataFrame's geometry-awareness upstream — re-wrap with "
            "gpd.GeoDataFrame(..., geometry=..., crs=...) before calling into src.geometry."
        )


def _compact_crs_repr(crs: object) -> str:
    """A short `AUTHORITY:CODE` string for error messages. pyproj.CRS's own __repr__ is a
    multi-line block (name, axis info, area of use, datum, ellipsoid — several hundred characters)
    that makes a raised error swallow a log line instead of reading as one; this keeps error
    messages scannable. Falls back to str(crs) for a CRS pyproj can't resolve to an authority code
    (e.g. a custom/WKT-only CRS), and to "None" for an unset CRS."""
    if crs is None:
        return "None"
    authority = _crs_authority(crs)
    if authority is not None:
        return f"{authority[0]}:{authority[1]}"
    return str(crs)


def _assert_geom_types(obj: GeoFrameOrSeries, allowed_types: frozenset[str], fn_name: str) -> None:
    """Raises ValueError if any non-null geometry in `obj` has a `.geom_type` outside
    `allowed_types`. Null geometries are ignored here — missing-geometry handling is a caller/
    Stage 6 decision (see `geodesic_area_m2`'s and `geodesic_length_m`'s docstrings), not a type
    error.

    This exists because shapely silently returns a NUMBER, not an error, for the wrong geometry
    type: `.area` on a LineString is 0.0, and `.length` on a Polygon is its PERIMETER — a real,
    plausible-looking value, not an obvious mistake. Without this check, passing a roads layer to
    `geodesic_area_m2` (or a buildings layer to `geodesic_length_m`) by a wiring mistake would
    silently produce a wrong-but-plausible number instead of failing — exactly the kind of silent
    failure this module exists to prevent for CRS handling, extended here to geometry types too."""
    _require_geo(obj, fn_name)
    geom_series = obj.geometry if isinstance(obj, gpd.GeoDataFrame) else obj
    present_types = set(geom_series.dropna().geom_type.unique())
    unexpected = present_types - allowed_types
    if unexpected:
        raise ValueError(
            f"{fn_name}: expected geometry type(s) {sorted(allowed_types)}, found unexpected "
            f"type(s) {sorted(unexpected)} in the input. This usually means the wrong layer was "
            "passed in (e.g. a roads layer into an area function, or a buildings layer into a "
            "length function) — shapely computes a plausible-looking number for the wrong "
            "geometry type instead of raising, which is exactly why this check exists."
        )


# -------------------------------------------------------------------------------------------
# CRS validation and normalization (geopandas side)
# -------------------------------------------------------------------------------------------


def is_crs84(crs: object) -> bool:
    """True only if `crs` resolves to exactly OGC:CRS84 — not EPSG:4326, not None, not anything
    else. Strict by design; use `normalize_geographic_crs` first if you have raw source data that
    may be tagged EPSG:4326 or left unset."""
    return _crs_authority(crs) == _CRS84_AUTHORITY


def assert_crs84(obj: GeoFrameOrSeries, *, context: str = "") -> None:
    """Raises ValueError unless `obj.crs` is exactly OGC:CRS84. This is the guardrail every
    CRS84-consuming function below calls first — it forces every caller to have gone through
    `normalize_geographic_crs` already, rather than each function silently assuming a CRS that may
    not actually be there.

    `context` is an optional short label (e.g. a layer name) included in the error message to make
    a failure easy to trace back to its source when this is called deep inside a pipeline."""
    _require_geo(obj, "assert_crs84")
    if not is_crs84(obj.crs):
        where = f" ({context})" if context else ""
        raise ValueError(
            f"assert_crs84{where}: expected CRS exactly {GEOGRAPHIC_CRS!r}, got "
            f"{_compact_crs_repr(obj.crs)!r}. Call src.geometry.normalize_geographic_crs() on "
            "this object first."
        )


def normalize_geographic_crs(obj: GeoFrameOrSeries) -> GeoFrameOrSeries:
    """The mandatory first step for every layer this project reads, before any other function in
    this module (or downstream code) touches its geometry. Called by every loader in `src/io.py`.

    Behaviour:
      - `obj.crs is None`: raises ValueError. GeoParquet's spec-implied default when no CRS is
        embedded is OGC:CRS84, and geopandas/pyarrow readers are expected to apply that default
        automatically — an unset CRS reaching this function means something upstream (a manual
        geometry construction, a non-GeoParquet source) skipped that step, and this project would
        rather fail loudly here than silently assume a CRS for geometry with none declared.
      - `obj.crs` resolves to OGC:CRS84 or EPSG:4326: re-tagged as exactly CRS84
        (`set_crs(GEOGRAPHIC_CRS, allow_override=True)`). Safe because geopandas/shapely coordinate
        order never depends on which of these two labels was attached (see
        `_WGS84_LONLAT_COMPATIBLE_AUTHORITIES` above) — this collapses the ambiguity to a single
        unambiguous label the rest of the codebase can rely on.
      - `obj.crs` resolves to anything else (a UTM zone, Web Mercator, EQUAL_AREA_CRS itself,
        etc.): raises ValueError. This project never silently reprojects an unexpected source CRS —
        every layer in the challenge bucket is documented as CRS84-native, so anything else reaching
        this function signals a real problem worth investigating, not a routine conversion.

    Returns a new object (does not mutate `obj` in place), matching geopandas' own convention.
    """
    _require_geo(obj, "normalize_geographic_crs")

    if obj.crs is None:
        raise ValueError(
            "normalize_geographic_crs: input has no CRS set. Every layer in the challenge bucket "
            f"is CRS84-native ({GEOGRAPHIC_CRS}) — an unset CRS means the read path did not apply "
            "GeoParquet's implied default and should be fixed at the source, not papered over here."
        )

    authority = _crs_authority(obj.crs)
    if authority not in _WGS84_LONLAT_COMPATIBLE_AUTHORITIES:
        raise ValueError(
            f"normalize_geographic_crs: input CRS {_compact_crs_repr(obj.crs)!r} is not "
            f"{GEOGRAPHIC_CRS} or EPSG:4326-equivalent. Every source layer in this project is "
            "documented as CRS84-native; an unexpected CRS here means the source data changed or "
            "was mis-read, and should be investigated rather than blindly reprojected."
        )

    if authority == _CRS84_AUTHORITY:
        return obj
    return obj.set_crs(GEOGRAPHIC_CRS, allow_override=True)


# -------------------------------------------------------------------------------------------
# Equal-area projection and area/length utilities
# -------------------------------------------------------------------------------------------


def to_equal_area(obj: GeoFrameOrSeries) -> GeoFrameOrSeries:
    """Reprojects a CRS84 GeoDataFrame/GeoSeries to EQUAL_AREA_CRS. Requires the input to already
    be exactly CRS84 (call `normalize_geographic_crs` first if unsure) — this function does not
    guess or silently normalize, so a caller always knows exactly which CRS it started from.

    Uses geopandas' `.to_crs()`, which is safe against the axis-order pitfall by construction (see
    the module docstring) — no manual pyproj Transformer is needed here."""
    assert_crs84(obj, context="to_equal_area input")
    return obj.to_crs(EQUAL_AREA_CRS)


_AREA_GEOM_TYPES = frozenset({"Polygon", "MultiPolygon"})
_LENGTH_GEOM_TYPES = frozenset({"LineString", "MultiLineString", "LinearRing"})


def geodesic_area_m2(obj: GeoFrameOrSeries) -> pd.Series:
    """Area in square meters, computed via EQUAL_AREA_CRS. Input must be CRS84 (see
    `to_equal_area`). Exact, not approximate — EQUAL_AREA_CRS is equal-area by construction.

    Every non-null geometry must be a Polygon/MultiPolygon — anything else (a roads layer passed
    in by mistake, for instance) raises ValueError rather than silently returning 0.0, which is
    what shapely's own `.area` does for a LineString or Point (see `_assert_geom_types`).

    A null (missing) geometry produces NaN in the result, not an error or a 0 — missing-geometry
    handling (drop vs. impute vs. propagate) is a Stage 6/`gaps.py` decision made against the
    actual data, not one this module should make silently on its behalf."""
    _assert_geom_types(obj, _AREA_GEOM_TYPES, "geodesic_area_m2")
    return to_equal_area(obj).geometry.area


def geodesic_length_m(obj: GeoFrameOrSeries) -> pd.Series:
    """Length in meters, computed via EQUAL_AREA_CRS. Input must be CRS84 (see `to_equal_area`).
    Approximate, not exact — EQUAL_AREA_CRS is not conformal; see EQUAL_AREA_CRS's docstring for
    the documented, deliberate size of this trade-off at this project's scale.

    Every non-null geometry must be a LineString/MultiLineString/LinearRing — anything else (a
    buildings layer passed in by mistake, for instance) raises ValueError rather than silently
    returning shapely's `.length`, which for a Polygon is its PERIMETER: a plausible-looking wrong
    number, not an obvious mistake (see `_assert_geom_types`).

    A null (missing) geometry produces NaN in the result, not an error or a 0 — same rationale as
    `geodesic_area_m2` above."""
    _assert_geom_types(obj, _LENGTH_GEOM_TYPES, "geodesic_length_m")
    return to_equal_area(obj).geometry.length


# -------------------------------------------------------------------------------------------
# DuckDB SQL helpers — the sanctioned way to write a CRS transform in hand-written SQL
# -------------------------------------------------------------------------------------------


def assert_no_forbidden_crs_literal(sql: str, *, context: str = "") -> None:
    """Raises ValueError if `sql` contains a forbidden CRS token (see `_FORBIDDEN_CRS_TOKENS`) —
    a lightweight, dependency-free lint any script or notebook can run on a hand-built SQL string
    before executing it against DuckDB. Case-insensitive. `duckdb_transform_sql`'s own output is
    checked against this function in tests/test_geometry.py as a self-consistency guarantee."""
    lowered = sql.lower()
    for token in _FORBIDDEN_CRS_TOKENS:
        if token in lowered:
            where = f" ({context})" if context else ""
            raise ValueError(
                f"assert_no_forbidden_crs_literal{where}: forbidden CRS token {token!r} found in "
                f"SQL string. Use src.geometry.GEOGRAPHIC_CRS ({GEOGRAPHIC_CRS!r}) instead of a "
                "literal EPSG:4326/4326 reference — see src/geometry.py's module docstring for why."
            )


def duckdb_transform_sql(
    geom_expr: str,
    *,
    to_crs: str = EQUAL_AREA_CRS,
    from_crs: str = GEOGRAPHIC_CRS,
) -> str:
    """Builds a DuckDB `ST_Transform(...)` SQL fragment for `geom_expr` (a column name or any
    other SQL expression evaluating to a GEOMETRY), from `from_crs` to `to_crs`. This is the ONLY
    sanctioned way to write a CRS transform in hand-written SQL anywhere in this project: it always
    passes `always_xy := true` and always defaults to `GEOGRAPHIC_CRS` (`OGC:CRS84`) as the source,
    never the literal `EPSG:4326` — see the module docstring for exactly why that distinction
    matters for DuckDB's `spatial` extension specifically.

    Example: duckdb_transform_sql("geometry") ->
        "ST_Transform(geometry, 'OGC:CRS84', 'EPSG:5070', always_xy := true)"

    `geom_expr` is inserted verbatim as a SQL expression (a column name, or any other expression
    evaluating to GEOMETRY) — it is meant to be trusted, developer-written SQL, the same as every
    other string this function's caller writes directly into a query, not sanitized user input.
    `from_crs`/`to_crs` ARE defended against a stray quote character breaking the generated SQL
    (accidental misuse, not an untrusted-input threat model), since unlike `geom_expr` they are
    always short, literal CRS strings with no legitimate reason to contain one.
    """
    if "'" in from_crs or "'" in to_crs:
        raise ValueError(
            f"duckdb_transform_sql: from_crs={from_crs!r} / to_crs={to_crs!r} must not contain a "
            "single-quote character — it would break the generated SQL string."
        )
    sql = f"ST_Transform({geom_expr}, '{from_crs}', '{to_crs}', always_xy := true)"
    assert_no_forbidden_crs_literal(sql, context="duckdb_transform_sql output")
    return sql


def configure_duckdb_spatial(con: "object") -> "object":
    """Installs and loads the DuckDB `spatial` extension on `con` (idempotent — safe to call
    repeatedly / from multiple scripts on the same or different connections). The single place
    this happens in the project, so every script's spatial extension setup is identical. Does not
    load `httpfs` — that is a data-access concern owned by the scripts/modules that open a bucket
    connection, not by this CRS-and-geometry module.

    Returns `con` for convenient chaining (`con = configure_duckdb_spatial(duckdb.connect())`)."""
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    return con


# -------------------------------------------------------------------------------------------
# Stage 6 — spatial-assignment logic (point-in-polygon, centroid/intersection, line-clip-and-sum)
# -------------------------------------------------------------------------------------------
#
# Not yet implemented. Per PROJECT_BLUEPRINT.md this module is the designated sole home for that
# logic, added in Stage 6 once feature-table assembly begins. Intentionally left out of Stage 2
# Step 2's deliverable so this file's CRS-handling half can be tested and frozen on its own first.
