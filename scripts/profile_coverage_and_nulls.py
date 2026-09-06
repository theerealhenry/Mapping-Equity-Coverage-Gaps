"""
Stage 3 Step 3 — coverage and null-semantics profiling per domain, per study region, against real
row-level data.

Steps 1 and 2 worked entirely from schema (column names, dtypes, source-table attribution) with no
row-level data at all. This step is the first in Stage 3 that reads actual values: for every one of
the 232 columns in `national-strata-tract-table`, and separately for the national scope and each of
the four study regions, it computes how often the column is null, how many distinct values it takes,
and (for numeric columns) its basic range — then cross-checks that against the column's own
"_covered" flag where one exists, to tell genuine "no data available for this tract" nulls apart
from any other null pattern that flag doesn't explain.

Regions are scoped by each region's `reference/<region>/<region>-sample-submission.csv` GEOID list
(`src.io.load_sample_submission`), never by the raw national row count — this is the load-bearing
rule established in Stage 2 (`docs/data_manifest.md` Section 4.8/4.9): South-Central Texas's package
ships 6,010 tracts but only 6,003 are scored, and a join against the wrong list would silently
include seven tracts nothing downstream should ever score.

Loads the full joined table via `src.io.load_national_strata_attribute_table` — the flat-table
loader added in this same step after discovering `load_strata_national_table` (the pre-existing
geometry-only loader) cannot read this table at all (see `src/io.py`'s module docstring, "Two
distinct national strata loaders"). This is the one step in Stage 3 that genuinely needs live bucket
access — Steps 1 and 2 worked from already-committed schema artifacts, but no local fixture can
substitute for the real table's actual values here. Every pure function below is still fully tested
against small, hand-built fixtures with no network access; only `main()`'s two load calls touch the
real bucket, exactly the same testable-core / thin-real-path-wrapper split used throughout this
project.

Covered-flag grouping (`identify_covered_flag_groups`): 19 of `national-strata-tract-table`'s 232
columns are boolean `<prefix>_covered` flags. For a source table with exactly one such flag, every
other column from that same source table is treated as belonging to it. Two source tables carry TWO
covered flags each (`national-nasa-heat-tract-table`: `gehe_covered`/`uhe_covered`;
`national-drought-gov-tract-table`: `pmdi_covered`/`spi_covered`) — for those, membership is decided
by which flag's own name-prefix a column starts with (`gehe_*` vs `uhe_*`, `pmdi_*` vs `spi*` —
deliberately without a trailing underscore on the `spi` side, since `spi03_mean`/`spi12_mean` do not
carry the literal substring `spi_`). One real naming trap this surfaced: `national-cdc-wonder-tract-
table`'s single flag is named `cdcw_covered`, but every one of its actual measurement columns is
named `hwd_*` (heat/weather-data trend columns), not `cdcw_*` — a prefix-only matching rule would
have wrongly assigned `cdcw_covered` a near-empty group of 3 metadata columns and left all 15 real
`hwd_*` measurement columns unchecked. The single-flag-table branch (whole table minus the flag,
used whenever a table has exactly one covered flag) avoids this entirely by not depending on the
flag's own name matching its measurements' names — it only depends on flag columns being correctly
grouped by `source_table`, an attribution already independently confirmed in Step 2.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import REGIONS, STRATA_KEY_COLUMN, STRATA_NATIONAL_JOINED_TABLE
from src.io import load_national_strata_attribute_table, load_sample_submission

DEFAULT_DOMAIN_MAP_PATH = Path("docs/column_domain_map.csv")
DEFAULT_PROFILE_OUTPUT_PATH = Path("docs/coverage_null_profile.csv")
DEFAULT_DOMAIN_SUMMARY_OUTPUT_PATH = Path("docs/coverage_null_domain_region_summary.csv")
DEFAULT_FLAG_CONSISTENCY_OUTPUT_PATH = Path("docs/covered_flag_consistency.csv")

NATIONAL_SCOPE = "national"

# Explicit column order/name for the flag-consistency report — passed to pd.DataFrame.from_records
# so an empty `consistency_records` list (identify_covered_flag_groups found zero "_covered"
# columns, which never happens against the real, committed 232-column domain map but is not
# guaranteed against an arbitrary --domain-map) still produces a DataFrame with these columns
# rather than one with none at all. Without this, `main()`'s later `consistency_df["n_covered_..."]`
# filter would raise KeyError on a columnless empty frame instead of simply finding zero exceptions.
_FLAG_CONSISTENCY_COLUMNS = [
    "scope",
    "flag_column",
    "n_member_columns",
    "n_covered_true",
    "n_covered_false",
    "n_covered_true_but_all_members_null",
    "n_covered_false_but_some_member_non_null",
]

# Step 1's independently-confirmed row count for the joined table (docs/data_manifest.md Section
# 4.11) — checked again here as a cheap, loud sanity guard, not re-derived: if this ever mismatches,
# every downstream null-rate figure in this run is still computed correctly against whatever was
# actually loaded, but it's a strong signal Step 1 should be re-run before trusting Step 3's numbers.
EXPECTED_NATIONAL_ROW_COUNT = 85_396

# Numeric sentinel values worth flagging when they appear as a column's minimum alongside real
# nulls elsewhere — the pattern Stage 2 already found once for real (Microsoft buildings'
# confidence == -1.0 placeholder, docs/data_manifest.md Section 4.8). A column hitting one of these
# exactly, in more than a token number of rows, is worth a human look before Step 5 decides its
# null_semantics — it is a candidate for "coded missing", not proof of it. Includes both negative
# placeholders (the documented Microsoft-buildings pattern) and large positive ones (9999/99999 are
# a common coded-missing convention for year- or percentage-shaped columns, several of which exist
# in this joined table, e.g. svi_year, ruca_year, tribal_pct). Each value listed once as a float —
# `series == -1` and `series == -1.0` match identically regardless of the series' own int/float
# dtype, so listing both forms here would only ever produce a duplicate, confusing report of the
# same finding under two different labels.
SENTINEL_CANDIDATES = (-1.0, -999.0, -9999.0, 9999.0, 99999.0)
SENTINEL_MIN_SHARE = 0.01  # a sentinel occupying < 1% of rows is more likely a genuine value


# --- Pure functions (fully testable with no network) --------------------------------------------


def filter_to_geoids(df: pd.DataFrame, geoids: set[str]) -> pd.DataFrame:
    """Restrict df to rows whose GEOID is in the given set. Pure, no I/O — the region-scoping rule
    itself (which GEOID list to use) is applied by the caller; this just does the filter."""
    return df.loc[df[STRATA_KEY_COLUMN].isin(geoids)]


def identify_covered_flag_groups(domain_map: pd.DataFrame) -> dict[str, list[str]]:
    """Return {covered_flag_column: [member_column, ...]} for every `<prefix>_covered` boolean
    column in the joined table. See the module docstring for the two-branch algorithm (whole-table
    for a source table with exactly one flag; prefix-match for the two tables with more than one)
    and the `cdcw_covered`/`hwd_*` naming trap it was specifically designed around.

    Columns belonging to a source table with more than one covered flag that match none of that
    table's flags' prefixes (table-level metadata, e.g. a shared vintage window) are simply absent
    from every group's member list — not an error, not silently mis-assigned to the nearest flag.

    Every OTHER flag column in the same table is always excluded from a given flag's own member
    list, even in the multi-flag branch where a naive "exclude just this one flag" rule could
    otherwise let one flag's name get swallowed into another's group as if it were an ordinary
    measurement column (this would only happen if one flag's own `<prefix>_covered` name happened
    to start with a second flag's prefix — not the case for any of the 19 real flags today, but not
    something this function should silently get wrong if a future table's naming ever did collide
    that way).
    """
    covered = domain_map.loc[domain_map["column_name"].str.endswith("_covered")]
    flags_by_table = covered.groupby("source_table")["column_name"].apply(list).to_dict()

    groups: dict[str, list[str]] = {}
    for source_table, flag_cols in flags_by_table.items():
        table_columns = domain_map.loc[
            domain_map["source_table"] == source_table, "column_name"
        ].tolist()
        flag_cols_set = set(flag_cols)
        if len(flag_cols) == 1:
            flag = flag_cols[0]
            groups[flag] = [c for c in table_columns if c not in flag_cols_set]
        else:
            for flag in flag_cols:
                prefix = flag[: -len("_covered")]
                groups[flag] = [
                    c
                    for c in table_columns
                    if c not in flag_cols_set and c.startswith(prefix)
                ]
    return groups


def _sentinel_note(series: pd.Series) -> str | None:
    """Returns a short note listing every suspicious round-number sentinel value that occupies a
    non-trivial share of non-null rows, else None. Numeric columns only — the caller is responsible
    for only calling this on a numeric series.

    Reports every candidate that clears SENTINEL_MIN_SHARE, not just the first one found — a column
    could in principle carry two different coded-missing conventions at once (e.g. -1 for one
    upstream reason and 9999 for another), and stopping at the first match would silently hide the
    second."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return None
    hits = []
    for sentinel in SENTINEL_CANDIDATES:
        share = (non_null == sentinel).mean()
        if share >= SENTINEL_MIN_SHARE:
            hits.append(f"{sentinel!r} in {share:.1%} of non-null rows")
    if not hits:
        return None
    return "possible coded-missing sentinel(s): " + "; ".join(hits)


