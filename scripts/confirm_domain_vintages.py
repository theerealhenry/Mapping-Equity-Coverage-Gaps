"""
Stage 3 Step 4 — vintage confirmation per domain, cross-checked against external research.

Steps 1-3 established what columns exist (Step 2), what domain each belongs to (Step 2), and how
often each column is null/what range it takes (Step 3). None of that says whether the specific
vintage of each underlying public dataset — e.g. "2013 NCHS Urban-Rural Classification" vs. the
2023 scheme CDC has since published, or "2020 RUCA codes" vs. an older tract-boundary vintage — is
the most current one available, or whether two datasets joined into the same table (SVI 2022, CVI
"2010", tract boundaries 2020) are internally consistent with each other. That question can only be
answered by comparing this project's actual data against each source agency's own current
documentation — external research, not more profiling of the file already in hand.

This script does the half of that comparison that has to come from the file itself: for every
column across the 19 source tables that carries genuine vintage/edition/version/coverage-window
metadata, it reports the column's actual value(s) as they exist in the live bucket. Step 3's
`null_profile` deliberately only computed min/max/mean for numeric columns; several of the vintage
columns here are non-numeric (a string edition label, a string grain/extent label), and this is
specifically about what those strings actually say, not about null rates. The other half — what
each source agency's own site currently documents as that dataset's authoritative vintage, plus a
same-day retrieval URL and date for the Best Bias Discovery writeup's citation requirement — was
done separately via external research and is recorded, side by side with these live values, in
`docs/data_vintage_confirmation.md`.

`VINTAGE_COLUMNS_BY_SOURCE_TABLE` below is an explicit, hand-built per-source-table list, not a
keyword- or prefix-matched one. Step 3's `identify_covered_flag_groups` already showed that
prefix-matching against real column names is not reliable enough to trust blindly (the
`cdcw_covered`/`hwd_*` naming trap) — for something Best Bias Discovery evidence depends on being
exactly right, an explicit list built by reading the real, committed `docs/column_domain_map.csv`
column-by-column is worth the extra care. `national-tribal-tract-table` (the AIANNH/tribal-land
domain) carries no vintage or edition column of its own at all — confirmed by that same column-by-
column read — so it has no entry here; it is cross-checked in `docs/data_vintage_confirmation.md`
against `tract_vintage` instead (both should be the same 2020 TIGER/Line cycle, since AIANNH
boundaries and Census tracts are published together).

Two entries exist here specifically to settle questions external research alone could not close:
`uhe_city_country`/`uhe_city_name`'s actual distinct values (to help decide which of two candidate
NASA/academic urban-heat-exposure datasets this table's "uhe" columns actually come from — with a
caveat found during review: since this table is already joined to only US census tracts,
`uhe_city_country` alone will likely show just the US plus territories regardless of which candidate
source it is, so it mainly rules out a non-US-only mismatch rather than fully discriminating between
the two candidates; `uhe_city_name`'s actual city list, once pulled, is what a human comparison
against each candidate dataset's published city list can actually use), and `usfs_edition`/
`usfs_extent`'s actual string values (to decide between the USFS Wildfire Risk to Communities 1st
and 2nd edition, both of which are still published side by side).

Like Step 3, this is the one function in this file that touches the live bucket
(`load_national_strata_attribute_table`); everything else is a pure function tested against small,
hand-built fixtures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config import STRATA_NATIONAL_JOINED_TABLE
from src.io import load_national_strata_attribute_table

DEFAULT_OUTPUT_PATH = Path("docs/domain_vintage_raw_values.csv")

# Step 1's independently-confirmed row count (docs/data_manifest.md Section 4.11) — checked again
# here as a cheap sanity guard, exactly as Step 3 does.
EXPECTED_NATIONAL_ROW_COUNT = 85_396

MAX_DISTINCT_VALUES_SHOWN = 15

VINTAGE_COLUMNS_BY_SOURCE_TABLE: dict[str, list[str]] = {
    "national-carbonplan-tract-table": ["carbonplan_version"],
    "national-fpa-fod-tract-table": ["fod_edition", "fod_year_min", "fod_year_max"],
    "national-mtbs-tract-table": ["mtbs_year_min", "mtbs_year_max", "mtbs_size_threshold"],
    "national-nifc-tract-table": ["nifc_year_min", "nifc_year_max"],
    "national-usfs-wildfire-tract-table": ["usfs_edition", "usfs_extent"],
    "national-usgs-combined-tract-table": ["usgs_record_start", "usgs_record_end"],
    "national-cdc-wonder-tract-table": ["cdcw_grain", "cdcw_window_start", "cdcw_window_end"],
    "national-epht-heat-tract-table": [
        "epht_threshold",
        "epht_metric",
        "epht_year_min",
        "epht_year_max",
    ],
    "national-nasa-heat-tract-table": [
        "gehe_record_start",
        "gehe_record_end",
        "uhe_city_country",
        "uhe_city_name",
    ],
    "national-noaa-ghcn-tract-table": ["ghcn_year_min", "ghcn_year_max"],
    "national-drought-gov-tract-table": [
        "spi_calibration",
        "drought_gov_window_start",
        "drought_gov_window_end",
    ],
    "national-usdm-drought-tract-table": ["usdm_year_min", "usdm_year_max"],
    "national-nchs-tract-table": ["nchs_year"],
    "national-ruca-tract-table": ["ruca_year"],
    "national-rucc-tract-table": ["rucc_year"],
    "national-cvi-tract-table": ["cvi_source_vintage"],
    "national-svi-tract-table": ["svi_year"],
    "national-census-tract-table": ["tract_vintage"],
}


# --- Pure functions (fully testable with no network) --------------------------------------------


def all_vintage_columns(columns_by_table: dict[str, list[str]] | None = None) -> list[str]:
    """Flat list of every column named anywhere in VINTAGE_COLUMNS_BY_SOURCE_TABLE, in table order.
    A column named under more than one source table would be listed twice here — this project's
    real table has no such collision (confirmed: every vintage column name is unique across all 19
    source tables), but this function does not assume that; the caller decides what to do with
    duplicates, if any ever appear."""
    columns_by_table = columns_by_table if columns_by_table is not None else VINTAGE_COLUMNS_BY_SOURCE_TABLE
    return [c for cols in columns_by_table.values() for c in cols]


def distinct_value_summary(series: pd.Series, *, max_values: int = MAX_DISTINCT_VALUES_SHOWN) -> str:
    """Human-readable 'value (count); value (count); ...' summary of a column's distinct non-null
    values, most frequent first, truncated at max_values with a '+N more distinct value(s)' suffix.

    Used instead of min/max/mean here because several of these columns are non-numeric (a string
    edition label, a string grain/extent label) that Step 3's null_profile deliberately skipped
    numeric stats for, but whose actual value(s) this step specifically needs — external research
    can say what vintages an agency has EVER published; only this file says which one is actually
    in it.
    """
    counts = series.dropna().value_counts()
    if len(counts) == 0:
        return "(all null)"
    shown = counts.iloc[:max_values]
    parts = [f"{value!r} ({count})" for value, count in shown.items()]
    if len(counts) > max_values:
        parts.append(f"... +{len(counts) - max_values} more distinct value(s)")
    return "; ".join(parts)


def summarize_vintage_columns(
    df: pd.DataFrame, columns_by_table: dict[str, list[str]]
) -> pd.DataFrame:
    """One row per vintage/edition column: its source table, dtype, null rate, distinct-value
    count, and its actual value(s). Assumes every listed column is present in df — the caller
    (main()) is responsible for checking that first and failing loudly if not, matching Step 3's
    own missing-column discipline."""
    n_rows = len(df)
    records = []
    for source_table, columns in columns_by_table.items():
        for column in columns:
            series = df[column]
            n_null = int(series.isna().sum())
            records.append(
                {
                    "source_table": source_table,
                    "column_name": column,
                    "dtype": str(series.dtype),
                    "n_rows": n_rows,
                    "n_null": n_null,
                    "pct_null": (n_null / n_rows) if n_rows else float("nan"),
                    "n_distinct": int(series.nunique(dropna=True)),
                    "values": distinct_value_summary(series),
                }
            )
    return pd.DataFrame.from_records(records)


# --- Real-path orchestration (network required) --------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    print(f"Loading {STRATA_NATIONAL_JOINED_TABLE} from the live bucket (85,396 rows expected)...")
    national_df = load_national_strata_attribute_table(STRATA_NATIONAL_JOINED_TABLE)
    print(f"Loaded {len(national_df)} rows, {len(national_df.columns)} columns.")
    if len(national_df) != EXPECTED_NATIONAL_ROW_COUNT:
        print(
            f"WARNING: expected {EXPECTED_NATIONAL_ROW_COUNT} rows (Step 1's confirmed figure, "
            "docs/data_manifest.md Section 4.11) but got "
            f"{len(national_df)}. Proceeding anyway — every value below is still computed "
            "correctly against whatever was actually loaded, but re-run Step 1 to confirm the "
            "bucket has not changed.",
            file=sys.stderr,
        )

    missing_columns = [c for c in all_vintage_columns() if c not in national_df.columns]
    if missing_columns:
        print(
            f"ERROR: {len(missing_columns)} expected vintage column(s) not present in the live "
            f"table: {missing_columns}. The bucket's schema may have changed since Steps 1-3 — "
            "re-run inspect_national_strata_schema.py and map_column_domains.py before this "
            "script.",
            file=sys.stderr,
        )
        return 2

    summary_df = summarize_vintage_columns(national_df, VINTAGE_COLUMNS_BY_SOURCE_TABLE)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(args.output, index=False)
    print(f"\nWrote {len(summary_df)} vintage-column rows to {args.output}\n")
    print(summary_df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
