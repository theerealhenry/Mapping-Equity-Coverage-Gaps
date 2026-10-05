"""
scripts/debug_building_gap_centroid.py — Stage 7 Step 9 follow-up: root-cause investigation of the
`building_gap_centroid` discrepancy flagged in `docs/validation/` for three tracts
(eastern-ok/40109108508, northern-ca/06033000502, south-central-tx/48007950102), plus one contrast
tract (south-central-tx/48427950701, which showed clean agreement).

Purpose (per agent-skills:debugging-and-error-recovery's triage checklist):
  Step 1 (Reproduce) — independently recompute building_gap_centroid for these 4 tracts directly
    against the live bucket, and cross-check against the stored value in
    data/processed/<region>-step3-ingredients.parquet. If they disagree, the bug is a stale/wrong
    ingredients file, not the formula itself.
  Step 2 (Localize) — for every building (both Overture and Microsoft) that INTERSECTS the tract
    polygon (the population a human looking at the map would see "inside" the tract), determine
    whether its CENTROID also falls within the tract (the actual production rule,
    `ST_Within(ST_Centroid(geom), tract.geometry)`), or whether the centroid falls in a
    *different* tract, or in neither (open water / gap). This directly tests the hypothesis
    written into docs/decision_log.md: that centroid-based assignment silently reassigns
    boundary-hugging buildings in irregularly-shaped, water-adjacent tracts to a neighboring
    tract, making the map (which shows every intersecting building) look like a coverage gap that
    the centroid-based formula does not see, because the buildings are legitimately "owned" by a
    neighboring tract instead.
  Step 3/4 (Reduce / root cause) — a tract shape-compactness metric (Polsby-Popper,
    4*pi*area/perimeter^2 in an equal-area CRS; 1.0 = circle, near 0 = long/thin/irregular) is
    computed for all 4 tracts, to test whether the 3 flagged tracts are objectively more irregular
    than the contrast tract, rather than relying on the map images alone.

Run with:
    python -m scripts.debug_building_gap_centroid
"""

from __future__ import annotations

import duckdb
import geopandas as gpd
import pandas as pd

from src.config import (
    LAYER_MICROSOFT_BUILDINGS,
    LAYER_OVERTURE_BUILDINGS,
    reference_url,
    strata_url,
)
from src.geometry import configure_duckdb_spatial

TRACT_ID_COL = "GEOID"

# The 3 flagged tracts (from docs/validation/*/note.md) + 1 contrast tract that showed clean
# agreement, used as a control.
CASES = [
    ("eastern-ok", "40109108508", "FLAGGED"),
    ("northern-ca", "06033000502", "FLAGGED"),
    ("south-central-tx", "48007950102", "FLAGGED"),
    ("south-central-tx", "48427950701", "CONTROL (clean agreement in Step 9)"),
]

EQUAL_AREA_CRS = "EPSG:5070"  # CONUS Albers -- standard equal-area CRS for US tract-area comparisons


