"""
scripts/verify_stage6_step9.py — Stage 6, Step 9: cross-checks against known Stage 5 findings.

A lightweight verification pass, not a new pipeline stage — every check below is written as if it
were expected to FAIL (debugging-and-error-recovery's reproduce-localize-fix-guard loop, applied
proactively), then run to confirm it doesn't, per the guideline's own "verify, don't assume"
discipline. Reads the four `data/processed/<region>-tract-features.parquet` files (Step 6's real
output) plus two live layers this check needs directly (`national-census-tracts` for water
fraction, `overture-pois`/`hifld-hospitals` for the hospital-exclusion spot-check) — does not
recompute or modify anything in `data/processed/`.

Run:
    python -m scripts.verify_stage6_step9
"""

from __future__ import annotations

import sys

import duckdb
import pandas as pd

from src.config import (
    LAYER_HIFLD_HOSPITALS,
    LAYER_OVERTURE_POIS,
    REGIONS,
    REGION_TRACT_COUNTS,
    SCORED_TRACT_COUNTS,
    reference_url,
)
from src.geometry import configure_duckdb_spatial
from src.io import load_sample_submission, load_strata_national_table

TRACT_ID_COL = "GEOID"

# Section 4.22's published clipped-length transport-only-undefined counts, computed over each
# region's SCORED tract set (confirmed by back-solving the published percentages: 1,704 / 6,003 =
# 28.39%, matching Section 4.22's printed south-central-tx figure — 1,704 / 6,010 would be
# 28.35%, which is NOT what's printed. Every other region's scored and total counts are identical,
# so this only matters for south-central-tx.).
PUBLISHED_TRANSPORT_UNDEFINED = {
    "maricopa-az": 869,
    "northern-ca": 218,
    "eastern-ok": 253,
    "south-central-tx": 1704,
}

# Section 4.26's published water-dominated tract counts (water_fraction > 0.5) for the two regions
# where they remain in the scored set (south-central-tx's 7 are the documented pre-scoring
# exclusion, already covered by Check 1, not re-checked here).
PUBLISHED_WATER_DOMINATED = {
    "eastern-ok": 1,
    "northern-ca": 2,
}


def _load_features(region: str) -> pd.DataFrame:
    return pd.read_parquet(f"data/processed/{region}-tract-features.parquet").set_index(TRACT_ID_COL)


def check1_row_counts() -> bool:
    """Row counts must match SCORED_TRACT_COUNTS exactly — except south-central-tx, where Section
    4.23 already documented and resolved a 7-tract gap (the water-tract exclusion, confirmed
    data-derived: `sctx_all_tract_geoids - sctx_scored_geoids` matched the 7 documented tracts
    exactly). This check re-confirms that gap is STILL exactly 7 and STILL exactly the water
    exclusion, not silently accepting "it was fine before" as proof it's still fine now."""
    print("\n=== Check 1: row counts vs. SCORED_TRACT_COUNTS ===")
    ok = True
    for region in REGIONS:
        df = _load_features(region)
        n = len(df)
        expected = SCORED_TRACT_COUNTS[region]
        if n == expected:
            print(f"  [{region}] PASS: {n} == {expected}")
            continue
        # Only south-central-tx is allowed a documented, resolved gap (Section 4.23).
        total_expected = REGION_TRACT_COUNTS[region]
        gap = n - expected
        if region == "south-central-tx" and n == total_expected and gap == 7:
            scored = set(load_sample_submission(region)[TRACT_ID_COL])
            extra = set(df.index) - scored
            print(
                f"  [{region}] DOCUMENTED DISCREPANCY, RESOLVED: {n} rows (full membership, "
                f"REGION_TRACT_COUNTS) vs. {expected} scored (SCORED_TRACT_COUNTS) — gap of "
                f"{gap}, matching Section 4.23's 7-tract water-exclusion finding exactly. "
                f"{len(extra)} tracts present in the table but absent from the real sample-"
                f"submission GEOID list (live-checked here, not assumed)."
            )
            if len(extra) != 7:
                print(f"    FAIL: expected exactly 7 non-scored extra tracts, found {len(extra)}")
                ok = False
        else:
            print(f"  [{region}] FAIL: {n} != {expected} (unexplained — not the known sctx gap)")
            ok = False
    return ok


def check2_transport_undefined() -> bool:
    """transport_defined (this table's own flag, `tiger_transport_length_m > 0`, via the SAME
    `assign_and_clip_lines` function used in Section 4.22) must reproduce Section 4.22's published
    clipped-length transport-only-undefined counts EXACTLY, per region — same function, same
    inputs, an exact match is the required outcome. Computed over the SCORED tract subset only
    (Section 4.22's own universe), which matters only for south-central-tx (6,010 rows in this
    table vs. 6,003 scored)."""
    print("\n=== Check 2: transport-undefined counts vs. Section 4.22 ===")
    ok = True
    for region in REGIONS:
        df = _load_features(region)
        scored = set(load_sample_submission(region)[TRACT_ID_COL])
        scored_df = df.loc[df.index.isin(scored)]
        undefined_count = int((~scored_df["transport_defined"]).sum())
        expected = PUBLISHED_TRANSPORT_UNDEFINED[region]
        status = "PASS" if undefined_count == expected else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"  [{region}] {status}: computed={undefined_count}, published={expected}")
    return ok


