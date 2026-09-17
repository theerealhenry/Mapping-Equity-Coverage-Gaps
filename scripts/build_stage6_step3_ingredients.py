"""
scripts/build_stage6_step3_ingredients.py — Stage 6, Step 3: core per-component raw ingredients
and candidate capped-ratio gap values, computed per region.

Produces data/processed/<region>-step3-ingredients.parquet: raw counts/lengths (Overture vs.
reference source, per candidate spatial-assignment variant where more than one exists — buildings
only) plus their candidate capped-ratio gap values and `*_defined` booleans, per
claude/stage6-feature-engineering-guideline.md Step 3. This is NOT a final feature table (Step 6
assembles and schema-validates that) and does NOT compute coverage_gap_score (Stage 7's gaps.py
does that) — purely the raw ingredients Stage 7's calibration will select from.

Run with (Phase 1 — eastern-ok only, per incremental-implementation discipline; do not run other
regions until eastern-ok's verification numbers are confirmed):
    python scripts/build_stage6_step3_ingredients.py eastern-ok
"""

from __future__ import annotations

import os
import sys

import duckdb
import numpy as np
import pandas as pd

from src.config import (
    CBP_ESTAB_COLUMN_DEFAULT,
    LAYER_CENSUS_CBP,
    LAYER_CENSUS_TIGER_ROADS,
    LAYER_HIFLD_EMS_STATIONS,
    LAYER_HIFLD_FIRE_STATIONS,
    LAYER_HIFLD_SCHOOLS,
    LAYER_MICROSOFT_BUILDINGS,
    LAYER_OVERTURE_BUILDINGS,
    LAYER_OVERTURE_POIS,
    LAYER_OVERTURE_ROADS,
    OVERTURE_NAMED_HIGHWAY_CLASSES,
    POI_FACILITY_CATEGORY_MAP,
    SCORED_TRACT_COUNTS,
    TIGER_NAMED_HIGHWAY_MTFCC,
    reference_url,
    strata_url,
)
from src.geometry import (
    assign_and_clip_lines,
    configure_duckdb_spatial,
    geodesic_length_m,
)
from src.io import load_reference_layer, load_strata_table

TRACT_ID_COL = "GEOID"

_HIFLD_LAYERS = {
    "fire": LAYER_HIFLD_FIRE_STATIONS,
    "ems": LAYER_HIFLD_EMS_STATIONS,
    "schools": LAYER_HIFLD_SCHOOLS,
}