def _register_region_tracts(con: duckdb.DuckDBPyConnection, region: str) -> None:
    """Registers ALL of the region's tracts (not just the one under investigation), read straight
    off the remote parquet -- the exact same query `_register_tracts()` in
    `scripts/build_stage6_step3_ingredients.py` uses for the real production pipeline, reused
    here rather than inventing a second, unverified way to get tract geometry into DuckDB. Having
    every tract (not just the target) registered is what lets us identify which neighboring tract
    (if any) a reassigned building's centroid actually belongs to -- the single most important
    piece of evidence for the boundary-reassignment hypothesis."""
    tracts_url = strata_url(region, "census-tracts")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE tracts AS
        SELECT "GEOID", CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{tracts_url}')
        """
    )


def _polsby_popper(tract_geom_wkt: str) -> float:
    """Shape-compactness score in an equal-area CRS: 4*pi*Area/Perimeter^2. 1.0 = a perfect
    circle; values near 0 indicate a long, thin, or highly irregular (e.g. jagged coastal)
    boundary -- exactly the shape where centroid-vs-intersects spatial-assignment divergence is
    most likely to matter."""
    gdf = gpd.GeoSeries.from_wkt([tract_geom_wkt], crs="OGC:CRS84").to_crs(EQUAL_AREA_CRS)
    geom = gdf.iloc[0]
    return float(4 * 3.141592653589793 * geom.area / (geom.length**2))


def investigate_tract(con: duckdb.DuckDBPyConnection, region: str, geoid: str, label: str) -> dict:
    print(f"\n{'=' * 90}\n{region} / {geoid}  [{label}]\n{'=' * 90}")

    tract_row = con.execute(
        "SELECT ST_AsText(geometry) AS wkt FROM tracts WHERE \"GEOID\" = ?", [geoid]
    ).fetchone()
    if tract_row is None:
        raise KeyError(f"{geoid} not found in {region}'s tracts table -- check GEOID spelling")
    tract_wkt = tract_row[0]
    compactness = _polsby_popper(tract_wkt)
    print(f"Polsby-Popper compactness: {compactness:.4f}  (1.0 = circle, lower = more irregular)")

    result = {"region": region, "GEOID": geoid, "label": label, "compactness": compactness}

    for source_label, layer in (("overture", LAYER_OVERTURE_BUILDINGS), ("microsoft", LAYER_MICROSOFT_BUILDINGS)):
        url = reference_url(region, layer)
        con.execute(
            f"CREATE OR REPLACE TABLE _bld AS "
            f"SELECT CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{url}')"
        )

        # Every building that INTERSECTS the target tract -- this is what a human looking at a map
        # clipped to the tract boundary would see as "inside" the tract.
        con.execute(
            f"""
            CREATE OR REPLACE TABLE _candidates AS
            SELECT b.geometry AS geometry, ST_Centroid(b.geometry) AS centroid
            FROM _bld b, (SELECT ST_GeomFromText(?) AS geometry) t
            WHERE ST_Intersects(b.geometry, t.geometry)
            """,
            [tract_wkt],
        )
        n_intersecting = con.execute("SELECT COUNT(*) FROM _candidates").fetchone()[0]

        # Of those, how many have their CENTROID inside the target tract? (the production rule)
        n_centroid_within_target = con.execute(
            """
            SELECT COUNT(*) FROM _candidates c, (SELECT ST_GeomFromText(?) AS geometry) t
            WHERE ST_Within(c.centroid, t.geometry)
            """,
            [tract_wkt],
        ).fetchone()[0]

        # Of the REMAINDER (centroid not in target tract), how many have their centroid inside
        # SOME OTHER tract in the same region (i.e., genuinely "owned" by a neighbor), vs. neither
        # (open water / a gap between tract polygons)?
        n_centroid_elsewhere_in_region = con.execute(
            """
            SELECT COUNT(*) FROM _candidates c
            JOIN tracts t2 ON ST_Within(c.centroid, t2.geometry)
            WHERE t2."GEOID" != ?
            """,
            [geoid],
        ).fetchone()[0]

        n_centroid_in_no_tract = n_intersecting - n_centroid_within_target - n_centroid_elsewhere_in_region

        # Full-region centroid-based count for THIS tract (matches build_buildings()'s real query
        # exactly -- this is the actual production number, independent of the "intersecting"
        # candidate set above, as a cross-check that the two computations of the same quantity
        # agree).
        n_centroid_production = con.execute(
            """
            SELECT COUNT(*) FROM _bld b JOIN tracts t ON ST_Within(ST_Centroid(b.geometry), t.geometry)
            WHERE t."GEOID" = ?
            """,
            [geoid],
        ).fetchone()[0]

        assert n_centroid_production == n_centroid_within_target, (
            f"Internal inconsistency: the two independent ways of counting centroid-within-tract "
            f"buildings disagree ({n_centroid_production} vs {n_centroid_within_target}) for "
            f"{region}/{geoid}/{source_label} -- investigate before trusting anything else below."
        )

        print(f"\n  {source_label.upper()} buildings:")
        print(f"    intersecting the tract (what the map shows):     {n_intersecting}")
        print(f"    centroid WITHIN this tract (production count):    {n_centroid_within_target}")
        print(f"    centroid actually in a NEIGHBORING tract:          {n_centroid_elsewhere_in_region}")
        print(f"    centroid in NO tract (water/gap):                  {n_centroid_in_no_tract}")
        if n_intersecting > 0:
            pct_reassigned = 100 * (n_intersecting - n_centroid_within_target) / n_intersecting
            print(f"    -> {pct_reassigned:.1f}% of visually-intersecting buildings are NOT "
                  f"counted for this tract under the centroid rule")

        result[f"{source_label}_intersecting"] = n_intersecting
        result[f"{source_label}_centroid_within"] = n_centroid_within_target
        result[f"{source_label}_centroid_elsewhere"] = n_centroid_elsewhere_in_region
        result[f"{source_label}_centroid_no_tract"] = n_centroid_in_no_tract

    overture_c = result["overture_centroid_within"]
    microsoft_c = result["microsoft_centroid_within"]
    building_gap_centroid_recomputed = (
        None if microsoft_c == 0 else max(0.0, 1 - min(1.0, overture_c / microsoft_c))
    )
    overture_i = result["overture_intersecting"]
    microsoft_i = result["microsoft_intersecting"]
    building_gap_intersecting_of_map = (
        None if microsoft_i == 0 else max(0.0, 1 - min(1.0, overture_i / microsoft_i))
    )
    result["building_gap_centroid_recomputed"] = building_gap_centroid_recomputed
    result["building_gap_if_using_map_intersecting_counts"] = building_gap_intersecting_of_map

    print(f"\n  building_gap_centroid, recomputed live:              "
          f"{building_gap_centroid_recomputed}")
    print(f"  building_gap if the MAP's intersecting counts were used instead: "
          f"{building_gap_intersecting_of_map}")

    return result


def main() -> None:
    con = duckdb.connect()
    configure_duckdb_spatial(con)
    con.execute("INSTALL httpfs; LOAD httpfs;")

    all_results = []
    registered_regions: set[str] = set()
    for region, geoid, label in CASES:
        if region not in registered_regions:
            _register_region_tracts(con, region)
            registered_regions.add(region)
        all_results.append(investigate_tract(con, region, geoid, label))

    # Cross-check against the stored step3-ingredients.parquet value for each region, where it
    # exists on this machine -- confirms whether the note.md values came from a stale file.
    print(f"\n{'=' * 90}\nCross-check against data/processed/<region>-step3-ingredients.parquet\n{'=' * 90}")
    for region, geoid, label in CASES:
        try:
            ingredients = pd.read_parquet(f"data/processed/{region}-step3-ingredients.parquet")
        except FileNotFoundError:
            print(f"  {region}: step3-ingredients.parquet not found locally -- skipping cross-check")
            continue
        row = ingredients[ingredients[TRACT_ID_COL] == geoid]
        if row.empty:
            print(f"  {region}/{geoid}: GEOID not found in step3-ingredients.parquet")
            continue
        stored = row.iloc[0]
        recomputed = next(r for r in all_results if r["region"] == region and r["GEOID"] == geoid)
        print(
            f"  {region}/{geoid}: stored building_gap_centroid={stored['building_gap_centroid']:.4f} "
            f"(overture_count={stored['overture_building_count_centroid']:.0f}, "
            f"microsoft_count={stored['microsoft_building_count_centroid']:.0f})  vs.  "
            f"recomputed live overture={recomputed['overture_centroid_within']}, "
            f"microsoft={recomputed['microsoft_centroid_within']}"
        )
        match = (
            int(stored["overture_building_count_centroid"]) == recomputed["overture_centroid_within"]
            and int(stored["microsoft_building_count_centroid"]) == recomputed["microsoft_centroid_within"]
        )
        print(f"    -> {'MATCH (data is fresh, not stale)' if match else 'MISMATCH -- ingredients file is stale, re-run Step 3'}")

    print(f"\n{'=' * 90}\nSummary table\n{'=' * 90}")
    summary = pd.DataFrame(all_results)
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