def null_profile(df: pd.DataFrame, domain_map: pd.DataFrame, scope: str) -> pd.DataFrame:
    """One row per column in domain_map, describing df's real values for that column in this scope
    (a region name, or NATIONAL_SCOPE). Columns not present in df are skipped with a printed
    warning by the caller, not silently dropped here — this function assumes every domain_map
    column is present in df, matching the joined table's real, already-confirmed 232-column shape.
    """
    n_rows = len(df)
    records = []
    for _, row in domain_map.iterrows():
        column = row["column_name"]
        series = df[column]
        n_null = int(series.isna().sum())
        pct_null = (n_null / n_rows) if n_rows else float("nan")
        n_distinct = int(series.nunique(dropna=True))

        is_numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
        col_min = series.min() if is_numeric and n_null < n_rows else np.nan
        col_max = series.max() if is_numeric and n_null < n_rows else np.nan
        col_mean = series.mean() if is_numeric and n_null < n_rows else np.nan
        sentinel_note = _sentinel_note(series) if is_numeric else None

        records.append(
            {
                "scope": scope,
                "column_name": column,
                "domain": row["domain"],
                "source_table": row["source_table"],
                "n_rows": n_rows,
                "n_null": n_null,
                "pct_null": pct_null,
                "n_distinct": n_distinct,
                "min": col_min,
                "max": col_max,
                "mean": col_mean,
                "sentinel_note": sentinel_note,
            }
        )
    return pd.DataFrame.from_records(records)


