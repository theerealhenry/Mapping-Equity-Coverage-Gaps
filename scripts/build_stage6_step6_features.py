"""
scripts/build_stage6_step6_features.py — Stage 6, Step 6: assemble Steps 3-5's output into
data/processed/<region>-tract-features.parquet, one per region, GEOID-indexed.

Combines, per region:
  - Step 3's raw ingredients + candidate capped-ratio gap values (data/processed/<region>-
    step3-ingredients.parquet — already built, one file per region, Phase 1+2 confirmed).
  - Step 4's strata join (src.features.join_strata_features against the national strata table).
  - Step 5's derived columns that are actually computable from Step 3 + Step 4 alone:
    dispatch_blind_reachability, component_dominance_and_definedness, attach_region.

Deliberately does NOT include `confidence_reporting_rate`/`mean_reported_confidence`,
`source_provenance_vector`'s columns, or `distance_to_tract_boundary_m` — their raw per-record
inputs (per-record confidence values, per-record source-dataset strings, facility point
geometries) are not gathered anywhere yet; Step 3's ingredients script only ever aggregates to
per-tract COUNTS/LENGTHS, never per-tract LISTS of raw record-level values. Building that raw-list
ingredient gathering is new scope beyond what Step 6 asked for and is called out here rather than
silently faked with placeholder columns — see TRACT_FEATURES_SCHEMA's comment in src/schemas.py
for the same note. `population_weighted_gap_stats` is also excluded from the table on purpose: it
is a region-level diagnostic STATISTIC, not a per-tract feature column (printed to stdout instead,
below).

Does NOT filter any tract for any reason (including the 3 water-dominated tracts from Section
4.26) — Step 9 is where that check happens, this step must not pre-empt it.

Run per region:
    python -m scripts.build_stage6_step6_features maricopa-az
    python -m scripts.build_stage6_step6_features northern-ca
    python -m scripts.build_stage6_step6_features eastern-ok
    python -m scripts.build_stage6_step6_features south-central-tx
"""

from __future__ import annotations

import os
import sys

import pandas as pd

from src.config import SCORED_TRACT_COUNTS, STRATA_NATIONAL_JOINED_TABLE
from src.features import (
    attach_region,
    component_dominance_and_definedness,
    dispatch_blind_reachability,
    join_strata_features,
    population_weighted_gap_stats,
)
from src.io import load_national_strata_attribute_table
from src.schemas import TRACT_FEATURES_LAYER, validate_layer

TRACT_ID_COL = "GEOID"

# gap column -> its raw `*_defined` column name in the step3-ingredients file (naming isn't
# uniform there — "transport_gap"'s flag is "transport_defined", not "transport_gap_defined" —
# see build_stage6_step3_ingredients.py's build_candidate_gaps).
_GAP_TO_DEFINED_COL = {
    "transport_gap": "transport_defined",
    "building_gap_centroid": "building_gap_centroid_defined",
    "building_gap_intersection": "building_gap_intersection_defined",
    "poi_gap_fire": "poi_gap_fire_defined",
    "poi_gap_ems": "poi_gap_ems_defined",
    "poi_gap_schools": "poi_gap_schools_defined",
    "poi_gap_establishments": "poi_gap_establishments_defined",
}


def main(region: str) -> None:
    ingredients_path = f"data/processed/{region}-step3-ingredients.parquet"
    print(f"[{region}] loading {ingredients_path}...", flush=True)
    ingredients = pd.read_parquet(ingredients_path).set_index(TRACT_ID_COL)

    print(f"[{region}] loading national strata table + joining Step 4 columns...", flush=True)
    national_strata = load_national_strata_attribute_table(STRATA_NATIONAL_JOINED_TABLE)
    strata = join_strata_features(national_strata, ingredients.index)

    print(f"[{region}] Step 5: dispatch-blind reachability + component dominance...", flush=True)
    # "dispatch" = fire/EMS reaching a tract, not schools — see dispatch_blind_reachability's
    # docstring for why schools are excluded from this combination.
    poi_gap_dispatch = ingredients[["poi_gap_fire", "poi_gap_ems"]].mean(axis=1, skipna=True)
    dispatch = dispatch_blind_reachability(ingredients["transport_gap"], poi_gap_dispatch)

    gap_cols = list(_GAP_TO_DEFINED_COL)
    defined_flags = pd.DataFrame(
        {f"{gap}_defined": ingredients[flag_col] for gap, flag_col in _GAP_TO_DEFINED_COL.items()}
    )
    dominance = component_dominance_and_definedness(ingredients[gap_cols], defined_flags)

    result = pd.concat([ingredients, strata, dispatch, dominance], axis=1)
    result = attach_region(result, region)
    result.index.name = TRACT_ID_COL
    result = result.reset_index()

    print(f"[{region}] validating against TRACT_FEATURES_SCHEMA...", flush=True)
    result = validate_layer(result, TRACT_FEATURES_LAYER)

    out_path = f"data/processed/{region}-tract-features.parquet"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result.to_parquet(out_path, index=False)

    # --- Step 6 verification numbers ---
    expected = SCORED_TRACT_COUNTS[region]
    print(f"row count: {len(result)} (expected {expected})")
    print(f"schema validation: PASS ({len(result.columns)} columns)")
    for gap_col in gap_cols:
        pw = population_weighted_gap_stats(result[gap_col], result["pop_total"])
        print(f"  population-weighted {gap_col}: mean={pw['pop_weighted_mean']}, n={pw['n_tracts_used']}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m scripts.build_stage6_step6_features <region>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
