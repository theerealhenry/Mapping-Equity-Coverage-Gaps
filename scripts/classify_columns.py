"""
Stage 3 Step 5 — role, allowed_for_scoring, and allowed_for_bias classification for every column of
`national-strata-tract-table`.

Steps 1-4 established what the 232 columns are, what domain each belongs to, how often each is null,
and (for 37 of them) what vintage/edition/methodology metadata they carry. This step answers two
different questions for every column: what KIND of thing is it structurally (its `role`), and — the
two questions that actually matter for winning this competition safely — is it allowed to influence
the number this project submits for leaderboard scoring (`allowed_for_scoring`), and is it usable as
an input to this project's own bias-discovery analysis (`allowed_for_bias`)?

**`allowed_for_scoring` is False for every single one of the 232 columns, without exception, and
this is a table-level rule, not a per-column judgment call.** It follows directly from how the
challenge's own documentation (`README.md`, the `The Dataset` project doc, and the `Evaluation`
project doc) organizes the data: `reference/` is explicitly "the map data you score" (Overture
extracts, Microsoft Building Footprints, TIGER/Line Roads, ACS housing, HIFLD facilities, County
Business Patterns), and `strata/` — which is where `national-strata-tract-table` and every column in
it lives — is explicitly the separate "Bias API strata datasets" collection (SVI, CVI, RUCA, tribal,
drought, wildfire, heat). The challenge's own rule is direct: "the scored coverage-gap computation
must use only the datasets provided for the challenge" (meaning `reference/`), and additional data —
which includes anything from `strata/`, since it plays no role in computing the coverage-gap formula
itself — is "permitted only for the Best Bias Discovery prize." Using any `strata/` column as an
input to the actual submitted coverage-gap number would not just be unnecessary, it would risk
looking like an attempt to smuggle disallowed signal into the scored computation. One clarifying
scope note: the Reference Reconstruction Engine's tract GEOMETRY (needed to spatially assign Overture
features to tracts) comes from `national-census-tracts.parquet` — a separate, geometry-only file,
not one of the 232 columns being classified here, and out of this step's scope entirely; nothing
about that file's necessity changes the `national-strata-tract-table` answer above.

**`allowed_for_bias` is the real per-column judgment, and it is derived here from two things, both
already independently confirmed by earlier steps rather than freshly guessed:** (1) a column's
`role` — a vintage/edition/methodology metadata column (Step 4) is, by construction, identical for
every one of the 85,396 tracts, and an identifier/geometry column is not itself a vulnerability or
hazard signal; and (2) a hard, data-driven override that already caught real, previously undocumented
cases while this step was being built: ANY column — regardless of role — that takes only one distinct
value across all 85,396 tracts nationally (`docs/coverage_null_profile.csv`, national scope,
`n_distinct <= 1`) cannot explain variance in anything and is forced to `allowed_for_bias=False`
regardless of what its role would otherwise suggest. This is not a new list to hand-maintain — it is
computed directly from the same real profiling data Step 3 already produced, so it can never silently
drift out of sync with the actual data the way a hand-typed exception list could.

This script needs no live bucket access at all — everything it reads
(`docs/column_domain_map.csv`, `docs/coverage_null_profile.csv`, and
`scripts.confirm_domain_vintages.VINTAGE_COLUMNS_BY_SOURCE_TABLE`) is already committed, real data
from Steps 2-4. Every function here is pure and tested against both small hand-built fixtures and
the real, committed inputs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.confirm_domain_vintages import all_vintage_columns

DEFAULT_DOMAIN_MAP_PATH = Path("docs/column_domain_map.csv")
DEFAULT_NULL_PROFILE_PATH = Path("docs/coverage_null_profile.csv")
DEFAULT_OUTPUT_PATH = Path("docs/column_classification.csv")

NATIONAL_SCOPE = "national"

# --- Explicit, hand-verified column sets (priority order matters — see classify_role) ------------
# Each set was built by reading the real, committed docs/column_domain_map.csv column-by-column,
# the same discipline Step 4 used for its vintage-column list — not inferred from domain or dtype
# alone, which Step 4 already showed is not reliable enough on its own (the cdcw_covered/hwd_* naming
# trap, and this step's own epht_metric correction to Step 4).

IDENTIFIER_COLUMNS = {"GEOID", "STATEFP", "COUNTYFP", "state_usps", "state_name"}
GEOMETRY_MEASURE_COLUMNS = {"ALAND", "AWATER", "INTPTLAT", "INTPTLON"}
POPULATION_COLUMNS = {"pop_total", "pop_urban", "pop_rural", "pct_urban", "ur_class"}
EVER_FLAG_COLUMNS = {"fod_ever", "mtbs_wildfire_ever", "nifc_wildfire_ever", "usgs_wildfire_ever"}
IDENTITY_METADATA_COLUMNS = {"aiannh_geoid", "aiannh_name", "uhe_city_name", "uhe_city_country"}

ROLE_IDENTIFIER = "identifier"
ROLE_GEOMETRY_MEASURE = "geometry_measure"
ROLE_POPULATION = "population"
ROLE_VINTAGE_METADATA = "vintage_metadata"
ROLE_COVERAGE_FLAG = "coverage_flag"
ROLE_DERIVED_EVER_FLAG = "derived_ever_flag"
ROLE_IDENTITY_METADATA = "identity_metadata"
ROLE_MEASUREMENT = "measurement"

SCORING_REASON = (
    "national-strata-tract-table lives entirely under strata/ (the Bias API stratification "
    "datasets), never under reference/ (the map data actually scored). The challenge's own rule — "
    "the scored coverage-gap computation must use only the datasets provided for the challenge — "
    "means no column from this table may influence the submitted coverage-gap number, regardless "
    "of its role."
)


# --- Pure functions (fully testable with no network) --------------------------------------------


def classify_role(column_name: str, vintage_columns: set[str]) -> str:
    """Assigns exactly one role per column, in a fixed priority order — a column is checked against
    each explicit set in turn, and the first match wins. `vintage_columns` is passed in rather than
    read from the module-level import directly so tests can exercise this against a small synthetic
    set without needing the real 36-column list.

    IDENTITY_METADATA_COLUMNS is checked BEFORE vintage_columns, and this order matters: it was
    found, while first running this script against real data, that `uhe_city_name`/
    `uhe_city_country` are members of Step 4's `VINTAGE_COLUMNS_BY_SOURCE_TABLE` — but only because
    Step 4 added them there for a different, narrower reason (to have its extraction script pull
    their live values while investigating which "uhe" dataset this table actually comes from), not
    because they are genuinely vintage/edition/methodology metadata describing the source dataset.
    Checking the explicit, purpose-built IDENTITY_METADATA_COLUMNS set first means Step 4's
    extraction-convenience list can never leak an incorrect role into this step, regardless of why a
    column ended up in it.
    """
    if column_name in IDENTIFIER_COLUMNS:
        return ROLE_IDENTIFIER
    if column_name in GEOMETRY_MEASURE_COLUMNS:
        return ROLE_GEOMETRY_MEASURE
    if column_name in POPULATION_COLUMNS:
        return ROLE_POPULATION
    if column_name in IDENTITY_METADATA_COLUMNS:
        return ROLE_IDENTITY_METADATA
    if column_name in vintage_columns:
        return ROLE_VINTAGE_METADATA
    if column_name.endswith("_covered"):
        return ROLE_COVERAGE_FLAG
    if column_name in EVER_FLAG_COLUMNS:
        return ROLE_DERIVED_EVER_FLAG
    return ROLE_MEASUREMENT


def compute_allowed_for_bias(role: str, n_distinct: int) -> tuple[bool, str]:
    """The hard override fires first, regardless of role: a column with n_distinct <= 1 nationally
    is constant across every one of the 85,396 tracts and cannot explain variance in anything,
    however plausible its role would otherwise make it sound. This is the same real-data check that
    caught rucc_covered/ghcn_covered (Step 3 Finding 4) and hwd_maxtemp_never_defined during this
    step's own build — it is a live computation here, not a hand-copied list, so it can never drift
    out of sync with whatever the real data actually says.
    """
    if n_distinct <= 1:
        return False, (
            f"constant across all tracts nationally (n_distinct={n_distinct}) — carries no "
            "discriminative signal for any bias analysis, regardless of role"
        )

    if role == ROLE_VINTAGE_METADATA:
        # Should be unreachable in practice (every vintage column is independently confirmed
        # n_distinct<=1 nationally — see tests/test_classify_columns.py's real-data regression) but
        # not assumed: if a future vintage column ever DID vary, it would still not belong in a
        # per-tract bias analysis, since it describes the source dataset's own methodology, not the
        # tract.
        return False, "vintage/edition/methodology metadata describes the source dataset, not the tract"
    if role == ROLE_IDENTIFIER:
        return False, "a join/reference key, not itself a vulnerability or hazard signal"
    if role == ROLE_GEOMETRY_MEASURE:
        return True, "tract land area/water area/centroid — usable as a rurality/isolation proxy or for spatial statistics (Moran's I, Getis-Ord Gi*)"
    if role == ROLE_POPULATION:
        return True, "base population/urban-rural figures — directly needed for population-weighting critiques of any tract-mean disparity statistic"
    if role == ROLE_COVERAGE_FLAG:
        return True, "central to Measurement Eligibility Bias analysis (whether a hazard/vulnerability measurement exists for a tract at all, cross-tabulated against SVI/tribal/rurality/hazard exposure)"
    if role == ROLE_DERIVED_EVER_FLAG:
        return True, (
            "real per-tract signal, but MUST be interpreted jointly with its own _covered flag — "
            "Step 3 Finding 2 documented that this defaults to False for uncovered tracts rather "
            "than propagating unknown-ness, which risks misreading 'no data' as 'no history' if "
            "used alone"
        )
    if role == ROLE_IDENTITY_METADATA:
        return True, "descriptive/provenance label (which external entity a tract was matched to or overlaps), usable for named-instance or coarse-grouping bias analysis, not for anything for which its own cardinality can't support meaningful stratification"
    # ROLE_MEASUREMENT
    return True, "a substantive per-tract measurement with real variance nationally"


def build_classification(
    domain_map: pd.DataFrame, national_profile: pd.DataFrame, vintage_columns: set[str]
) -> pd.DataFrame:
    """One row per column in domain_map: its role, allowed_for_scoring (always False, see module
    docstring), and allowed_for_bias with its reason. Assumes every domain_map column is present in
    national_profile — the caller (main()) is responsible for checking that and failing loudly if
    not, matching every previous step's own missing-column discipline."""
    n_distinct_by_column = dict(zip(national_profile["column_name"], national_profile["n_distinct"]))

    records = []
    for _, row in domain_map.iterrows():
        column = row["column_name"]
        role = classify_role(column, vintage_columns)
        n_distinct = int(n_distinct_by_column[column])
        allowed_for_bias, bias_reason = compute_allowed_for_bias(role, n_distinct)
        records.append(
            {
                "column_name": column,
                "source_table": row["source_table"],
                "domain": row["domain"],
                "dtype": row["dtype"],
                "role": role,
                "n_distinct_national": n_distinct,
                "allowed_for_scoring": False,
                "scoring_reason": SCORING_REASON,
                "allowed_for_bias": allowed_for_bias,
                "bias_reason": bias_reason,
            }
        )
    return pd.DataFrame.from_records(records)