def _capped_ratio(overture: pd.Series, reference: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Step 0 Ambiguity 2's formula, applied per candidate raw-count/length pair:
    `1 - min(1, overture / reference)`, clipped to [0, 1], with a `*_defined` boolean
    (`reference > 0`). An undefined component stays NaN here, never silently zeroed (R-005) —
    Stage 7 excludes undefined components from the composite mean, it does not treat them as a
    zero gap."""
    reference = reference.astype(float)
    overture = overture.astype(float)
    defined = reference.notna() & (reference > 0)
    ratio = pd.Series(np.nan, index=overture.index, dtype=float)
    safe_ratio = (overture[defined] / reference[defined]).clip(upper=1)
    ratio.loc[defined] = (1 - safe_ratio).clip(lower=0)
    return ratio, defined


def _register_tracts(con: duckdb.DuckDBPyConnection, region: str) -> None:
    """Registers the region's tract polygons as DuckDB table `tracts` (GEOID + geometry only) —
    the small side of every spatial join below, indexed for the join via an RTREE on its own
    geometry column (1,192 tracts in eastern-ok — cheap to index; the large side, e.g. 2.5M
    Overture buildings, is read straight off the remote parquet, never materialized wholesale into
    Python/GeoPandas memory — this is exactly the DuckDB-not-in-memory-GeoPandas discipline Section
    4.21's memory/freeze incident requires for anything at building/POI scale)."""
    tracts_url = strata_url(region, "census-tracts")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE tracts AS
        SELECT "GEOID", CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{tracts_url}')
        """
    )
    con.execute('CREATE INDEX IF NOT EXISTS tracts_geom_idx ON tracts USING RTREE (geometry)')


def build_transport(region: str, tracts_gdf) -> pd.DataFrame:
    """Transport raw lengths (Overture named-highway vs. TIGER named-highway), per tract —
    reuses `assign_and_clip_lines` (Stage 5's own already-validated clipped-length logic,
    promoted into src/geometry.py at Step 2), not re-derived here. In-memory GeoPandas is safe for
    this one: road-segment counts (tens of thousands per region) are two-plus orders of magnitude
    smaller than the building layers Section 4.21's incident involved.

    Filters each source to its documented named-highway subset BEFORE clipping — TIGER to
    `MTFCC in TIGER_NAMED_HIGHWAY_MTFCC` (S1100/S1200), Overture to
    `class in OVERTURE_NAMED_HIGHWAY_CLASSES` (motorway/trunk/primary/secondary) — per R-006's
    documented filter and Section 4.6/4.22's own methodology. Found and fixed via Stage 6 Step 9's
    cross-check against Section 4.22's published transport-only-undefined counts (869/218/253/
    1,704): the original version of this function clipped and summed EVERY road segment in both
    sources, unfiltered, which made almost every tract show a nonzero, real-road-network-scale
    length instead of the much sparser named-highway-only network — undercounting undefined
    tracts by nearly 100% and inflating every length figure by roughly an order of magnitude."""
    overture_roads = load_reference_layer(region, LAYER_OVERTURE_ROADS)
    tiger_roads = load_reference_layer(region, LAYER_CENSUS_TIGER_ROADS)
    overture_roads = overture_roads[overture_roads["class"].isin(OVERTURE_NAMED_HIGHWAY_CLASSES)]
    tiger_roads = tiger_roads[tiger_roads["MTFCC"].isin(TIGER_NAMED_HIGHWAY_MTFCC)]

    overture_clipped = assign_and_clip_lines(overture_roads, tracts_gdf)
    tiger_clipped = assign_and_clip_lines(tiger_roads, tracts_gdf)

    overture_len = geodesic_length_m(overture_clipped).groupby(overture_clipped[TRACT_ID_COL]).sum()
    tiger_len = geodesic_length_m(tiger_clipped).groupby(tiger_clipped[TRACT_ID_COL]).sum()

    return pd.DataFrame(
        {
            "overture_transport_length_m": overture_len,
            "tiger_transport_length_m": tiger_len,
        }
    )


def build_buildings(con: duckdb.DuckDBPyConnection, region: str) -> pd.DataFrame:
    """Building raw counts (Overture, Microsoft), per tract, under BOTH candidate
    spatial-assignment variants (centroid, intersection) — four raw columns, per Step 0 Ambiguity
    2 (both built now, deliberately; Stage 7's calibration selects between them on real RMSE
    evidence). DuckDB spatial throughout — never in-memory GeoPandas sjoin at this row scale."""
    results: dict[str, pd.Series] = {}
    for label, layer in (
        ("overture", LAYER_OVERTURE_BUILDINGS),
        ("microsoft", LAYER_MICROSOFT_BUILDINGS),
    ):
        url = reference_url(region, layer)
        con.execute(
            f"CREATE OR REPLACE TABLE _bld AS "
            f"SELECT CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{url}')"
        )

        centroid_counts = (
            con.execute(
                """
                SELECT t."GEOID" AS "GEOID", COUNT(*) AS n
                FROM _bld b JOIN tracts t ON ST_Within(ST_Centroid(b.geometry), t.geometry)
                GROUP BY t."GEOID"
                """
            )
            .fetchdf()
            .set_index("GEOID")["n"]
        )
        intersection_counts = (
            con.execute(
                """
                SELECT t."GEOID" AS "GEOID", COUNT(*) AS n
                FROM _bld b JOIN tracts t ON ST_Intersects(b.geometry, t.geometry)
                GROUP BY t."GEOID"
                """
            )
            .fetchdf()
            .set_index("GEOID")["n"]
        )
        results[f"{label}_building_count_centroid"] = centroid_counts
        results[f"{label}_building_count_intersection"] = intersection_counts

    return pd.DataFrame(results)


def build_poi(con: duckdb.DuckDBPyConnection, region: str) -> pd.DataFrame:
    """POI raw counts, per tract: facilities half (Overture vs. HIFLD, per sub-type — fire, EMS,
    schools; hospitals explicitly excluded here via `WHERE category NOT IN (...)`, Step 0
    Ambiguity 3's resolution / R-004) and establishments half (all Overture POIs, unfiltered, vs.
    `cbp_estab_bus` — a broad places-vs-business-count comparison, not subject to the hospital
    exclusion, which applies only to the facilities term).

    Every category string matched EXACT against `categories.primary` — never substring/fuzzy —
    per `docs/data_manifest.md` Section 4.4's real near-miss evidence (`security_systems` contains
    the literal substring "ems"). One spatial join assigns every Overture POI to its tract; every
    downstream count (per facility sub-type, and the unfiltered establishments total) is then a
    cheap group-by over that single join's result, not a repeated spatial join per sub-type."""
    pois_url = reference_url(region, LAYER_OVERTURE_POIS)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE _poi_tract AS
        SELECT t."GEOID" AS "GEOID", p.category AS category
        FROM (SELECT categories.primary AS category, CAST(geometry AS GEOMETRY) AS geometry
              FROM read_parquet('{pois_url}')) p
        JOIN tracts t ON ST_Within(p.geometry, t.geometry)
        """
    )

    results: dict[str, pd.Series] = {}

    hospital_excluded_note = "hospital"  # documented, deliberate — R-004 / Ambiguity 3
    for subtype, categories in POI_FACILITY_CATEGORY_MAP.items():
        assert hospital_excluded_note not in categories, (
            f"config.py's POI_FACILITY_CATEGORY_MAP[{subtype!r}] unexpectedly includes "
            "'hospital' — R-004's exclusion must hold; this assert exists so a future edit to "
            "config.py can't silently reintroduce the ~12x overcount."
        )
        cat_list = ", ".join(f"'{c}'" for c in categories)
        overture_counts = (
            con.execute(
                f"""
                SELECT "GEOID", COUNT(*) AS n FROM _poi_tract
                WHERE category IN ({cat_list})
                GROUP BY "GEOID"
                """
            )
            .fetchdf()
            .set_index("GEOID")["n"]
        )
        results[f"overture_poi_count_{subtype}"] = overture_counts

        hifld_url = reference_url(region, _HIFLD_LAYERS[subtype])
        con.execute(
            f"CREATE OR REPLACE TABLE _hifld AS "
            f"SELECT CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{hifld_url}')"
        )
        hifld_counts = (
            con.execute(
                """
                SELECT t."GEOID" AS "GEOID", COUNT(*) AS n
                FROM _hifld h JOIN tracts t ON ST_Within(h.geometry, t.geometry)
                GROUP BY t."GEOID"
                """
            )
            .fetchdf()
            .set_index("GEOID")["n"]
        )
        results[f"hifld_count_{subtype}"] = hifld_counts

    # Establishments half: ALL Overture POIs (unfiltered — no hospital exclusion here, that only
    # applies to the facilities term above), vs. CBP business-address establishment count.
    results["overture_places_count"] = (
        con.execute('SELECT "GEOID", COUNT(*) AS n FROM _poi_tract GROUP BY "GEOID"')
        .fetchdf()
        .set_index("GEOID")["n"]
    )

    # census-cbp ships under reference/, not strata/ (config.py groups LAYER_CENSUS_CBP with the
    # other reference-layer constants; Section 4.3 confirms the real bucket path) — schema-
    # validated too, via load_reference_layer -> validate_layer, unlike load_strata_table.
    cbp = load_reference_layer(region, LAYER_CENSUS_CBP)
    results["cbp_estab_bus"] = cbp.set_index(TRACT_ID_COL)[CBP_ESTAB_COLUMN_DEFAULT]

    return pd.DataFrame(results)


def build_candidate_gaps(raw: pd.DataFrame) -> pd.DataFrame:
    """Computes the candidate capped-ratio + `*_defined` pair for every raw ingredient built
    above, per candidate variant where more than one exists (buildings: two variants each)."""
    out = {}

    ratio, defined = _capped_ratio(raw["overture_transport_length_m"], raw["tiger_transport_length_m"])
    out["transport_gap"] = ratio
    out["transport_defined"] = defined

    for variant in ("centroid", "intersection"):
        ratio, defined = _capped_ratio(
            raw[f"overture_building_count_{variant}"], raw[f"microsoft_building_count_{variant}"]
        )
        out[f"building_gap_{variant}"] = ratio
        out[f"building_gap_{variant}_defined"] = defined

    for subtype in POI_FACILITY_CATEGORY_MAP:
        ratio, defined = _capped_ratio(raw[f"overture_poi_count_{subtype}"], raw[f"hifld_count_{subtype}"])
        out[f"poi_gap_{subtype}"] = ratio
        out[f"poi_gap_{subtype}_defined"] = defined

    ratio, defined = _capped_ratio(raw["overture_places_count"], raw["cbp_estab_bus"])
    out["poi_gap_establishments"] = ratio
    out["poi_gap_establishments_defined"] = defined

    return pd.DataFrame(out)


def main(region: str) -> None:
    print(f"[{region}] connecting + registering tracts...", flush=True)
    con = duckdb.connect()
    configure_duckdb_spatial(con)
    con.execute("INSTALL httpfs; LOAD httpfs;")
    _register_tracts(con, region)

    tracts_gdf = load_strata_table(region, "census-tracts")[[TRACT_ID_COL, "geometry"]]
    full_index = pd.Index(tracts_gdf[TRACT_ID_COL].unique(), name=TRACT_ID_COL)

    print(f"[{region}] transport (GeoPandas, in-memory)...", flush=True)
    transport = build_transport(region, tracts_gdf)
    print(f"[{region}] buildings (DuckDB, centroid + intersection, 2 sources)...", flush=True)
    buildings = build_buildings(con, region)
    print(f"[{region}] POI facilities + establishments (DuckDB)...", flush=True)
    poi = build_poi(con, region)

    raw = pd.concat([transport, buildings, poi], axis=1).reindex(full_index)
    # Count/length columns: a tract absent from a join genuinely had zero matches — fill 0, not
    # NaN. cbp_estab_bus is the one column that can be a legitimate null (CBP non-disclosure) —
    # left as NaN, which _capped_ratio already treats as undefined, not zero.
    count_cols = [c for c in raw.columns if c != "cbp_estab_bus"]
    raw[count_cols] = raw[count_cols].fillna(0)

    candidates = build_candidate_gaps(raw)
    result = pd.concat([raw, candidates], axis=1)
    result.index.name = TRACT_ID_COL

    out_path = f"data/processed/{region}-step3-ingredients.parquet"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result.reset_index().to_parquet(out_path, index=False)

    # --- Phase 1 verification numbers (Step 3's required report) ---
    expected = SCORED_TRACT_COUNTS[region]
    print(f"row count: {len(result)} (expected {expected})")
    required_cols = [c for c in raw.columns if c != "cbp_estab_bus"]
    null_counts = result[required_cols].isna().sum()
    print(f"nulls in required (non-CBP) raw columns: {int(null_counts.sum())}")
    if null_counts.sum():
        print(null_counts[null_counts > 0])
    defined_cols = [c for c in result.columns if c.endswith("_defined")]
    print("defined-flag true-rates:")
    print(result[defined_cols].mean().round(3))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "eastern-ok")
