"""
Stage 3 Step 2 — column-to-domain mapping for the national strata joined table.

Purpose: for every one of the 232 columns in `national-strata-tract-table` (the joined table this
project's bias analysis is scored against), determine (a) which single source table it truly
derives from and (b) which analytical domain it belongs to (population, SVI, CVI, rurality, heat,
wildfire, drought, tribal, or the geography/identifier columns the blueprint's domain list does not
name but that genuinely exist). This is the skeleton every later Stage 3 step builds on: Step 3
profiles coverage/nulls per domain, Step 5 assigns role/allowed_for_scoring/allowed_for_bias, Step 6
tags candidate_hypotheses — all of that groups columns by the domain assigned here.

Deliberately operates entirely offline against `docs/national_strata_schema_raw.csv`, the artifact
Stage 3 Step 1 already committed to this repository. No bucket access, no network, is needed to run
this script or its tests — the schema facts it needs were already confirmed against the live bucket
in Step 1, and re-deriving them from the same live data a second time would just be redundant
network I/O for zero new information. If the bucket's national strata tables are ever refreshed,
re-run `inspect_national_strata_schema.py` first (Step 1) and then this script, in that order.

Source-table attribution logic (established directly in Step 1, see `docs/data_manifest.md` Section
4.11 — not re-derived here, only applied): of the joined table's 232 columns, 223 have a name that
appears in exactly one of the 25 source tables and are attributed to that table directly. The
remaining 9 are shared join-key/geography fields (`GEOID`, `STATEFP`, `ALAND`, `AWATER`,
`INTPTLAT`, `INTPTLON`, `COUNTYFP`, `state_usps`, `tract_vintage`) that appear, by name, in many
source tables — these are all attributed to `national-census-tract-table`, the only source table
that carries all nine together and is therefore the join's backbone/spine table.

Domain classification logic: most source tables map to exactly one domain by their evident content
(confirmed by reading their real column names, not guessed from the table name alone — this
surfaced one real naming trap, documented in `TABLE_DOMAIN`'s comments, worth restating here:
`national-carbonplan-tract-table`'s name suggests a carbon/emissions dataset, but its actual columns
(`carbonplan_bp_*` = burn probability, `carbonplan_crps_*`/`carbonplan_rps_*` = conditional/rate of
spread) are CarbonPlan's wildfire-risk-projection product — it is classified `wildfire`, not
`heat`). One table, `national-census-tract-table`, genuinely spans two domains at the column level:
its nine backbone/identifier columns (see above) carry no analytical signal about any hazard or
vulnerability axis and are classified `geography`, a ninth bucket added deliberately alongside the
blueprint's eight named domains (population, SVI, CVI, rurality, heat, wildfire, drought, tribal)
because identifier columns are a real, distinct category that the blueprint's domain list does not
itself name; its five population columns (`pop_total`, `pop_urban`, `pop_rural`, `pct_urban`,
`ur_class`) are classified `population`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

DEFAULT_SCHEMA_CSV_PATH = Path("docs/national_strata_schema_raw.csv")
DEFAULT_OUTPUT_PATH = Path("docs/column_domain_map.csv")

JOINED_TABLE = "national-strata-tract-table"

# The nine shared join-key/geography columns established in Step 1 (docs/data_manifest.md Section
# 4.11) — every one of these appears, by exact name, in many of the 25 source tables, but only
# national-census-tract-table carries all nine together, so all nine are attributed to it rather
# than left as a genuinely ambiguous multi-table match.
SHARED_BACKBONE_COLUMNS = frozenset(
    {
        "GEOID",
        "STATEFP",
        "ALAND",
        "AWATER",
        "INTPTLAT",
        "INTPTLON",
        "COUNTYFP",
        "state_usps",
        "tract_vintage",
    }
)
BACKBONE_SOURCE_TABLE = "national-census-tract-table"

# One domain per source table under strata/national/, confirmed by reading each table's real
# column names (docs/national_strata_schema_raw.csv), not guessed from the table's filename.
# Includes the 4 tables that are NOT part of the 232-column join (national-cdc-wonder-heat-
# mortality, national-census-aiannh, national-census-tribal-subdivisions,
# national-census-tribal-tracts) and national-noaa-ghcn-stations and national-census-tracts, so
# every one of the 26 tables inspected in Step 1 gets a domain entry in the full dictionary later,
# not only the 25 that feed the join.
TABLE_DOMAIN = {
    # Vulnerability-index domains
    "national-svi-tract-table": "svi",
    "national-cvi-tract-table": "cvi",
    # Rurality/urbanicity domain
    "national-ruca-tract-table": "rurality",
    "national-rucc-tract-table": "rurality",
    "national-nchs-tract-table": "rurality",
    # Tribal domain
    "national-tribal-tract-table": "tribal",
    "national-census-aiannh": "tribal",  # parquet-only boundary file, not joined
    "national-census-tribal-subdivisions": "tribal",  # parquet-only boundary file, not joined
    "national-census-tribal-tracts": "tribal",  # parquet-only boundary file, not joined
    # Drought domain
    "national-usdm-drought-tract-table": "drought",
    "national-drought-gov-tract-table": "drought",
    # Wildfire domain — includes national-carbonplan-tract-table: its name suggests carbon/
    # emissions, but its real columns (burn probability, conditional/rate of spread) are a
    # wildfire-risk projection product. See module docstring.
    "national-usfs-wildfire-tract-table": "wildfire",
    "national-usgs-combined-tract-table": "wildfire",
    "national-mtbs-tract-table": "wildfire",
    "national-nifc-tract-table": "wildfire",
    "national-fpa-fod-tract-table": "wildfire",
    "national-carbonplan-tract-table": "wildfire",
    # Heat domain
    "national-epht-heat-tract-table": "heat",
    "national-cdc-wonder-tract-table": "heat",
    "national-cdc-wonder-heat-mortality": "heat",  # national-only reference table, not joined
    "national-nasa-heat-tract-table": "heat",
    "national-noaa-ghcn-tract-table": "heat",
    "national-noaa-ghcn-stations": "heat",  # station-indexed source file, not joined
    # Geography backbone table — column-level split, see CENSUS_TRACT_TABLE_POPULATION_COLUMNS
    # below; every other column of this table not in that set is classified "geography".
    "national-census-tract-table": "geography",
    "national-census-tracts": "geography",  # boundary/geometry duplicate-ish file, not joined
}

# The five columns of national-census-tract-table that carry real population signal rather than
# a bare geographic identifier — classified "population", overriding the table-level "geography"
# default above. Confirmed against the table's real 19-column schema (Step 1 output): the other 14
# columns (GEOID, STATEFP, COUNTYFP, TRACTCE, NAMELSAD, state_usps, state_name, ALAND, AWATER,
# INTPTLAT, INTPTLON, tract_vintage, tiger_year, dhc_year) are identifiers, boundary geometry
# descriptors, or vintage metadata — none of them measure population.
CENSUS_TRACT_TABLE_POPULATION_COLUMNS = frozenset(
    {"pop_total", "pop_urban", "pop_rural", "pct_urban", "ur_class"}
)

# The full domain vocabulary this project uses, for a single validation point against typos in the
# TABLE_DOMAIN dict above and any column-level override.
VALID_DOMAINS = frozenset(
    {
        "geography",
        "population",
        "svi",
        "cvi",
        "rurality",
        "heat",
        "wildfire",
        "drought",
        "tribal",
    }
)


def load_schema_csv(path: Path = DEFAULT_SCHEMA_CSV_PATH) -> pd.DataFrame:
    """Load Step 1's committed schema-inspection output. Pure I/O, no transformation."""
    return pd.read_csv(path)


