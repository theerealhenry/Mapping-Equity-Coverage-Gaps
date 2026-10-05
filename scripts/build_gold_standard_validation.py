"""
scripts/build_gold_standard_validation.py — Stage 7 Step 9: gold-standard manual validation set.

Selects ~10 tracts spread across all four regions and across strata (urban/rural, tribal/
non-tribal, high/low SVI, water-dominated/not), deliberately including the known water-dominated
tracts from Stage 5/6 (docs/data_manifest.md Section 4.26: 1 in eastern-ok, 2 in northern-ca).
Those GEOIDs were never persisted to a standalone file (only computed in-notebook), so this script
recomputes them from the exact documented method (water_fraction = AWATER / (ALAND + AWATER) > 0.5
against `national-census-tracts`) and writes them to docs/validation/water_dominated_geoids.json
as a byproduct -- closing that loose end from Section 4.26 for free.

For each selected tract, renders a 3-panel comparison map (Overture vs. TIGER named-highway roads,
Overture vs. Microsoft building footprints, Overture vs. HIFLD facility points) clipped to that
one tract, and writes a note with the pipeline's own computed coverage_gap_score/component values.
The "do these visually agree" judgment is deliberately left as a placeholder in each note -- this
step's whole point (per test-driven-development's spirit applied manually) is a real human look at
each map, not a generated guess at what a human would see.

Reuses tested project code wherever it exists rather than re-deriving spatial logic:
`assign_and_clip_lines` for roads (same function Stage 6 uses for the real transport_gap
computation), `load_reference_layer` for every layer small enough to load in-memory per Stage 5's
own 2,000,000-row threshold (roads, HIFLD points, Overture POIs), and DuckDB with a per-tract
ST_Intersects filter only for buildings (2.5M-11.4M rows region-wide -- the one layer family this
project has always kept out of in-memory GeoPandas, per Section 4.21's memory-freeze incident).

Run with:
    python -m scripts.build_gold_standard_validation
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # headless batch rendering -- default TkAgg is unstable in a loop with no display
import matplotlib.pyplot as plt
import pandas as pd
from shapely import wkt as shapely_wkt

from src.config import (
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
    REGIONS,
    TIGER_NAMED_HIGHWAY_MTFCC,
    reference_url,
    strata_national_url,
)
from src.gaps import score_all_regions
from src.geometry import GEOGRAPHIC_CRS, assign_and_clip_lines, configure_duckdb_spatial
from src.io import load_reference_layer, load_strata_table
from src.validate import load_manifest

OUT_DIR = Path("docs/validation")
_HIFLD_LAYERS = {
    "fire": LAYER_HIFLD_FIRE_STATIONS,
    "ems": LAYER_HIFLD_EMS_STATIONS,
    "schools": LAYER_HIFLD_SCHOOLS,
}
# Sums to 10; skewed slightly toward the two largest regions (south-central-tx, maricopa-az) so the
# sample isn't dominated by the two smallest regions' idiosyncrasies.
N_PER_REGION = {"maricopa-az": 3, "northern-ca": 2, "eastern-ok": 2, "south-central-tx": 3}


def _compute_water_dominated(con: duckdb.DuckDBPyConnection, geoids: list[str]) -> list[str]:
    """Section 4.26's documented method, recomputed against the live national table (never
    hardcoded -- these GEOIDs exist nowhere as a saved file yet)."""
    if not geoids:
        return []
    url = strata_national_url("national-census-tracts")
    in_list = ", ".join(f"'{g}'" for g in geoids)
    df = con.execute(
        f"""SELECT "GEOID", "AWATER", "ALAND" FROM read_parquet('{url}')
            WHERE "GEOID" IN ({in_list})"""
    ).fetchdf()
    df["water_fraction"] = df["AWATER"] / (df["ALAND"] + df["AWATER"])
    return sorted(df.loc[df["water_fraction"] > 0.5, "GEOID"].tolist())


def _load_region_strata(region: str) -> pd.DataFrame:
    """Tribal membership: `aiannh_geoid.notna()` (role=identity_metadata, docs/data_manifest.md).
    Rurality: `pct_urban < 50`. SVI: `svi_overall` -- this project's own real column name for the
    CDC/ATSDR Social Vulnerability Index overall percentile rank (the equivalent of the CDC's raw
    `RPL_THEMES` field, renamed to this project's `svi_<theme>` convention during the national
    strata join -- see `docs/DATA_DICTIONARY.md`'s `svi` domain section, whose four theme columns
    `svi_socioeconomic`/`svi_household`/`svi_minority`/`svi_housing_transport` are exactly the CDC
    SVI 2020's four real themes). An earlier version of this function guessed the raw CDC field
    name (`RPL_THEMES`) and printed only a 25-column alphabetical sample when it wasn't found --
    `svi_overall` sorts well past position 25 alphabetically, so the real column was silently
    never reached; see `docs/decision_log.md`'s Stage 7 Step 9 SVI-naming follow-up for the full
    investigation (confirmed present, with matching dtype, in all four regions' own joined strata
    tables via `docs/region_national_schema_consistency.csv`). `svi_covered` (bool; 1.3% national
    null rate on `svi_overall` per `docs/DATA_DICTIONARY.md`) is checked first so the small
    minority of tracts CDC's own SVI release doesn't cover are correctly left undefined, rather
    than trusting a bare non-null check on `svi_overall` alone to mean the same thing.

    Read via `src.io`'s private `_read_flat_parquet` + `_s3_filesystem`, NOT `load_strata_table` --
    this table is the attribute-only joined strata table (SVI/tribal/rurality columns keyed by
    GEOID), with no embedded GeoParquet geo metadata; geometry lives separately in each region's
    own `census-tracts` table. Two things already found the hard way on real runs, not guessed in
    advance: `load_strata_table` assumes every strata table carries geometry and fails loudly on
    this one ("Missing geo metadata..."); and plain `pandas.read_parquet` against the HTTPS URL
    gets a 403 -- this bucket's HTTPS endpoint isn't set up for bare urllib reads the way
    `load_sample_submission`'s CSV path is (that one needs a custom User-Agent, per `src/io.py`'s
    own module docstring); every OTHER loader in this project goes through pyarrow's anonymous S3
    filesystem instead, never raw HTTPS, and `_read_flat_parquet` is the exact existing helper for
    a flat (no-geometry) table via that same transport -- `load_national_strata_attribute_table`
    uses it for the national-level equivalent of this exact table shape."""
    from src.config import strata_s3_path
    from src.io import _read_flat_parquet, _s3_filesystem

    df = _read_flat_parquet(
        _s3_filesystem(), strata_s3_path(region, "strata-tract-table"), context=f"_load_region_strata({region!r})"
    )
    df["GEOID"] = df["GEOID"].astype(str)
    cols = set(df.columns)
    missing = [c for c in ("aiannh_geoid", "pct_urban", "svi_overall", "svi_covered") if c not in cols]
    if missing:
        raise KeyError(
            f"{region}: expected strata columns {missing} not found in the real "
            f"strata-tract-table. Actual columns: {sorted(cols)}. Fix this script's column names "
            "to match reality rather than guessing -- do not proceed with a wrong strata label."
        )
    out = pd.DataFrame(index=df["GEOID"])
    out["is_tribal"] = df["aiannh_geoid"].notna().to_numpy()
    out["is_rural"] = (df["pct_urban"] < 50).to_numpy()
    svi_overall = df["svi_overall"].where(df["svi_covered"].to_numpy())
    n_uncovered = int((~df["svi_covered"]).sum())
    if n_uncovered:
        print(f"[{region}] {n_uncovered} tract(s) have svi_covered=False; SVI strata left as NaN for those")
    # NB: a plain `svi_overall >= median` comparison would silently turn NaN (uncovered tracts)
    # into False, not NaN (pandas/numpy comparisons against NaN return False, never NaN) --
    # exactly the kind of "undefined coerced into a real-looking value" bug this project's own
    # R-005 exists to prevent elsewhere in the pipeline. mask() re-applies NaN afterward instead.
    out["svi_high"] = (svi_overall >= svi_overall.median()).mask(svi_overall.isna()).to_numpy()
    return out


def select_tracts(con: duckdb.DuckDBPyConnection) -> tuple[list[tuple[str, str]], dict[str, list[str]]]:
    manifest = load_manifest()
    scored = score_all_regions().set_index("GEOID")
    selections: list[tuple[str, str]] = []
    water_geoids: dict[str, list[str]] = {}

    for region in REGIONS:
        region_geoids = manifest.loc[manifest["region"] == region, "GEOID"].tolist()
        water = _compute_water_dominated(con, region_geoids)
        water_geoids[region] = water
        print(f"[{region}] {len(water)} water-dominated tract(s) in the scored set: {water}")

        strata = _load_region_strata(region)
        candidates = strata.join(scored[["coverage_gap_score"]], how="inner")
        candidates = candidates.loc[candidates.index.isin(region_geoids)]
        candidates["is_water"] = candidates.index.isin(water)

        picks: list[str] = []
        if water:
            picks.append(water[0])  # deliberate inclusion, per Step 9's explicit instruction
        tribal = candidates.index[candidates["is_tribal"] & ~candidates.index.isin(picks)]
        if len(tribal):
            picks.append(tribal[0])
        rural = candidates.index[candidates["is_rural"] & ~candidates.index.isin(picks)]
        if len(rural) and len(picks) < N_PER_REGION[region]:
            picks.append(rural[0])
        urban = candidates.index[~candidates["is_rural"] & ~candidates.index.isin(picks)]
        if len(urban) and len(picks) < N_PER_REGION[region]:
            picks.append(urban[0])
        # Top up any remaining slots with the highest-coverage_gap_score tracts not yet picked --
        # deliberately includes at least one "bad-looking" tract per region, worth eyeballing hard.
        remaining = candidates.loc[~candidates.index.isin(picks)].sort_values(
            "coverage_gap_score", ascending=False
        )
        i = 0
        while len(picks) < N_PER_REGION[region] and i < len(remaining):
            picks.append(remaining.index[i])
            i += 1

        selections.extend((region, geoid) for geoid in picks[: N_PER_REGION[region]])

    return selections, water_geoids


def _tract_polygon(region: str, geoid: str) -> gpd.GeoDataFrame:
    tracts = load_strata_table(region, "census-tracts")
    row = tracts.loc[tracts["GEOID"] == geoid]
    if row.empty:
        raise KeyError(f"{geoid} not found in {region}'s census-tracts table")
    return row.iloc[[0]]


def _clip_points(points: gpd.GeoDataFrame, tract: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if points.empty:
        return points
    mask = points.within(tract.geometry.iloc[0])
    return points.loc[mask]


def _duckdb_geometries_near_tract(
    con: duckdb.DuckDBPyConnection, url: str, tract_wkt: str, *, where_extra: str = ""
) -> gpd.GeoDataFrame:
    """Shared helper: pulls just the rows intersecting one tract's WKT via DuckDB (no CRS
    transform involved, so R-002's ST_Transform axis-order footgun does not apply -- both sides
    are already the bucket's native CRS84 (x, y) = (lon, lat) coordinates), returned as a small
    in-memory GeoDataFrame. Used for buildings (too large for a full in-memory geopandas load per
    Stage 5's 2,000,000-row threshold) and for Overture POIs filtered to facility categories
    (struct-typed `categories.primary` is far simpler to read via DuckDB's native dot-path than to
    unpack from a pyarrow struct column in pandas -- reuses the same SQL shape
    `scripts/build_stage6_step3_ingredients.py`'s `build_poi()` already tests)."""
    extra = f" AND {where_extra}" if where_extra else ""
    df = con.execute(
        f"""
        SELECT ST_AsText(CAST(geometry AS GEOMETRY)) AS wkt FROM read_parquet('{url}')
        WHERE ST_Intersects(CAST(geometry AS GEOMETRY), ST_GeomFromText('{tract_wkt}')){extra}
        """
    ).fetchdf()
    if df.empty:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=GEOGRAPHIC_CRS)
    return gpd.GeoDataFrame(
        {"geometry": df["wkt"].map(shapely_wkt.loads)}, geometry="geometry", crs=GEOGRAPHIC_CRS
    )


def _overture_facilities_near_tract(
    con: duckdb.DuckDBPyConnection, region: str, tract_wkt: str
) -> gpd.GeoDataFrame:
    """Overture POI facilities (fire/EMS/schools categories) intersecting one tract. Filters on
    `categories.primary` via DuckDB's native struct dot-path -- the same SQL shape
    `scripts/build_stage6_step3_ingredients.py`'s `build_poi()` already uses and tests -- rather
    than unpacking Overture's struct-typed `categories` column from a pyarrow-backed pandas frame,
    which this project has never done and would be new, unverified code for a one-off map."""
    url = reference_url(region, LAYER_OVERTURE_POIS)
    facility_categories = {c for cats in POI_FACILITY_CATEGORY_MAP.values() for c in cats}
    cat_list = ", ".join(f"'{c}'" for c in facility_categories)
    df = con.execute(
        f"""
        SELECT ST_AsText(CAST(geometry AS GEOMETRY)) AS wkt
        FROM (SELECT categories.primary AS category, geometry FROM read_parquet('{url}')) p
        WHERE category IN ({cat_list})
          AND ST_Intersects(CAST(geometry AS GEOMETRY), ST_GeomFromText('{tract_wkt}'))
        """
    ).fetchdf()
    if df.empty:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=GEOGRAPHIC_CRS)
    return gpd.GeoDataFrame(
        {"geometry": df["wkt"].map(shapely_wkt.loads)}, geometry="geometry", crs=GEOGRAPHIC_CRS
    )


