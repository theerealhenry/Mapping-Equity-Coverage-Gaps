"""
Verifies src/geometry.py's own documented claim about geodesic_length_m's precision: that its
equal-area-projection (EPSG:5070) length approximation carries "a few tenths of a percent"
distortion, "well under any threshold that would change a tract's relative coverage-gap ranking".
That claim is already in the codebase (geometry.py's EQUAL_AREA_CRS docstring, docs/risk_register.md)
-- this checks it against a TRUE geodesic length (WGS84 ellipsoid, via pyproj.Geod), rather than
taking the prose on faith, and separately checks whether the distortion cancels out in the
transport_gap RATIO (since both Overture and TIGER lengths go through the identical projection).

Run from the repo root:
    python scripts/audit/check_transport_length_precision.py eastern-ok

Uses the exact same clip step (`assign_and_clip_lines`) and the exact same named-highway filters
(`OVERTURE_NAMED_HIGHWAY_CLASSES`/`TIGER_NAMED_HIGHWAY_MTFCC`) the production ingredients script
uses, so this measures the real pipeline's actual clipped segments, not a synthetic approximation
of them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from pyproj import Geod

from src.config import (
    LAYER_CENSUS_TIGER_ROADS,
    LAYER_OVERTURE_ROADS,
    OVERTURE_NAMED_HIGHWAY_CLASSES,
    TIGER_NAMED_HIGHWAY_MTFCC,
)
from src.geometry import assign_and_clip_lines, geodesic_length_m
from src.io import load_reference_layer, load_strata_table

REGION = sys.argv[1] if len(sys.argv) > 1 else "eastern-ok"
_GEOD = Geod(ellps="WGS84")


def true_geodesic_length_m(gdf) -> pd.Series:
    """Real ellipsoidal (WGS84) length via pyproj's Geod -- the ground-truth this project's own
    equal-area-projection approximation is checked against. Sums Geod.line_length over every
    LineString in a MultiLineString when needed."""
    def _one(geom):
        if geom is None or geom.is_empty:
            return np.nan
        if geom.geom_type == "LineString":
            lons, lats = geom.xy
            return _GEOD.line_length(lons, lats)
        if geom.geom_type == "MultiLineString":
            return sum(_GEOD.line_length(*g.xy) for g in geom.geoms)
        raise ValueError(f"unexpected geometry type for length: {geom.geom_type}")
    return gdf.geometry.apply(_one)


def main() -> None:
    print(f"Region: {REGION}\n")
    tracts = load_strata_table(REGION, "census-tracts")[["GEOID", "geometry"]]

    overture_roads = load_reference_layer(REGION, LAYER_OVERTURE_ROADS)
    tiger_roads = load_reference_layer(REGION, LAYER_CENSUS_TIGER_ROADS)
    overture_roads = overture_roads[overture_roads["class"].isin(OVERTURE_NAMED_HIGHWAY_CLASSES)]
    tiger_roads = tiger_roads[tiger_roads["MTFCC"].isin(TIGER_NAMED_HIGHWAY_MTFCC)]

    print("Clipping (assign_and_clip_lines, same as production)...")
    overture_clipped = assign_and_clip_lines(overture_roads, tracts)
    tiger_clipped = assign_and_clip_lines(tiger_roads, tracts)

    print("Computing lengths both ways (this can take a minute for the true-geodesic pass)...")
    overture_equal_area = geodesic_length_m(overture_clipped)
    overture_true = true_geodesic_length_m(overture_clipped)
    tiger_equal_area = geodesic_length_m(tiger_clipped)
    tiger_true = true_geodesic_length_m(tiger_clipped)

    # --- Segment-level distortion check ---
    for label, equal_area, true in (
        ("overture", overture_equal_area, overture_true),
        ("tiger", tiger_equal_area, tiger_true),
    ):
        pct_diff = ((equal_area - true) / true * 100).replace([np.inf, -np.inf], np.nan).dropna()
        print(
            f"\n{label} segment-level equal-area vs true-geodesic distortion: "
            f"mean={pct_diff.mean():+.4f}%  median={pct_diff.median():+.4f}%  "
            f"max_abs={pct_diff.abs().max():.4f}%  n={len(pct_diff)}"
        )

    # --- Per-tract transport_gap comparison: does the distortion survive into the ratio? ---
    def per_tract_gap(clipped, lengths, tract_col="GEOID"):
        return lengths.groupby(clipped[tract_col]).sum()

    overture_len_by_tract_ea = per_tract_gap(overture_clipped, overture_equal_area)
    overture_len_by_tract_true = per_tract_gap(overture_clipped, overture_true)
    tiger_len_by_tract_ea = per_tract_gap(tiger_clipped, tiger_equal_area)
    tiger_len_by_tract_true = per_tract_gap(tiger_clipped, tiger_true)

    idx = tiger_len_by_tract_ea.index.intersection(overture_len_by_tract_ea.index)
    idx = idx[(tiger_len_by_tract_ea.loc[idx] > 0) & (tiger_len_by_tract_true.loc[idx] > 0)]

    gap_ea = (1 - (overture_len_by_tract_ea.loc[idx] / tiger_len_by_tract_ea.loc[idx]).clip(upper=1)).clip(lower=0)
    gap_true = (1 - (overture_len_by_tract_true.loc[idx] / tiger_len_by_tract_true.loc[idx]).clip(upper=1)).clip(lower=0)

    gap_diff = (gap_ea - gap_true).abs()
    print(f"\ntransport_gap comparison across {len(idx)} tracts (equal-area formula vs true-geodesic formula):")
    print(f"  mean |diff| = {gap_diff.mean():.6f}")
    print(f"  max  |diff| = {gap_diff.max():.6f}  (at GEOID {gap_diff.idxmax()})")
    print(f"  tracts with |diff| > 0.001: {(gap_diff > 0.001).sum()} / {len(idx)}")
    print(f"  tracts with |diff| > 0.01:  {(gap_diff > 0.01).sum()} / {len(idx)}")

    # --- Ranking check: does the equal-area approximation ever flip which of two tracts has the
    # larger transport_gap, among adjacent-ranked tracts? A coarse proxy: Spearman-style check via
    # rank correlation. ---
    rank_ea = gap_ea.rank()
    rank_true = gap_true.rank()
    rank_diff = (rank_ea - rank_true).abs()
    print(f"\nrank(transport_gap) stability: mean |rank diff| = {rank_diff.mean():.2f} positions, "
          f"max = {rank_diff.max():.0f} positions (out of {len(idx)} tracts)")


if __name__ == "__main__":
    main()