def attribute_source_table(joined_column: str, non_joined_rows: pd.DataFrame) -> tuple[str, str]:
    """Return (source_table, method) for one column of the joined table.

    `non_joined_rows` must already exclude JOINED_TABLE's own rows (callers pass the same filtered
    frame for every column rather than re-filtering per call, since this runs once per joined
    column — 232 times — and re-filtering the full ~1,269-row frame each time is wasted, avoidable
    work at this scale).

    method is one of:
    - "shared-backbone": one of the 9 known shared key/geography columns, attributed to
      BACKBONE_SOURCE_TABLE regardless of how many source tables actually carry that name.
    - "unambiguous": the column name appears in exactly one source table.
    - "AMBIGUOUS": the column name appears in more than one source table and is not a known shared
      backbone column — this should never happen given Step 1's findings (only the 9 backbone
      columns were found to be multiply-attributed), so a caller seeing this for a real bucket
      schema should treat it as a signal the underlying data changed since Step 1 and Step 1 should
      be re-run, not silently resolved.
    - "NOT_FOUND": the column name does not appear in any source table at all — should also never
      happen (Step 1 already confirmed all 232 joined columns trace to some source table); kept as
      an explicit, loud sentinel rather than raising, so a single bad row does not abort the whole
      report.
    """
    if joined_column in SHARED_BACKBONE_COLUMNS:
        return BACKBONE_SOURCE_TABLE, "shared-backbone"

    matches = non_joined_rows.loc[
        non_joined_rows["column_name"] == joined_column, "source_table"
    ].unique()

    if len(matches) == 0:
        return "<none>", "NOT_FOUND"
    if len(matches) == 1:
        return str(matches[0]), "unambiguous"
    return "|".join(sorted(str(m) for m in matches)), "AMBIGUOUS"