def render_map(con: duckdb.DuckDBPyConnection, region: str, geoid: str, out_path: Path) -> None:
    tract = _tract_polygon(region, geoid)
    tract_wkt = tract.geometry.iloc[0].wkt

    overture_roads = load_reference_layer(region, LAYER_OVERTURE_ROADS)
    overture_roads = overture_roads[overture_roads["class"].isin(OVERTURE_NAMED_HIGHWAY_CLASSES)]
    tiger_roads = load_reference_layer(region, LAYER_CENSUS_TIGER_ROADS)
    tiger_roads = tiger_roads[tiger_roads["MTFCC"].isin(TIGER_NAMED_HIGHWAY_MTFCC)]
    overture_roads_clipped = assign_and_clip_lines(overture_roads, tract)
    tiger_roads_clipped = assign_and_clip_lines(tiger_roads, tract)

    overture_buildings = _duckdb_geometries_near_tract(
        con, reference_url(region, LAYER_OVERTURE_BUILDINGS), tract_wkt
    )
    microsoft_buildings = _duckdb_geometries_near_tract(
        con, reference_url(region, LAYER_MICROSOFT_BUILDINGS), tract_wkt
    )
    overture_facilities = _overture_facilities_near_tract(con, region, tract_wkt)
    hifld_points = {
        subtype: _clip_points(load_reference_layer(region, layer), tract)
        for subtype, layer in _HIFLD_LAYERS.items()
    }
    hifld_all = gpd.GeoDataFrame(
        pd.concat([g for g in hifld_points.values() if not g.empty], ignore_index=True)
        if any(not g.empty for g in hifld_points.values())
        else pd.DataFrame({"geometry": []}),
        geometry="geometry",
        crs=GEOGRAPHIC_CRS,
    )

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    panels = [
        ("Roads: Overture (blue) vs. TIGER (orange)", overture_roads_clipped, tiger_roads_clipped),
        ("Buildings: Overture (blue) vs. Microsoft (orange)", overture_buildings, microsoft_buildings),
        ("Facilities: Overture (blue) vs. HIFLD (orange)", overture_facilities, hifld_all),
    ]
    for ax, (title, overture_layer, reference_layer) in zip(axes, panels):
        tract.boundary.plot(ax=ax, color="black", linewidth=1.5, zorder=3)
        if not reference_layer.empty:
            reference_layer.plot(ax=ax, color="orange", markersize=15, linewidth=1.5, alpha=0.8, zorder=2)
        if not overture_layer.empty:
            overture_layer.plot(ax=ax, color="tab:blue", markersize=8, linewidth=1.0, alpha=0.8, zorder=1)
        ax.set_title(title, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"{region} — {geoid}", fontsize=13)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def write_note(region: str, geoid: str, water_geoids: dict[str, list[str]], out_path: Path) -> None:
    scored = score_all_regions().set_index("GEOID")
    row = scored.loc[geoid]
    strata = _load_region_strata(region).loc[geoid]
    is_water = geoid in water_geoids.get(region, [])

    note = f"""# Gold-standard validation — {region} / {geoid}

**Strata**: tribal={bool(strata['is_tribal'])}, rural={bool(strata['is_rural'])}, \
svi_high={strata['svi_high'] if pd.notna(strata['svi_high']) else 'unavailable'}, \
water_dominated={is_water}

**Pipeline's own computed values for this tract** (from `src.gaps.score_all_regions()`, current \
default `building_gap_centroid`):

| component | value | defined |
|---|---|---|
| coverage_gap_score | {row['coverage_gap_score']:.4f} | — |
| transport_gap | {row['transport_gap']:.4f} | {row['transport_defined']} |
| building_gap | {row['building_gap']:.4f} | {row['building_defined']} |
| poi_gap | {row['poi_gap']:.4f} | {row['poi_defined']} |
| poi_gap_fire | {row['poi_gap_fire']:.4f} | {row['poi_gap_fire_defined']} |
| poi_gap_ems | {row['poi_gap_ems']:.4f} | {row['poi_gap_ems_defined']} |
| poi_gap_schools | {row['poi_gap_schools']:.4f} | {row['poi_gap_schools_defined']} |
| poi_gap_establishments | {row['poi_gap_establishments']:.4f} | {row['poi_gap_establishments_defined']} |

![map](./map.png)

## Manual visual-agreement judgment — [TO FILL IN]

For each panel, does the map visually agree with the computed gap value above? Specifically:
- **Roads**: does the blue (Overture)/orange (TIGER) density difference match `transport_gap`'s
  size — e.g. a high transport_gap should visibly show much sparser blue than orange?
- **Buildings**: does the same hold for `building_gap` against the Overture/Microsoft footprint
  density in the middle panel?
- **Facilities**: does the same hold for `poi_gap`'s facility sub-parts against the Overture/HIFLD
  point density in the right panel?
{"- **Water-dominance context**: this tract is >50% water by area (Section 4.26) — an extreme or unstable-looking gap value here may be a real artifact of having little land area for buildings/roads/POIs to occupy, not a pipeline bug. Note whether that reads as the likely explanation." if is_water else ""}

[Henry: write your real observation here after looking at map.png — agree / disagree, and why.
Any disagreement is treated as seriously as a failed automated test: localize it, then either fix
a real bug or document why it's a known, explainable limitation (e.g. water-dominance).]
"""
    out_path.write_text(note, encoding="utf-8")


def main() -> None:
    con = duckdb.connect()
    configure_duckdb_spatial(con)
    con.execute("INSTALL httpfs; LOAD httpfs;")

    selections, water_geoids = select_tracts(con)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "water_dominated_geoids.json").write_text(
        json.dumps(water_geoids, indent=2), encoding="utf-8"
    )

    index_lines = ["# Gold-standard validation set — Stage 7 Step 9", "", "| region | GEOID | note |", "|---|---|---|"]
    for region, geoid in selections:
        print(f"[{region}] rendering {geoid}...", flush=True)
        tract_dir = OUT_DIR / f"{region}_{geoid}"
        render_map(con, region, geoid, tract_dir / "map.png")
        write_note(region, geoid, water_geoids, tract_dir / "note.md")
        index_lines.append(f"| {region} | {geoid} | [{region}_{geoid}/note.md](./{region}_{geoid}/note.md) |")

    (OUT_DIR / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {len(selections)} validation entries to {OUT_DIR}/")
    print("Next: open each note.md, look at its map.png, and fill in the manual judgment section.")


if __name__ == "__main__":
    main()