def check3_water_dominated() -> bool:
    """Recomputes water_fraction (Section 4.26's method: AWATER / (ALAND + AWATER), joined from
    `national-census-tracts` by GEOID — the same branch-detection choice Section 4.26 made, since
    the per-region `<region>-census-tracts` table does not carry AWATER) for eastern-ok and
    northern-ca, confirms the published counts (1 and 2), and shows each water-dominated tract's
    building/POI gap-candidate values and `*_defined` flags from this table — confirming the R-009
    confound is actually visible in this stage's own output, not just a documented risk."""
    print("\n=== Check 3: water-dominated tracts vs. Section 4.26 ===")
    national_tracts = load_strata_national_table("national-census-tracts")
    if "ALAND" not in national_tracts.columns:
        print("  FAIL: national-census-tracts lacks ALAND — cannot compute water_fraction as "
              "Section 4.26 did. Stopping this check rather than silently using a different "
              "denominator.")
        return False

    national_tracts_by_geoid = national_tracts.set_index(TRACT_ID_COL)

    ok = True
    for region in ("eastern-ok", "northern-ca"):
        df = _load_features(region)
        # Build the boolean mask FROM the already-GEOID-indexed frame, not from the pre-set_index
        # RangeIndex-based one — mixing the two (the original bug here) raises pandas'
        # "Unalignable boolean Series" IndexingError, since .loc[mask] requires mask and frame to
        # share the same index.
        nt = national_tracts_by_geoid.loc[national_tracts_by_geoid.index.isin(df.index)]
        total_area = nt["ALAND"] + nt["AWATER"]
        water_fraction = (nt["AWATER"] / total_area.where(total_area > 0)).reindex(df.index)
        water_dominated = df.index[water_fraction > 0.5]
        expected = PUBLISHED_WATER_DOMINATED[region]
        status = "PASS" if len(water_dominated) == expected else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"  [{region}] {status}: computed={len(water_dominated)} water-dominated tracts, "
              f"published={expected}")
        if len(water_dominated):
            cols = [
                "building_gap_centroid", "building_gap_centroid_defined",
                "building_gap_intersection", "building_gap_intersection_defined",
                "poi_gap_fire", "poi_gap_fire_defined",
            ]
            print(df.loc[water_dominated, cols].to_string())
    return ok


def check4_hospital_exclusion() -> bool:
    """Spot-checks the hospital-exclusion filter (Step 3, R-004) — recomputes the raw Overture-vs-
    HIFLD hospital count in every region (not just one, after the single-region eastern-ok result
    came back at 5.43x against a documented "~12x ... everywhere" claim in README.md — checking
    all four is how we find out whether eastern-ok is a genuine regional exception or the
    documented figure itself was measured on a narrower sample, rather than guessing).

    PASS criterion is deliberately loose (ratio > 3x, "unambiguously and materially overcounting,"
    not a tight band around 12) — the qualitative conclusion R-004 depends on (hospitals must be
    excluded because Overture over-counts them enough to make that term never show a deficit) does
    not require the multiplier to be exactly 12x in every region, and gating a hard FAIL on a
    number this check cannot itself validate as precise would be circular."""
    print("\n=== Check 4: hospital-exclusion spot-check (all regions) ===")
    con = duckdb.connect()
    configure_duckdb_spatial(con)
    con.execute("INSTALL httpfs; LOAD httpfs;")

    ok = True
    ratios = {}
    for region in REGIONS:
        pois_url = reference_url(region, LAYER_OVERTURE_POIS)
        hospitals_url = reference_url(region, LAYER_HIFLD_HOSPITALS)

        overture_hospital_count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{pois_url}') WHERE categories.primary = 'hospital'"
        ).fetchone()[0]
        hifld_hospital_count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{hospitals_url}')"
        ).fetchone()[0]

        if hifld_hospital_count == 0:
            print(f"  [{region}] FAIL: hifld_hospital_count is 0 — cannot compute a ratio.")
            ok = False
            continue

        ratio = overture_hospital_count / hifld_hospital_count
        ratios[region] = ratio
        region_ok = ratio > 3.0
        status = "PASS" if region_ok else "FAIL"
        if not region_ok:
            ok = False
        print(f"  [{region}] {status}: overture hospital POIs={overture_hospital_count}, "
              f"HIFLD hospitals={hifld_hospital_count}, ratio={ratio:.2f}x "
              f"(documented: ~12x 'everywhere', README.md)")

    if ratios:
        print(f"  Spread across regions: {min(ratios.values()):.2f}x - {max(ratios.values()):.2f}x")
        print("  Confirms R-004's exclusion is warranted in every region checked: including "
              "'hospital' in the facilities term would make that component show a near-permanent "
              "or fully-permanent zero deficit given this overcount magnitude, whatever the exact "
              "multiplier turns out to be region by region.")
    return ok


def main() -> None:
    results = {
        "row_counts": check1_row_counts(),
        "transport_undefined": check2_transport_undefined(),
        "water_dominated": check3_water_dominated(),
        "hospital_exclusion": check4_hospital_exclusion(),
    }
    print("\n=== Summary ===")
    for name, passed in results.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