def classify_domain(column: str, source_table: str) -> str:
    """Return the domain for one column, given its attributed source table.

    Column-level override takes precedence over the table-level default — currently the only
    override is national-census-tract-table's five population columns (see
    CENSUS_TRACT_TABLE_POPULATION_COLUMNS). Returns the literal string "UNCLASSIFIED" for a source
    table with no entry in TABLE_DOMAIN, rather than raising, so a report can be built and the gap
    surfaced explicitly (see build_domain_map's unclassified-count check) instead of the whole run
    aborting on the first unmapped table.
    """
    if source_table == BACKBONE_SOURCE_TABLE and column in CENSUS_TRACT_TABLE_POPULATION_COLUMNS:
        return "population"
    return TABLE_DOMAIN.get(source_table, "UNCLASSIFIED")


def build_domain_map(schema_df: pd.DataFrame) -> pd.DataFrame:
    """Build the full column-to-domain map for the joined table's 232 columns.

    Returns one row per joined column: column_name, dtype, source_table, attribution_method,
    domain, position (the joined table's own column order, preserved so the output CSV reads in
    the same order the real table's columns appear in — useful when a reviewer cross-references it
    against the joined parquet file directly).
    """
    joined_rows = schema_df.loc[schema_df["source_table"] == JOINED_TABLE].sort_values("position")
    non_joined_rows = schema_df.loc[schema_df["source_table"] != JOINED_TABLE]

    records = []
    for _, row in joined_rows.iterrows():
        column = row["column_name"]
        source_table, method = attribute_source_table(column, non_joined_rows)
        domain = classify_domain(column, source_table)
        records.append(
            {
                "column_name": column,
                "dtype": row["arrow_dtype"],
                "source_table": source_table,
                "attribution_method": method,
                "domain": domain,
                "position": row["position"],
            }
        )

    return pd.DataFrame.from_records(
        records,
        columns=["column_name", "dtype", "source_table", "attribution_method", "domain", "position"],
    )


def domain_summary(domain_map: pd.DataFrame) -> pd.Series:
    """Column count per domain, most populous first — the headline table worth eyeballing after
    every run."""
    return domain_map["domain"].value_counts()


def find_unresolved(domain_map: pd.DataFrame) -> pd.DataFrame:
    """Rows needing manual attention: an attribution method other than the two expected clean
    outcomes, an unclassified domain, or an invalid domain string not in VALID_DOMAINS (a typo
    guard against TABLE_DOMAIN). Empty on a clean run — anything returned here must be resolved
    before Stage 3 Step 2 can be considered closed."""
    bad_attribution = ~domain_map["attribution_method"].isin(["unambiguous", "shared-backbone"])
    bad_domain = ~domain_map["domain"].isin(VALID_DOMAINS)
    return domain_map.loc[bad_attribution | bad_domain]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema-csv", type=Path, default=DEFAULT_SCHEMA_CSV_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    try:
        schema_df = load_schema_csv(args.schema_csv)
    except FileNotFoundError:
        print(
            f"ERROR: {args.schema_csv} not found. This script reads Stage 3 Step 1's committed "
            "output — run `python scripts/inspect_national_strata_schema.py` first (from the repo "
            "root, or pass --schema-csv pointing at the file directly).",
            file=sys.stderr,
        )
        return 2

    domain_map = build_domain_map(schema_df)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    domain_map.to_csv(args.output, index=False)

    print(f"Wrote {len(domain_map)} column-to-domain rows to {args.output}")
    print()
    print("Domain counts:")
    print(domain_summary(domain_map).to_string())

    unresolved = find_unresolved(domain_map)
    if len(unresolved) > 0:
        print()
        print(f"UNRESOLVED — {len(unresolved)} column(s) need manual attention:")
        print(unresolved.to_string(index=False))
        return 1

    print()
    print(f"All {len(domain_map)} columns cleanly attributed and classified. Step 2 complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
