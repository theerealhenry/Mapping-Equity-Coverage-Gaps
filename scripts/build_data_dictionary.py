"""
scripts/build_data_dictionary.py — Stage 3, Step 8: the full data dictionary build.

Steps 1-7 each answered one narrow question about `national-strata-tract-table`'s 232 columns —
what exists (Step 1), what domain each belongs to (Step 2), how complete each is (Step 3), whether
its vintage is current (Step 4), whether it may be used for scoring or bias analysis (Step 5), which
Bias Discovery candidate(s) it can feed (Step 6), and whether the national schema actually matches
what each of the four study regions ships (Step 7). This step does not repeat any of that work — it
assembles the seven already-committed outputs of Steps 1-7 into two things: one machine-readable
catalog (`docs/schema_catalog.csv`) and one human-readable reference (`docs/DATA_DICTIONARY.md`),
so a reader (or a later script) never again has to open seven separate CSVs to answer one question
about one column.

**One genuinely new fact is folded in here, not carried over from an earlier step.** Step 7's live
region-schema read found `frac_inside_aoi` — a column present in all four regions' own
`<region>-strata-tract-table` but absent from the national schema entirely, so it was never seen by
Steps 2/5/6 and has no row in any of their outputs. Step 7 deliberately deferred classifying it,
flagging it as "a real, open item for Stage 3 Step 8's data-dictionary build to classify properly."
This step is that classification: `frac_inside_aoi` is read live (column-pruned, GEOID +
frac_inside_aoi only, from all four regions) so its dictionary entry is grounded in its real values,
not guessed from its name alone. `role`/`allowed_for_scoring` are structural facts, hand-set the same
way Steps 5/6 classified the structurally closest existing columns (`AWATER`/`INTPTLAT`/`INTPTLON`,
role=geometry_measure). **`allowed_for_bias`/`candidate_hypotheses` are NOT hand-set** — they are
computed live from the real distinct-value count, by the exact same hard, data-driven override Step
5 already established for every other column in this project (`scripts/classify_columns.py`'s
`compute_allowed_for_bias`: n_distinct <= 1 forces `allowed_for_bias=False` regardless of role). This
was not a hypothetical guard: it fired on the real live data — `frac_inside_aoi` is constant at 1.0
across all 9,386 tracts in all four regions, confirmed by Henry's live run, meaning every tract in
this project's four pre-packaged study regions is fully inside its own region's area-of-interest
boundary, with no partial-containment edge cases in this data at all. See `FRAC_INSIDE_AOI_ROLE` and
`build_frac_inside_aoi_row`'s override logic below for the full reasoning, both for this constant
case and the non-constant fallback preserved for a future region/vintage where it might vary.

**Vintage status is folded in at the source-table level, not re-derived.** `docs/data_vintage_
confirmation.md` (Step 4) already did the real external-research work; `VINTAGE_STATUS_BY_SOURCE_
TABLE` below is a hand-typed transcription of that document's own conclusions, one entry per source
table (vintage is a property of the underlying dataset a source table came from, not of any one
column within it) — checked by a permanent regression test that its keys match `src.config.
NATIONAL_STRATA_SOURCE_TABLES` exactly, the same discipline every other hand-typed set in this
project already follows (Steps 4/5/6's own hand-typed-set regression tests).

Design: testable-core / thin-real-path-wrapper, the same pattern used throughout this project.
Every function that builds/merges/renders the catalog is pure and fully unit-tested with no
network. `read_frac_inside_aoi_column` is the one thin, live-bucket-touching wrapper (column-pruned
read, not a full-table download) — tested against a real local parquet fixture via
`pyarrow.fs.LocalFileSystem`, never the real bucket.

Run with:
    python -m scripts.build_data_dictionary

Writes `docs/schema_catalog.csv` (233 rows: the 232 real national-schema columns plus the one
region-only `frac_inside_aoi` row) and `docs/DATA_DICTIONARY.md` (the same 233 columns, grouped by
domain, in human-readable form).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pyarrow.fs import FileSystem, S3FileSystem

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import (  # noqa: E402
    NATIONAL_STRATA_SOURCE_TABLES,
    REGIONS,
    S3_REGION,
    STRATA_KEY_COLUMN,
    STRATA_NATIONAL_JOINED_TABLE,
    STRATA_REGION_JOINED_TABLE,
    strata_s3_path,
)

DEFAULT_NATIONAL_SCHEMA_PATH = REPO_ROOT / "docs" / "national_strata_schema_raw.csv"
DEFAULT_DOMAIN_MAP_PATH = REPO_ROOT / "docs" / "column_domain_map.csv"
DEFAULT_NULL_PROFILE_PATH = REPO_ROOT / "docs" / "coverage_null_profile.csv"
DEFAULT_CLASSIFICATION_PATH = REPO_ROOT / "docs" / "column_classification.csv"
DEFAULT_CANDIDATE_HYPOTHESES_PATH = REPO_ROOT / "docs" / "column_candidate_hypotheses.csv"
DEFAULT_REGION_CONSISTENCY_PATH = REPO_ROOT / "docs" / "region_national_schema_consistency.csv"

DEFAULT_CATALOG_OUTPUT_PATH = REPO_ROOT / "docs" / "schema_catalog.csv"
DEFAULT_DICTIONARY_OUTPUT_PATH = REPO_ROOT / "docs" / "DATA_DICTIONARY.md"

NATIONAL_SCOPE = "national"
FRAC_INSIDE_AOI_COLUMN = "frac_inside_aoi"

# Stage 6 Step 8 (2026-09-16) appended project-computed feature-table columns directly into this
# same schema_catalog.csv/DATA_DICTIONARY.md, tagged with this domain value, per the Stage 6
# guideline's own instruction to keep "one continuous, consistent catalog." Those rows are
# classified by hand in schema_catalog.csv itself (never via the three Stage 3 per-column
# generator CSVs this script reads) and are documented in DATA_DICTIONARY.md's own dedicated,
# hand-authored "## Stage 6, Step 8" section — not through the generic per-domain rendering below.
# `render_data_dictionary_markdown` excludes them from that generic loop for the same reason
# `region_only` rows already are: mixing them in would silently produce a broken generic table
# (Stage 6 rows carry no `pct_null`/`national_position`, which crashes or misformats the generic
# per-domain table) instead of respecting the hand-authored section that already covers them.
STAGE6_APPENDED_DOMAIN = "coverage_gap"

# Step 1's independently-confirmed row count (docs/data_manifest.md Section 4.11) — checked again
# here as a cheap sanity guard, the same discipline every prior Stage 3 step has used.
EXPECTED_NATIONAL_ROW_COUNT = 85_396

# --- frac_inside_aoi classification -------------------------------------------------------------
# `frac_inside_aoi` was found only in Step 7's live region-schema read (present in all four regions'
# joined strata tables, absent from the national schema — see the module docstring). `role` and the
# scoring rule are structural facts, independent of the column's actual values, and are hand-set
# below. `allowed_for_bias`/`candidate_hypotheses` are NOT hand-set — they are computed live from
# `combined_profile["n_distinct"]` in `build_frac_inside_aoi_row`, by the exact same hard,
# data-driven override Step 5 already established for every other column in this project
# (`scripts/classify_columns.py`'s `compute_allowed_for_bias`: any column with n_distinct <= 1 is
# constant and therefore forced to allowed_for_bias=False, regardless of what its role would
# otherwise suggest). This was not a hypothetical guard added out of caution — it is exactly what
# fired on the real live data: `frac_inside_aoi` is constant at 1.0 across all 9,386 tracts in all
# four regions (n_distinct=1, confirmed live), meaning every one of this project's four pre-packaged
# study regions ships only tracts that are fully inside its own area-of-interest boundary. The
# geometry_measure-based reasoning below (a tract only partially inside a region's AOI is the same
# edge case Tribal Sub-type + Edge Effect already covers for tribal lands) is preserved as the
# NON-constant-case fallback, in case this project is ever extended to a region/vintage where
# frac_inside_aoi genuinely does vary — it is deliberately NOT hardcoded True given today's data.
FRAC_INSIDE_AOI_ROLE = "geometry_measure"
FRAC_INSIDE_AOI_CANDIDATE_HYPOTHESES_IF_VARIABLE = "Tribal Sub-type + Edge Effect"
FRAC_INSIDE_AOI_BIAS_REASON_IF_VARIABLE = (
    "region-boundary edge-fraction measure — a tract with a low frac_inside_aoi is only partially "
    "inside the study region, the same geometric edge-case Tribal Sub-type + Edge Effect already "
    "covers for tribal lands that straddle a boundary, generalized here to every tract at a region's "
    "edge rather than tribal tracts specifically. Worth a Stage 8/9 judgment call on whether this "
    "earns its own place in that candidate's writeup or stays a supporting covariate."
)
FRAC_INSIDE_AOI_CANDIDATE_REASON_IF_VARIABLE = (
    "new column, found only in Step 7's live region-schema read — absent from the national schema "
    "Step 6 tagged, so it has no Step 6 row of its own. Classified directly here using Step 6's own "
    "role-based logic for geometry_measure columns, restricted to Tribal Sub-type + Edge Effect only "
    "(not also Dispatch-Blind Reachability — see FRAC_INSIDE_AOI_ROLE's comment for why)."
)
FRAC_INSIDE_AOI_SCORING_REASON = (
    "strata-tract-table lives entirely under strata/ (the Bias API stratification datasets), never "
    "under reference/ (the map data actually scored) — the same table-wide blanket rule Step 5 "
    "established for every column of national-strata-tract-table applies identically here, since "
    "frac_inside_aoi lives in the region-level counterpart of that same table family."
)

# --- Vintage status, transcribed from docs/data_vintage_confirmation.md (Stage 3 Step 4) ---------
# One entry per source table (vintage is a property of the underlying public dataset a source table
# was built from, not of any individual column within it). Keys must match
# `src.config.NATIONAL_STRATA_SOURCE_TABLES` exactly — checked by a permanent regression test, the
# same discipline every other hand-typed set in this project already follows. Six of the 25 source
# tables contribute no attribute columns to the 232-column joined table at all (5 geometry-only
# boundary/station tables plus the county-level `national-cdc-wonder-heat-mortality` reference
# table, confirmed directly against `docs/column_domain_map.csv`'s 19 real source_table values) —
# these are marked `not_applicable` rather than left out, so every one of the 25 tables this project
# tracks has an explicit, on-record status.
VINTAGE_STATUS_BY_SOURCE_TABLE: dict[str, tuple[str, str]] = {
    "national-carbonplan-tract-table": (
        "confirmed",
        "carbonplan_version='v1.1.0' matches CarbonPlan's current public release tag.",
    ),
    "national-cdc-wonder-heat-mortality": (
        "not_applicable",
        "No attribute columns from this table are joined into national-strata-tract-table; not "
        "part of Step 4's vintage check.",
    ),
    "national-cdc-wonder-tract-table": (
        "confirmed_with_clarification",
        "The 1981-2010 window traces to a NOAA NCEI Normals baseline, not a CDC-native vintage; the "
        "live cdcw_grain='county' value also revealed this table is county-level, not tract-level, "
        "disaggregated down to every tract sharing one county-wide figure.",
    ),
    "national-census-aiannh": (
        "not_applicable",
        "Geometry-only table (AIANNH boundaries); no attribute columns joined into "
        "national-strata-tract-table.",
    ),
    "national-census-tract-table": (
        "confirmed",
        "tract_vintage=2020 matches the 2020 TIGER/Line Census tract boundaries and P.L. 94-171 "
        "population base.",
    ),
    "national-census-tracts": (
        "not_applicable",
        "Geometry-only table (tract boundaries used for spatial joins); no attribute columns "
        "joined into national-strata-tract-table.",
    ),
    "national-census-tribal-subdivisions": (
        "not_applicable",
        "Geometry-only table, also confirmed absent from South-Central Texas's package; no "
        "attribute columns joined into national-strata-tract-table.",
    ),
    "national-census-tribal-tracts": (
        "not_applicable",
        "Geometry-only table; no attribute columns joined into national-strata-tract-table.",
    ),
    "national-cvi-tract-table": (
        "confirmed_with_clarification",
        "cvi_source_vintage=2010 is the CVI methodology's deliberately-chosen Census geography "
        "vintage, not its 2023 publication year or its ~2017-2019 underlying-data years.",
    ),
    "national-drought-gov-tract-table": (
        "unresolved",
        "drought_gov_window_start/end (2015-2023) and spi_calibration have no single documented "
        "NIDIS/CPC top-level vintage; would need a narrower per-dataset page to close.",
    ),
    "national-epht-heat-tract-table": (
        "confirmed_with_clarification",
        "epht_threshold ('95th percentile') and epht_metric confirmed live; the 2015-2023 window's "
        "exact provenance is unresolved pending the EPHT Data Explorer's per-measure metadata.",
    ),
    "national-fpa-fod-tract-table": (
        "confirmed",
        "fod_year_min/max (1992-2020) matches USFS FPA-FOD 6th Edition (RDS-2013-0009.6) exactly.",
    ),
    "national-mtbs-tract-table": (
        "confirmed_with_clarification",
        "Coverage window (1984-2023) and size-threshold convention confirmed; the live file is one "
        "MTBS release behind the current v12.0 (April 2025) — expected for any snapshot, not an "
        "error.",
    ),
    "national-nasa-heat-tract-table": (
        "confirmed_with_clarification",
        "gehe_* (1983-2016) is an exact title/date match to NASA SEDAC's GEHE product; uhe_* is "
        "strengthened toward SEDAC's UHE-Daily product (Mexico/Canada cities present in the live "
        "data) but not fully proven.",
    ),
    "national-nchs-tract-table": (
        "confirmed_but_flagged",
        "nchs_year=2013 while CDC's current scheme is 2023; CDC itself calls the practical "
        "difference 'minimal'. Flagged as a Stage 8/9 testable hypothesis (a county-level crosswalk "
        "check), not asserted as a finding on its own.",
    ),
    "national-nifc-tract-table": (
        "confirmed",
        "nifc_year_min/max (1984-2025) is consistent with NIFC's continuously-updated, no-fixed-"
        "edition feature layer.",
    ),
    "national-noaa-ghcn-stations": (
        "not_applicable",
        "Geometry-only station-location table; no attribute columns joined into "
        "national-strata-tract-table.",
    ),
    "national-noaa-ghcn-tract-table": (
        "unresolved",
        "ghcn_year_min/max (2015-2023) matches no documented NOAA-native derived product; most "
        "likely this project's own upstream window choice, not a GHCN limitation.",
    ),
    "national-ruca-tract-table": (
        "confirmed",
        "ruca_year=2020 matches USDA ERS's current 2020-vintage RUCA release.",
    ),
    "national-rucc-tract-table": (
        "confirmed",
        "rucc_year=2023 matches USDA ERS's current published RUCC release.",
    ),
    "national-svi-tract-table": (
        "confirmed",
        "svi_year=2022 is CDC/ATSDR's current full SVI release (2018-2022 5-year ACS).",
    ),
    "national-tribal-tract-table": (
        "ambiguous_no_marker",
        "Carries no in-file vintage column; assumed 2020 TIGER/Line AIANNH vintage by consistency "
        "with tract_vintage=2020, not independently confirmed from the file itself.",
    ),
    "national-usdm-drought-tract-table": (
        "confirmed",
        "usdm_year_min/max (2015-2023) is a deliberate sub-window of USDM's full record (Jan "
        "2000-present), not a data limitation.",
    ),
    "national-usfs-wildfire-tract-table": (
        "confirmed",
        "usfs_edition confirms the 2nd edition (RDS-2020-0060-2), CONUS extent.",
    ),
    "national-usgs-combined-tract-table": (
        "confirmed",
        "usgs_record_start/end (1835-2020) is consistent with an FY21-vintage pull of USGS's "
        "versioned combined wildland-fire dataset.",
    ),
}

_FRAC_INSIDE_AOI_VINTAGE = (
    "not_applicable",
    "Not part of the national schema; discovered only in Step 7's live region-schema read. No "
    "independent vintage metadata of its own.",
)


# -------------------------------------------------------------------------------------------
# Pure core functions — no I/O, fully unit-testable
# -------------------------------------------------------------------------------------------


def load_national_joined_columns(national_schema_csv: pd.DataFrame) -> pd.DataFrame:
    """Extracts (column_name, national_position, dtype) for the national joined table, in schema
    order, from the already-committed `docs/national_strata_schema_raw.csv`. Raises `ValueError`
    loudly if that table's rows are missing, mirroring Step 7's `load_national_joined_schema`."""
    rows = national_schema_csv.loc[national_schema_csv["source_table"] == STRATA_NATIONAL_JOINED_TABLE]
    if len(rows) == 0:
        raise ValueError(
            f"{STRATA_NATIONAL_JOINED_TABLE!r} has no rows in the given national schema data — "
            "re-run scripts/inspect_national_strata_schema.py (Stage 3 Step 1) first"
        )
    rows = rows.sort_values("position")
    return rows[["column_name", "position", "arrow_dtype"]].rename(
        columns={"position": "national_position", "arrow_dtype": "dtype"}
    )


def summarize_region_presence(
    region_consistency: pd.DataFrame, all_regions: list[str] | None = None
) -> pd.DataFrame:
    """One row per column_name appearing anywhere in Step 7's per-region detail CSV, summarizing
    which of the four regions actually carry it. `present_in_regions`/`missing_from_regions` are
    ';'-joined, alphabetically sorted region-name strings (empty string, not NaN, when the list is
    empty) so the result round-trips cleanly through CSV. `present_in_all_four_regions` is True only
    when the column is present (`in_region`) in all of `all_regions` found for it — a column present
    in fewer rows than that at all (should never happen against the real, always-four-region output,
    but not assumed) is also treated as not present in all four.

    `all_regions` defaults to `src.config.REGIONS` (the project's real, fixed four regions) — the
    caller should only ever override it in a test that wants to exercise this function's pure logic
    against synthetic region labels.

    Deliberately computes `missing` against the fixed, complete `all_regions` list rather than
    against `~group["in_region"]` alone: Step 7's per-region detail CSV only ever emits a row for a
    (column, region) pair when that region's own schema block actually carries the column at all
    (every region's national columns, plus that region's own extra-in-region-only columns) — a
    region that lacks an extra-in-region-only column entirely never gets a row for it, `in_region`
    or not, so `group` can be missing rows outright rather than merely containing `in_region=False`
    rows. Computing `missing` from `~in_region` alone would silently under-report which regions a
    column is missing from whenever a region has zero rows for it at all — precisely the case this
    field exists to describe (this was a real, confirmed bug in an earlier version of this function:
    a column present in only 2 of 4 regions came back with `missing_from_regions=""` instead of the
    two genuinely-missing region names, because neither of those two regions ever produced a row for
    it at all). Comparing the regions actually present for a column against the full, fixed region
    list catches both shapes ("row exists with `in_region=False`" and "no row at all for this
    region") as equally missing."""
    if all_regions is None:
        all_regions = REGIONS
    records = []
    for column_name, group in region_consistency.groupby("column_name", sort=False):
        present = sorted(group.loc[group["in_region"], "region"].tolist())
        missing = sorted(set(all_regions) - set(present))
        records.append(
            {
                "column_name": column_name,
                "present_in_regions": ";".join(present),
                "missing_from_regions": ";".join(missing),
                "present_in_all_four_regions": len(present) == len(all_regions) and len(missing) == 0,
            }
        )
    return pd.DataFrame.from_records(records)


# Columns that must never come back null for one of the 232 real national columns once the merges
# below finish. `validate="one_to_one"` (used on every merge) only guards against a DUPLICATE match
# — it says nothing about a MISSING one: a `how="left"` merge silently fills every right-hand column
# with NaN for a left row that finds no match at all, and every one of Steps 2/3/5/6/7's outputs is
# an upstream file this script does not control the shape of. "missing_from_regions" is excluded
# deliberately — it is a legitimate empty STRING (not a null) for every column present everywhere,
# so it is never null for a matched row regardless of that row's own content, and would not actually
# detect the failure mode this check exists for.
_COMPLETENESS_REQUIRED_COLUMNS = [
    "source_table", "domain", "attribution_method",
    "n_null", "pct_null", "n_distinct",
    "role", "allowed_for_scoring", "scoring_reason", "allowed_for_bias", "bias_reason",
    "candidate_hypotheses_reason",
    "present_in_regions", "present_in_all_four_regions",
]

_MISSING_VINTAGE_SENTINEL = "MISSING_VINTAGE_ENTRY"


def assert_catalog_completeness(catalog: pd.DataFrame) -> None:
    """Raises `AssertionError`, loudly and with the specific column names named, if any of the 232
    real national columns ended up with a null value in a field that should never legitimately be
    null (see `_COMPLETENESS_REQUIRED_COLUMNS`) — the signature of an upstream file (Steps 2/3/5/6/7)
    silently missing a row for a real column, which a bare `how="left"` merge would otherwise let
    through as a quietly incomplete dictionary entry rather than a loud failure. Called right after
    the five merges, before `vintage_status`/`vintage_note` exist — see `assert_no_missing_vintage_
    status` for that field's own, separately-timed check."""
    for column in _COMPLETENESS_REQUIRED_COLUMNS:
        bad = catalog.loc[catalog[column].isna(), "column_name"].tolist()
        if bad:
            raise AssertionError(
                f"{len(bad)} national column(s) have a null {column!r} after merging — an upstream "
                f"Stage 3 output is missing a row for them (re-run the step that produces it): {bad}"
            )


def assert_no_missing_vintage_status(catalog: pd.DataFrame) -> None:
    """Raises `AssertionError` if any row's `vintage_status` carries `_MISSING_VINTAGE_SENTINEL` —
    meaning its `source_table` has no entry in the hand-typed `VINTAGE_STATUS_BY_SOURCE_TABLE`. This
    field is populated by a dict lookup, not a DataFrame merge, so it needs its own check rather than
    `assert_catalog_completeness`'s null-based logic (a missing dict entry produces the sentinel
    STRING, not a null, by design — the `.map(...)` call itself never returns NaN for a present
    source_table). Called after `vintage_status` is computed, unlike `assert_catalog_completeness`."""
    bad = catalog.loc[catalog["vintage_status"] == _MISSING_VINTAGE_SENTINEL, "column_name"].tolist()
    if bad:
        bad_source_tables = sorted(catalog.loc[catalog["column_name"].isin(bad), "source_table"].unique())
        raise AssertionError(
            f"{len(bad)} national column(s) belong to a source_table with no "
            f"VINTAGE_STATUS_BY_SOURCE_TABLE entry: {bad} (source table(s): {bad_source_tables}) "
            "— add an entry, transcribed from docs/data_vintage_confirmation.md."
        )


def build_catalog(
    national_columns: pd.DataFrame,
    domain_map: pd.DataFrame,
    null_profile: pd.DataFrame,
    classification: pd.DataFrame,
    candidate_hypotheses: pd.DataFrame,
    region_presence: pd.DataFrame,
    frac_inside_aoi_row: dict,
) -> pd.DataFrame:
    """Left-joins Steps 1/2/3/5/6/7's already-committed outputs onto the national joined table's
    232-column list (one row per column, national schema order preserved), then appends the one
    genuinely new `frac_inside_aoi` row. Every merge is `validate="one_to_one"` against `column_name`
    — each of Steps 2/3/5/6 is independently already known (their own prior review passes) to carry
    exactly one row per column, so a merge producing more than one match per column would mean one
    of those upstream files has silently changed shape since this project last checked it, and
    should fail loudly here rather than silently fan out rows. `validate="one_to_one"` alone does
    NOT catch the opposite failure — a national column with NO match at all in an upstream file,
    which a left join would otherwise silently fill with NaN — so `assert_catalog_completeness` is
    run immediately after all five merges, before the vintage lookup or the extra row is appended,
    to close that gap explicitly."""
    national_profile = null_profile.loc[null_profile["scope"] == NATIONAL_SCOPE]

    catalog = national_columns.merge(
        domain_map[["column_name", "source_table", "domain", "attribution_method"]],
        on="column_name",
        how="left",
        validate="one_to_one",
    )
    catalog = catalog.merge(
        national_profile[["column_name", "n_null", "pct_null", "n_distinct", "min", "max", "mean", "sentinel_note"]],
        on="column_name",
        how="left",
        validate="one_to_one",
    )
    catalog = catalog.merge(
        classification[["column_name", "role", "allowed_for_scoring", "scoring_reason", "allowed_for_bias", "bias_reason"]],
        on="column_name",
        how="left",
        validate="one_to_one",
    )
    catalog = catalog.merge(
        candidate_hypotheses[["column_name", "candidate_hypotheses", "candidate_hypotheses_reason"]],
        on="column_name",
        how="left",
        validate="one_to_one",
    )
    catalog = catalog.merge(
        region_presence[["column_name", "present_in_regions", "missing_from_regions", "present_in_all_four_regions"]],
        on="column_name",
        how="left",
        validate="one_to_one",
    )

    assert_catalog_completeness(catalog)

    catalog["region_only"] = False
    catalog["profile_scope"] = f"national ({EXPECTED_NATIONAL_ROW_COUNT:,} tracts)"
    catalog["vintage_status"] = catalog["source_table"].map(
        lambda t: VINTAGE_STATUS_BY_SOURCE_TABLE.get(t, (_MISSING_VINTAGE_SENTINEL, ""))[0]
    )
    catalog["vintage_note"] = catalog["source_table"].map(
        lambda t: VINTAGE_STATUS_BY_SOURCE_TABLE.get(t, (_MISSING_VINTAGE_SENTINEL, ""))[1]
    )
    assert_no_missing_vintage_status(catalog)

    extra = pd.DataFrame.from_records([frac_inside_aoi_row])
    catalog = pd.concat([catalog, extra], ignore_index=True, sort=False)
    return catalog


def profile_series(series: pd.Series) -> dict:
    """Pure numeric profile of one Series — n_rows, n_null, pct_null, n_distinct, min, max, mean.
    Deliberately simple (no sentinel-value detection, unlike Step 3's `null_profile`) — this is a
    single new column found late, not a full re-run of Step 3's profiling machinery for 232 columns;
    a sentinel check can be added later if a suspicious min/max value actually shows up here."""
    n_rows = len(series)
    n_null = int(series.isna().sum())
    non_null = series.dropna()
    return {
        "n_rows": n_rows,
        "n_null": n_null,
        "pct_null": (n_null / n_rows) if n_rows else float("nan"),
        "n_distinct": int(series.nunique(dropna=True)),
        "min": float(non_null.min()) if len(non_null) else float("nan"),
        "max": float(non_null.max()) if len(non_null) else float("nan"),
        "mean": float(non_null.mean()) if len(non_null) else float("nan"),
    }


def build_frac_inside_aoi_row(
    national_row_template: list[str], combined_profile: dict, *, regions_included: list[str] | None = None
) -> dict:
    """Assembles the one hand-classified `frac_inside_aoi` catalog row (see the module docstring
    and the FRAC_INSIDE_AOI_* constants above for the classification reasoning), using
    `combined_profile` (a `profile_series` result over ALL four regions' real values concatenated
    together) for its numeric fields rather than any placeholder. `national_row_template` is simply
    the target catalog's column order (from `national_columns.columns` plus the merge-added columns)
    so this row always has exactly the same columns as every other row, in the same order — passed
    in rather than hardcoded so a schema change to the main catalog can't silently leave this row
    with a different shape. `regions_included` names which regions actually contributed to
    `combined_profile` (defaults to all four, for the offline `--skip-live-read` path and existing
    callers) — `main()` passes the real subset when a live per-region read fails partway through, so
    `profile_scope` never overstates how many regions the numeric fields actually cover."""
    if regions_included is None:
        regions_included = list(REGIONS)
    vintage_status, vintage_note = _FRAC_INSIDE_AOI_VINTAGE

    n_rows = combined_profile.get("n_rows", 0)
    n_distinct = combined_profile.get("n_distinct", 0)
    if n_rows > 0 and n_distinct <= 1:
        # The hard, data-driven override actually fired on the real live data (confirmed: constant
        # at 1.0 across all 9,386 tracts in all four regions) — the exact same rule Step 5 already
        # established for every other column in this project (compute_allowed_for_bias), applied
        # here rather than trusting the structural, role-based guess above.
        allowed_for_bias = False
        candidate_hypotheses = ""
        constant_value = combined_profile.get("min")
        bias_reason = (
            f"constant across all {n_rows:,} tracts profiled live (n_distinct={n_distinct}, "
            f"value={constant_value!r}) — carries no discriminative signal for any bias analysis, "
            "regardless of role. The same hard, data-driven override Step 5 already established "
            "(scripts/classify_columns.py's compute_allowed_for_bias) for every other constant "
            "column in this project fires here too."
        )
        candidate_hypotheses_reason = (
            "blank — allowed_for_bias=False (constant-value override; see bias_reason), matching "
            "Step 6's own rule that a column with allowed_for_bias=False is never tagged with a "
            "candidate hypothesis."
        )
    elif n_rows > 0:
        allowed_for_bias = True
        candidate_hypotheses = FRAC_INSIDE_AOI_CANDIDATE_HYPOTHESES_IF_VARIABLE
        bias_reason = FRAC_INSIDE_AOI_BIAS_REASON_IF_VARIABLE
        candidate_hypotheses_reason = FRAC_INSIDE_AOI_CANDIDATE_REASON_IF_VARIABLE
    else:
        # No live values available yet (offline --skip-live-read, or every region's read failed) —
        # falls back to the structural, role-based classification, explicitly labeled provisional
        # rather than presented as confirmed, since the constant-value override above cannot be
        # evaluated without real values.
        allowed_for_bias = True
        candidate_hypotheses = FRAC_INSIDE_AOI_CANDIDATE_HYPOTHESES_IF_VARIABLE
        bias_reason = (
            FRAC_INSIDE_AOI_BIAS_REASON_IF_VARIABLE
            + " PROVISIONAL — no live read has completed yet to confirm this against real values "
            "(n_distinct unknown); re-run without --skip-live-read before trusting this."
        )
        candidate_hypotheses_reason = FRAC_INSIDE_AOI_CANDIDATE_REASON_IF_VARIABLE

    row = {
        "column_name": FRAC_INSIDE_AOI_COLUMN,
        "national_position": pd.NA,
        "dtype": "double",
        "source_table": f"{STRATA_REGION_JOINED_TABLE} (region-only)",
        "domain": "geography",
        "attribution_method": "region-only, discovered live in Step 7's schema read",
        "n_null": combined_profile["n_null"],
        "pct_null": combined_profile["pct_null"],
        "n_distinct": combined_profile["n_distinct"],
        "min": combined_profile["min"],
        "max": combined_profile["max"],
        "mean": combined_profile["mean"],
        "sentinel_note": "",
        "role": FRAC_INSIDE_AOI_ROLE,
        "allowed_for_scoring": False,
        "scoring_reason": FRAC_INSIDE_AOI_SCORING_REASON,
        "allowed_for_bias": allowed_for_bias,
        "bias_reason": bias_reason,
        "candidate_hypotheses": candidate_hypotheses,
        "candidate_hypotheses_reason": candidate_hypotheses_reason,
        "present_in_regions": ";".join(sorted(REGIONS)),
        "missing_from_regions": "",
        "present_in_all_four_regions": True,
        "region_only": True,
        "profile_scope": (
            f"region-combined ({combined_profile['n_rows']:,} tracts across "
            f"{len(regions_included)} region(s): {', '.join(regions_included) if regions_included else 'none'})"
        ),
        "vintage_status": vintage_status,
        "vintage_note": vintage_note,
    }
    missing = [c for c in national_row_template if c not in row]
    if missing:
        raise AssertionError(
            f"build_frac_inside_aoi_row is missing catalog column(s) {missing} — the main catalog's "
            "schema changed without this row being updated to match."
        )
    return {c: row[c] for c in national_row_template}


def render_data_dictionary_markdown(catalog: pd.DataFrame) -> str:
    """Renders the human-readable `docs/DATA_DICTIONARY.md` from the catalog DataFrame — one table
    per domain (national schema order within each domain, region-only rows appended last), plus a
    short header explaining the source of every field, a dedicated section on the 6 columns absent
    from every region's own joined table, and a dedicated section on the region-only addition."""
    lines: list[str] = []
    lines.append("# Data dictionary — national-strata-tract-table")
    lines.append("")
    lines.append(
        "Stage 3 Step 8 of the data-audit plan (see `docs/data_manifest.md` Section 4). Every field "
        "below is drawn from an already-committed, independently-run Stage 3 step, not re-derived "
        "here: `dtype`/`national_position` from Step 1, `domain`/`source_table` from Step 2, the "
        "numeric profile columns from Step 3 (national scope), `role`/`allowed_for_scoring`/"
        "`allowed_for_bias` from Step 5, `candidate_hypotheses` from Step 6, `present_in_regions`/"
        "`missing_from_regions` from Step 7, and `vintage_status`/`vintage_note` from Step 4's "
        "external research (`docs/data_vintage_confirmation.md`), transcribed once per source table "
        "since vintage is a property of the underlying dataset, not of any individual column."
    )
    lines.append("")
    lines.append(
        "**allowed_for_scoring is False for every single row in this dictionary, including the "
        "region-only addition below, without exception** — this table lives entirely under "
        "`strata/`, never `reference/`, and no column here may influence the submitted coverage-gap "
        "number regardless of role or domain (Step 5)."
    )
    lines.append("")

    columns_missing_everywhere = catalog.loc[
        (~catalog["region_only"]) & (catalog["present_in_all_four_regions"] == False),  # noqa: E712
        "column_name",
    ].tolist()
    if columns_missing_everywhere:
        lines.append("## Columns absent from every region's own joined table")
        lines.append("")
        lines.append(
            "Confirmed live (Step 7): these columns exist in the national schema but are absent from "
            "all four regions' `<region>-strata-tract-table`. See `docs/data_manifest.md` Section "
            "4.17 for the full triage of which of these are harmless (already `allowed_for_bias="
            "False`) versus materially impactful."
        )
        lines.append("")
        for name in columns_missing_everywhere:
            row = catalog.loc[catalog["column_name"] == name].iloc[0]
            lines.append(
                f"- `{name}` (role={row['role']}, allowed_for_bias={row['allowed_for_bias']})"
            )
        lines.append("")

    if "sentinel_note" in catalog.columns:
        sentinel_rows = catalog.loc[catalog["sentinel_note"].notna() & (catalog["sentinel_note"] != "")]
        if len(sentinel_rows):
            lines.append("## Possible coded-missing sentinel values (Step 3 finding)")
            lines.append("")
            lines.append(
                "Columns where a round-number value (e.g. -1, 9999) occupies a non-trivial share of "
                "non-null rows — a candidate for a coded-missing convention rather than a genuine "
                "measurement, first found by Step 3's null-profiling pass (e.g. Microsoft Building "
                "Footprints' `confidence == -1.0` placeholder, `docs/data_manifest.md` Section 4.8). "
                "Surfaced here explicitly rather than only in `docs/coverage_null_profile.csv`, since "
                "this is exactly the kind of proactive data-quality finding worth a reader seeing "
                "without having to separately open that CSV."
            )
            lines.append("")
            for _, row in sentinel_rows.iterrows():
                lines.append(f"- `{row['column_name']}` (`{row['source_table']}`): {row['sentinel_note']}")
            lines.append("")

    region_only = catalog.loc[catalog["region_only"]]
    if len(region_only):
        lines.append("## Region-only addition")
        lines.append("")
        lines.append(
            "Found only in Step 7's live region-schema read — present in all four regions' own "
            "joined tables, absent from the national schema, so it was never seen by Steps 2/5/6. "
            "Classified directly in this step; see the row below and `scripts/build_data_dictionary."
            "py`'s module docstring for the full reasoning."
        )
        lines.append("")
        for _, row in region_only.iterrows():
            # pd.notna guard, matching the identical pattern already used for the domain tables
            # below: a blank candidate_hypotheses is a real, legitimate value (frac_inside_aoi's
            # own committed row is exactly this case, once its constant-value override fires), and
            # it must render as '' — not as the literal string 'nan' this would otherwise produce
            # if `catalog` ever arrives here having round-tripped through a plain pd.read_csv()
            # (which reads a blank CSV cell back as float NaN, not an empty string). The real,
            # committed DATA_DICTIONARY.md was never affected by this — main() always calls this
            # function on the fresh in-memory catalog build_catalog() returns, where a blank
            # candidate_hypotheses is a genuine Python '' from build_frac_inside_aoi_row, never NaN
            # — but any future caller that re-renders from a re-read CSV (exactly what
            # tests/test_data_dictionary.py's own cross-file consistency check now does) would hit
            # this without the guard.
            candidates = row["candidate_hypotheses"] if pd.notna(row["candidate_hypotheses"]) else ""
            lines.append(f"- `{row['column_name']}`: role={row['role']}, "
                         f"allowed_for_bias={row['allowed_for_bias']}, "
                         f"candidate_hypotheses={candidates!r}")
            lines.append(f"  - {row['bias_reason']}")
        lines.append("")

    lines.append("## Columns by domain")
    lines.append("")
    generic_domain_rows = catalog.loc[
        (~catalog["region_only"]) & (catalog["domain"] != STAGE6_APPENDED_DOMAIN)
    ]
    for domain, group in generic_domain_rows.groupby("domain", sort=True):
        # Sort by national_position numerically, not by whatever dtype the caller's `catalog`
        # happens to carry for that column. In `main()`'s own real call path this is always already
        # a numeric dtype (the fresh in-memory catalog build_catalog() returns), so this coercion is
        # a no-op there — but a caller that instead reads schema_catalog.csv back with
        # `keep_default_na=False` (the correct way to preserve a blank candidate_hypotheses cell;
        # see the region-only section's own comment above) gets national_position back as a STRING
        # column, because frac_inside_aoi's blank national_position cell prevents the whole column
        # from being inferred as numeric. Sorting that column as-is would silently reorder every
        # domain table lexicographically ("10" sorting before "9") rather than raising any error —
        # exactly the kind of silent corruption this project's review passes exist to catch, found
        # by tests/test_data_dictionary.py's cross-file consistency check.
        group = group.sort_values("national_position", key=lambda s: pd.to_numeric(s, errors="coerce"))
        lines.append(f"### {domain} ({len(group)} columns)")
        lines.append("")
        lines.append(
            "| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for _, row in group.iterrows():
            pct_null = row["pct_null"]
            # Defensive, not just pd.notna(): a `keep_default_na=False` read (the correct way to
            # preserve a blank candidate_hypotheses cell — see the region-only section's comment
            # above) turns a blank pct_null cell into the empty STRING "", which pd.notna() treats
            # as present, not missing, and `f"{pct_null:.1%}"` then raises ValueError on a str. This
            # loop no longer receives Stage 6's blank-pct_null rows (excluded above), but this is a
            # correctness fix in its own right, not just a workaround for that exclusion.
            try:
                pct_null_str = f"{float(pct_null):.1%}"
            except (TypeError, ValueError):
                pct_null_str = ""
            candidates = row["candidate_hypotheses"] if pd.notna(row["candidate_hypotheses"]) else ""
            lines.append(
                f"| `{row['column_name']}` | `{row['source_table']}` | {row['dtype']} | {row['role']} "
                f"| {row['allowed_for_scoring']} | {row['allowed_for_bias']} | {candidates} "
                f"| {pct_null_str} | {row['vintage_status']} |"
            )
        lines.append("")

    return "\n".join(lines)


# -------------------------------------------------------------------------------------------
# Thin, network-touching wrapper
# -------------------------------------------------------------------------------------------


def read_frac_inside_aoi_column(
    filesystem: FileSystem, region: str, *, path_fn=strata_s3_path
) -> pd.Series:
    """Column-pruned read of one region's `frac_inside_aoi` column (plus GEOID, dropped again
    immediately — read only to keep the parquet reader's column-selection code path identical to
    every other loader in this project, which always reads GEOID alongside any attribute column).
    `path_fn` defaults to the real `src.config.strata_s3_path`; pass an override to test without a
    real S3 path — the same early-binding note as every other wrapper in this project applies (a
    monkeypatch of the imported name after this module loads will NOT affect a call that omits
    `path_fn=`)."""
    path = path_fn(region, STRATA_REGION_JOINED_TABLE)
    table = pq.read_table(path, filesystem=filesystem, columns=[STRATA_KEY_COLUMN, FRAC_INSIDE_AOI_COLUMN])
    return table.to_pandas()[FRAC_INSIDE_AOI_COLUMN]


# -------------------------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------------------------


def _load_csv_or_exit(path: Path, hint: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        print(f"ERROR: {path} not found. {hint}", file=sys.stderr)
        sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-output", type=Path, default=DEFAULT_CATALOG_OUTPUT_PATH)
    parser.add_argument("--dictionary-output", type=Path, default=DEFAULT_DICTIONARY_OUTPUT_PATH)
    parser.add_argument(
        "--skip-live-read",
        action="store_true",
        help="Skip the live frac_inside_aoi read (for offline smoke-testing); the region-only row "
        "is still produced, with its numeric fields left blank.",
    )
    args = parser.parse_args(argv)

    national_schema_csv = _load_csv_or_exit(
        DEFAULT_NATIONAL_SCHEMA_PATH, "Run scripts/inspect_national_strata_schema.py first (Step 1)."
    )
    domain_map = _load_csv_or_exit(
        DEFAULT_DOMAIN_MAP_PATH, "Run scripts/map_column_domains.py first (Step 2)."
    )
    null_profile = _load_csv_or_exit(
        DEFAULT_NULL_PROFILE_PATH, "Run scripts/profile_coverage_and_nulls.py first (Step 3)."
    )
    classification = _load_csv_or_exit(
        DEFAULT_CLASSIFICATION_PATH, "Run scripts/classify_columns.py first (Step 5)."
    )
    candidate_hypotheses = _load_csv_or_exit(
        DEFAULT_CANDIDATE_HYPOTHESES_PATH, "Run scripts/tag_candidate_hypotheses.py first (Step 6)."
    )
    region_consistency = _load_csv_or_exit(
        DEFAULT_REGION_CONSISTENCY_PATH,
        "Run scripts/check_region_national_schema_consistency.py first (Step 7).",
    )

    try:
        national_columns = load_national_joined_columns(national_schema_csv)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    region_presence = summarize_region_presence(region_consistency)

    combined_profile = {"n_rows": 0, "n_null": 0, "pct_null": float("nan"), "n_distinct": 0, "min": float("nan"), "max": float("nan"), "mean": float("nan")}
    regions_included: list[str] = []
    if not args.skip_live_read:
        print("Reading frac_inside_aoi live from all four regions (column-pruned)...")
        filesystem = S3FileSystem(anonymous=True, region=S3_REGION)
        series_by_region = []
        failed_regions: list[str] = []
        for region in REGIONS:
            # Per-region isolation, the same discipline Steps 1/7 already use: one region's read
            # failing (network hiccup, a genuinely missing file) must not crash the other three and
            # leave this step with NO output at all — it should be excluded, loudly, from the
            # combined profile instead. read_frac_inside_aoi_column itself does no error-wrapping of
            # its own (unlike src/io.py's loaders), so that isolation has to happen here.
            try:
                series = read_frac_inside_aoi_column(filesystem, region)
            except Exception as exc:  # noqa: BLE001 — reported, not swallowed; isolates this region only
                print(f"  ERROR reading {region}: {exc}", file=sys.stderr)
                failed_regions.append(region)
                continue
            print(f"  {region}: {len(series):,} row(s)")
            series_by_region.append(series)
            regions_included.append(region)

        if not series_by_region:
            print(
                "ERROR: frac_inside_aoi could not be read from ANY region — aborting without "
                "writing output.",
                file=sys.stderr,
            )
            return 1

        combined_series = pd.concat(series_by_region, ignore_index=True)
        combined_profile = profile_series(combined_series)
        if failed_regions:
            print(
                f"  WARNING: {len(failed_regions)} region(s) failed to load and are EXCLUDED from "
                f"the combined profile below: {failed_regions}"
            )
        print(f"  combined ({len(regions_included)}/{len(REGIONS)} region(s)): {combined_profile}")
    else:
        print("--skip-live-read set: frac_inside_aoi row will have blank numeric fields.")

    catalog_columns_template = (
        list(national_columns.columns)
        + ["source_table", "domain", "attribution_method"]
        + ["n_null", "pct_null", "n_distinct", "min", "max", "mean", "sentinel_note"]
        + ["role", "allowed_for_scoring", "scoring_reason", "allowed_for_bias", "bias_reason"]
        + ["candidate_hypotheses", "candidate_hypotheses_reason"]
        + ["present_in_regions", "missing_from_regions", "present_in_all_four_regions"]
        + ["region_only", "profile_scope", "vintage_status", "vintage_note"]
    )
    frac_inside_aoi_row = build_frac_inside_aoi_row(
        catalog_columns_template, combined_profile, regions_included=regions_included
    )

    catalog = build_catalog(
        national_columns,
        domain_map,
        null_profile,
        classification,
        candidate_hypotheses,
        region_presence,
        frac_inside_aoi_row,
    )

    args.catalog_output.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(args.catalog_output, index=False)
    print(f"Wrote {len(catalog)} row(s) to {args.catalog_output}")

    dictionary_markdown = render_data_dictionary_markdown(catalog)
    args.dictionary_output.parent.mkdir(parents=True, exist_ok=True)
    args.dictionary_output.write_text(dictionary_markdown, encoding="utf-8")
    print(f"Wrote {args.dictionary_output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
