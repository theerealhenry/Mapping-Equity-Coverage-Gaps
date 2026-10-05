"""
Checks how many facility/POI points are lost to the `ST_Within` boundary-touching edge case in
the production pipeline (scripts/build_stage6_step3_ingredients.py's build_poi / build_buildings).

Background: `ST_Within(point, polygon)` requires the point to be in the polygon's INTERIOR, not
merely on its boundary. A point sitting exactly on a shared tract line is `within` neither
adjacent tract, so it silently contributes to no tract's count at all -- a real, if likely small,
systematic undercount distinct from any formula bug.

This script measures the actual size of that effect on real data, per region, for every point
layer the production pipeline assigns via ST_Within (Overture POIs, HIFLD fire/ems/schools, and
Overture/Microsoft building centroids): total point count, how many are matched by ST_Within
(today's production behavior), and how many are matched by ST_Intersects but NOT by ST_Within --
i.e. genuinely boundary-touching points currently silently dropped from every tract's count.

Uses the exact same DuckDB + HTTPS read path as the production ingredients script (see
`_register_tracts`/`build_poi`/`build_buildings` there) -- not a different transport that could
pass or fail independently of it.

Run from the repo root (any single region is enough to establish the effect size; pass a region
name to check a different one, e.g. the largest, south-central-tx, for the most points to find
edge cases in):
    python scripts/audit/check_boundary_touching_points.py eastern-ok
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb

from src.config import (
    LAYER_HIFLD_EMS_STATIONS,
    LAYER_HIFLD_FIRE_STATIONS,
    LAYER_HIFLD_SCHOOLS,
    LAYER_MICROSOFT_BUILDINGS,
    LAYER_OVERTURE_BUILDINGS,
    LAYER_OVERTURE_POIS,
    reference_url,
    strata_url,
)
from src.geometry import configure_duckdb_spatial

REGION = sys.argv[1] if len(sys.argv) > 1 else "eastern-ok"

POINT_LAYERS = {
    "overture-pois": LAYER_OVERTURE_POIS,
    "hifld-fire": LAYER_HIFLD_FIRE_STATIONS,
    "hifld-ems": LAYER_HIFLD_EMS_STATIONS,
    "hifld-schools": LAYER_HIFLD_SCHOOLS,
}

# Buildings are assigned by CENTROID (a derived point, not the raw geometry) -- checked separately
# since it needs ST_Centroid first, matching build_buildings' own centroid_counts query exactly.
CENTROID_LAYERS = {
    "overture-buildings": LAYER_OVERTURE_BUILDINGS,
    "microsoft-buildings": LAYER_MICROSOFT_BUILDINGS,
}


def main() -> None:
    print(f"Region: {REGION}\n")
    con = duckdb.connect()
    configure_duckdb_spatial(con)
    con.execute("INSTALL httpfs; LOAD httpfs;")

    tracts_url = strata_url(REGION, "census-tracts")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE tracts AS
        SELECT "GEOID", CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{tracts_url}')
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS tracts_geom_idx ON tracts USING RTREE (geometry)")

    def report(label: str, points_sql_geom: str, source_table_sql: str, total_points: int) -> None:
        within_n = con.execute(
            f"""
            SELECT COUNT(DISTINCT p.rowid) FROM ({source_table_sql}) p
            JOIN tracts t ON ST_Within({points_sql_geom}, t.geometry)
            """
        ).fetchone()[0]
        boundary_only_n = con.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT p.rowid FROM ({source_table_sql}) p
                WHERE EXISTS (SELECT 1 FROM tracts t WHERE ST_Intersects({points_sql_geom}, t.geometry))
                  AND NOT EXISTS (SELECT 1 FROM tracts t WHERE ST_Within({points_sql_geom}, t.geometry))
            )
            """
        ).fetchone()[0]
        outside_n = total_points - within_n - boundary_only_n
        pct = (100 * boundary_only_n / total_points) if total_points else 0.0
        print(
            f"  {label:22s} total={total_points:>7,}  within={within_n:>7,}  "
            f"boundary-only(dropped)={boundary_only_n:>5,} ({pct:.3f}%)  "
            f"outside-region={outside_n:>6,}"
        )

    print("--- Raw point layers (ST_Within(point, tract), matches build_poi's own query) ---")
    for label, layer in POINT_LAYERS.items():
        url = reference_url(REGION, layer)
        source_sql = f"SELECT row_number() OVER () AS rowid, CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{url}')"
        total = con.execute(f"SELECT COUNT(*) FROM ({source_sql})").fetchone()[0]
        report(label, "p.geometry", source_sql, total)

    print("\n--- Building centroids (ST_Within(ST_Centroid(geom), tract), matches build_buildings' centroid_counts) ---")
    for label, layer in CENTROID_LAYERS.items():
        url = reference_url(REGION, layer)
        source_sql = f"SELECT row_number() OVER () AS rowid, CAST(geometry AS GEOMETRY) AS geometry FROM read_parquet('{url}')"
        total = con.execute(f"SELECT COUNT(*) FROM ({source_sql})").fetchone()[0]
        report(label, "ST_Centroid(p.geometry)", source_sql, total)


if __name__ == "__main__":
    main()