# --- Real-path orchestration (no network needed — every input is already committed) --------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain-map", type=Path, default=DEFAULT_DOMAIN_MAP_PATH)
    parser.add_argument("--null-profile", type=Path, default=DEFAULT_NULL_PROFILE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    try:
        domain_map = pd.read_csv(args.domain_map)
    except FileNotFoundError:
        print(f"ERROR: {args.domain_map} not found. Run scripts/map_column_domains.py first (Stage 3 Step 2).", file=sys.stderr)
        return 2

    try:
        profile = pd.read_csv(args.null_profile)
    except FileNotFoundError:
        print(
            f"ERROR: {args.null_profile} not found. Run scripts/profile_coverage_and_nulls.py first "
            "(Stage 3 Step 3) — this step needs its real n_distinct figures.",
            file=sys.stderr,
        )
        return 2

    national_profile = profile.loc[profile["scope"] == NATIONAL_SCOPE]
    if len(national_profile) == 0:
        print(f"ERROR: {args.null_profile} has no rows for scope={NATIONAL_SCOPE!r}.", file=sys.stderr)
        return 2

    missing_columns = set(domain_map["column_name"]) - set(national_profile["column_name"])
    if missing_columns:
        print(
            f"ERROR: {len(missing_columns)} column(s) in {args.domain_map} have no national-scope "
            f"row in {args.null_profile}: {sorted(missing_columns)}. Re-run Step 3 before this step.",
            file=sys.stderr,
        )
        return 2

    vintage_columns = set(all_vintage_columns())
    classification = build_classification(domain_map, national_profile, vintage_columns)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    classification.to_csv(args.output, index=False)
    print(f"Wrote {len(classification)} column classifications to {args.output}\n")

    print("Role counts:")
    print(classification["role"].value_counts().to_string())

    n_scoring_true = int(classification["allowed_for_scoring"].sum())
    print(f"\nallowed_for_scoring=True: {n_scoring_true} of {len(classification)} (must always be 0)")

    n_bias_false = classification.loc[~classification["allowed_for_bias"]]
    print(f"\nallowed_for_bias=False: {len(n_bias_false)} of {len(classification)} columns:")
    print(n_bias_false[["column_name", "role", "bias_reason"]].to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