def covered_flag_consistency(df: pd.DataFrame, flag_col: str, member_cols: list[str], scope: str) -> dict:
    """For one covered-flag column and its member columns, checks whether the flag actually
    explains the members' null pattern: every member should be null in every row where the flag is
    False, and (this project does not assume, but does check) non-null where the flag is True.

    Returns a dict with the two exception counts — n_covered_true_but_all_members_null (the flag
    says data exists but every member column is null anyway) and
    n_covered_false_but_some_member_non_null (the flag says no data, but at least one member has a
    real value) — plus n_covered_true/n_covered_false for context. Both exception counts are 0 on a
    "clean" flag; nonzero is not necessarily a bug in the data, but is exactly the kind of
    null_semantics nuance Step 5 (role/allowed_for_bias classification) needs to know about before
    treating a flag as a reliable stand-in for "this tract has real data here".

    If member_cols is empty (should not happen for any of the 19 real flags, see module docstring),
    returns a dict with all counts 0 rather than dividing by zero or raising.
    """
    if not member_cols:
        return {
            "scope": scope,
            "flag_column": flag_col,
            "n_member_columns": 0,
            "n_covered_true": 0,
            "n_covered_false": 0,
            "n_covered_true_but_all_members_null": 0,
            "n_covered_false_but_some_member_non_null": 0,
        }

    flag = df[flag_col]
    members = df[member_cols]
    all_members_null = members.isna().all(axis=1)
    any_member_non_null = members.notna().any(axis=1)

    # A plain `== True` / `== False` comparison (not `.fillna(...).astype(bool)`) is deliberate: for
    # a NaN flag value, both comparisons evaluate to False, so a null flag counts as neither
    # covered_true nor covered_false rather than being silently folded into one side.
    covered_true = flag == True  # noqa: E712
    covered_false = flag == False  # noqa: E712

    return {
        "scope": scope,
        "flag_column": flag_col,
        "n_member_columns": len(member_cols),
        "n_covered_true": int(covered_true.sum()),
        "n_covered_false": int(covered_false.sum()),
        "n_covered_true_but_all_members_null": int((covered_true & all_members_null).sum()),
        "n_covered_false_but_some_member_non_null": int(
            (covered_false & any_member_non_null).sum()
        ),
    }


def build_domain_scope_summary(profile_df: pd.DataFrame) -> pd.DataFrame:
    """Mean pct_null per domain x scope — the headline equity table: which domains are worst-covered
    in which regions. geography/population columns are excluded (they are, by construction, always
    populated identifiers/counts, not hazard or vulnerability measurements, and including them would
    dilute every region's average toward zero for reasons unrelated to data coverage)."""
    substantive = profile_df.loc[~profile_df["domain"].isin(["geography", "population"])]
    return substantive.pivot_table(index="domain", columns="scope", values="pct_null", aggfunc="mean")


# --- Real-path orchestration (network required) --------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain-map", type=Path, default=DEFAULT_DOMAIN_MAP_PATH)
    parser.add_argument("--profile-output", type=Path, default=DEFAULT_PROFILE_OUTPUT_PATH)
    parser.add_argument("--domain-summary-output", type=Path, default=DEFAULT_DOMAIN_SUMMARY_OUTPUT_PATH)
    parser.add_argument("--flag-consistency-output", type=Path, default=DEFAULT_FLAG_CONSISTENCY_OUTPUT_PATH)
    args = parser.parse_args(argv)

    try:
        domain_map = pd.read_csv(args.domain_map)
    except FileNotFoundError:
        print(
            f"ERROR: {args.domain_map} not found. Run scripts/map_column_domains.py first "
            "(Stage 3 Step 2).",
            file=sys.stderr,
        )
        return 2

    print(f"Loading {STRATA_NATIONAL_JOINED_TABLE} from the live bucket (85,396 rows expected)...")
    national_df = load_national_strata_attribute_table(STRATA_NATIONAL_JOINED_TABLE)
    print(f"Loaded {len(national_df)} rows, {len(national_df.columns)} columns.")
    if len(national_df) != EXPECTED_NATIONAL_ROW_COUNT:
        print(
            f"WARNING: expected {EXPECTED_NATIONAL_ROW_COUNT} rows (Step 1's confirmed figure, "
            f"docs/data_manifest.md Section 4.11) but got {len(national_df)}. The bucket's data may "
            "have changed since Step 1 — every null-rate figure below is still computed correctly "
            "against whatever was actually loaded, but the comparison to Step 1's numbers no longer "
            "holds and Step 1 should be re-run to confirm.",
            file=sys.stderr,
        )

    missing_columns = set(domain_map["column_name"]) - set(national_df.columns)
    if missing_columns:
        print(
            f"ERROR: {len(missing_columns)} column(s) in {args.domain_map} are not present in the "
            f"live table: {sorted(missing_columns)}. The bucket's schema may have changed since "
            "Step 1/2 — re-run inspect_national_strata_schema.py and map_column_domains.py before "
            "this script.",
            file=sys.stderr,
        )
        return 2

    scopes: dict[str, pd.DataFrame] = {NATIONAL_SCOPE: national_df}
    for region in REGIONS:
        print(f"Loading {region}'s sample-submission GEOID list...")
        sample_submission = load_sample_submission(region)
        region_geoids = set(sample_submission[STRATA_KEY_COLUMN])
        scopes[region] = filter_to_geoids(national_df, region_geoids)
        print(f"  {region}: {len(scopes[region])} scored tracts (of {len(region_geoids)} listed).")
        if len(scopes[region]) != len(region_geoids):
            print(
                f"  WARNING: {region}'s sample-submission lists {len(region_geoids)} GEOIDs but "
                f"only {len(scopes[region])} were found in the national table. Stage 2 (docs/"
                "data_manifest.md Section 4.9) confirmed missing_from_strata_count == 0 for every "
                "region — this scope's null/coverage figures below are computed only over the "
                "GEOIDs actually found, silently excluding whichever ones are missing, so treat "
                "them as provisional until this is investigated.",
                file=sys.stderr,
            )

    profile_frames = [null_profile(df, domain_map, scope) for scope, df in scopes.items()]
    profile_df = pd.concat(profile_frames, ignore_index=True)

    args.profile_output.parent.mkdir(parents=True, exist_ok=True)
    profile_df.to_csv(args.profile_output, index=False)
    print(f"\nWrote {len(profile_df)} (column x scope) rows to {args.profile_output}")

    domain_summary = build_domain_scope_summary(profile_df)
    domain_summary.to_csv(args.domain_summary_output)
    print(f"Wrote domain x scope null-rate summary to {args.domain_summary_output}")
    print()
    print(domain_summary.to_string())

    covered_flag_groups = identify_covered_flag_groups(domain_map)
    consistency_records = []
    for scope, df in scopes.items():
        for flag_col, member_cols in covered_flag_groups.items():
            consistency_records.append(covered_flag_consistency(df, flag_col, member_cols, scope))
    consistency_df = pd.DataFrame.from_records(consistency_records, columns=_FLAG_CONSISTENCY_COLUMNS)
    consistency_df.to_csv(args.flag_consistency_output, index=False)
    print(f"\nWrote {len(consistency_df)} flag-consistency rows to {args.flag_consistency_output}")

    exceptions = consistency_df.loc[
        (consistency_df["n_covered_true_but_all_members_null"] > 0)
        | (consistency_df["n_covered_false_but_some_member_non_null"] > 0)
    ]
    if len(exceptions) > 0:
        print(f"\n{len(exceptions)} scope/flag combination(s) have a covered-flag exception:")
        print(exceptions.to_string(index=False))
    else:
        print("\nEvery covered flag's null pattern is fully explained by the flag itself, in every scope.")

    sentinel_hits = profile_df.loc[profile_df["sentinel_note"].notna()]
    if len(sentinel_hits) > 0:
        print(f"\n{len(sentinel_hits)} (column x scope) row(s) show a possible coded-missing sentinel:")
        print(sentinel_hits[["scope", "column_name", "sentinel_note"]].to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
