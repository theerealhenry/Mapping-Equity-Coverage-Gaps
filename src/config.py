"""
Shared constants for the Bias Bounty Mapping Equity Challenge pipeline.

Centralises the data package layout (bucket paths, region names, layer names) and the fixed
component definitions used to compute the coverage gap score, so every script/notebook in this
repository reads from a single source of truth instead of re-typing paths or class lists.
"""

from __future__ import annotations

# --- Data package location -------------------------------------------------------------------
# Public bucket, no credentials required. Two equivalent access routes; HTTPS is used for
# DuckDB reads, the s3:// path (without scheme) for pyarrow/geopandas anonymous S3 reads.
ORG = "humane-intelligence"
PRODUCT = "bias-bounty-mapping-equity-challenge"
ROOT = f"{ORG}/{PRODUCT}"

HTTPS_BASE = f"https://data.source.coop/{ROOT}"
S3_BUCKET = "us-west-2.opendata.source.coop"
S3_REGION = "us-west-2"

# Overture Maps release this project computes against. Do not compute against any other release;
# the reference scores are pinned to this one.
OVERTURE_RELEASE = "2026-08-19.0"

# --- Reproducibility ------------------------------------------------------------------------------
# Single source of truth for every stochastic operation in this project: Optuna's sampler (Stage 8),
# the explanatory model's train/validation split and any stochastic clustering init (Stage 8),
# and the bootstrap/permutation tests used in statistical confirmation (Stage 9). Every module that
# needs randomness imports SEED from here rather than hardcoding its own value, so a single change
# in one place reseeds the entire project consistently. This module intentionally stays
# dependency-free (stdlib only) — seeding itself (`random.seed(SEED)`, `np.random.seed(SEED)`, an
# Optuna `TPESampler(seed=SEED)`, etc.) happens in whichever module actually uses that library, not
# here, so importing `src.config` for a constant never forces numpy/optuna to load.
SEED = 42

# --- Study regions -----------------------------------------------------------------------------
REGIONS = ["maricopa-az", "northern-ca", "eastern-ok", "south-central-tx"]

# Scored tract counts per region (the count of rows in each region's sample-submission.csv,
# i.e. tracts with at least one scorable component). Used as a sanity check after loading data.
SCORED_TRACT_COUNTS = {
    "maricopa-az": 1593,
    "northern-ca": 591,
    "eastern-ok": 1192,
    "south-central-tx": 6003,
}

# Total tract membership per region (before dropping unscorable tracts), from
# boundaries/<region>-tract-geoids.csv.
REGION_TRACT_COUNTS = {
    "maricopa-az": 1593,
    "northern-ca": 591,
    "eastern-ok": 1192,
    "south-central-tx": 6010,
}

# Maricopa's package includes one New Mexico tract at the state line (Hidalgo County, Tract 9700).
MARICOPA_NM_TRACT_GEOID = "35023970000"

# --- Reference layer filenames (reference/<region>/<region>-<LAYER>.parquet) -------------------
LAYER_OVERTURE_BUILDINGS = "overture-buildings"
LAYER_OVERTURE_ROADS = "overture-roads"
LAYER_OVERTURE_ROADS_UNFILTERED = "overture-roads-unfiltered"
LAYER_OVERTURE_RAIL = "overture-rail"
LAYER_OVERTURE_INFRASTRUCTURE = "overture-infrastructure"
LAYER_OVERTURE_POIS = "overture-pois"

LAYER_MICROSOFT_BUILDINGS = "microsoft-buildings"
LAYER_CENSUS_ACS_HOUSING = "census-acs-housing"
LAYER_CENSUS_TIGER_ROADS = "census-tiger-roads"
LAYER_CENSUS_CBP = "census-cbp"
LAYER_HIFLD_HOSPITALS = "hifld-hospitals"
LAYER_HIFLD_FIRE_STATIONS = "hifld-fire-stations"
LAYER_HIFLD_EMS_STATIONS = "hifld-ems-stations"
LAYER_HIFLD_SCHOOLS = "hifld-schools"

SAMPLE_SUBMISSION_SUFFIX = "sample-submission.csv"

# --- Coverage gap component definitions ---------------------------------------------------------
# Road gap: TIGER named-highway classes vs. Overture named-highway classes. NOT comparable
# across regions (the two sources draw the primary/secondary boundary differently, ratio 0.71-1.59
# across the four regions).
TIGER_NAMED_HIGHWAY_MTFCC = ("S1100", "S1200")
OVERTURE_NAMED_HIGHWAY_CLASSES = ("motorway", "trunk", "primary", "secondary")

# POI gap, facilities half: Overture places matched to HIFLD/USGS facility layers by
# categories.primary. Hospitals are deliberately excluded (Overture over-counts ~12x, so that
# term never shows a deficit).
POI_FACILITY_CATEGORY_MAP = {
    "fire": ("fire_department",),
    "ems": ("ambulance_and_ems_services",),
    "schools": (
        "elementary_school",
        "middle_school",
        "high_school",
        "school",
        "private_school",
        "public_school",
    ),
}

# CBP establishment weighting: business-address share is the default/documented choice.
CBP_ESTAB_COLUMN_DEFAULT = "cbp_estab_bus"
CBP_ESTAB_COLUMN_RESIDENTIAL = "cbp_estab_res"

# --- Strata (bias-analysis) tables --------------------------------------------------------------
STRATA_NATIONAL_JOINED_TABLE = "national-strata-tract-table"
STRATA_KEY_COLUMN = "GEOID"

# Bare table name of each region's own pre-joined strata table (Stage 3 Step 7 confirms, live,
# whether its schema actually matches STRATA_NATIONAL_JOINED_TABLE's — see docs/data_manifest.csv:
# every region's strata/ folder ships a "<region>-strata-tract-table.parquet" alongside its 22-23
# individual source tables, confirmed present in all four regions including South-Central Texas,
# which is otherwise missing one unrelated table, census-tribal-subdivisions). Pass this as the
# `table` argument to strata_s3_path/strata_url — e.g.
# strata_s3_path("eastern-ok", STRATA_REGION_JOINED_TABLE) -> ".../strata/eastern-ok/eastern-ok-
# strata-tract-table.parquet".
STRATA_REGION_JOINED_TABLE = "strata-tract-table"

# The 25 other tables under strata/national/ that STRATA_NATIONAL_JOINED_TABLE is built by joining
# together — confirmed directly (Stage 3 Step 1) against the real `docs/data_manifest.csv` object
# listing, not assumed from PROJECT_BLUEPRINT.md's domain-name prose ("population, SVI, CVI,
# rurality, heat, wildfire, drought, and tribal"). 21 of these 25 ship as both `.csv` and `.parquet`
# (48 objects total across all 26 tables including the joined one, matching Section 3's "strata/
# national/ holds 48 objects"); the 4 marked below ship parquet-only, which is itself a real,
# confirmed fact worth carrying into Stage 3's dictionary (they read as tract-boundary/membership
# files, not attribute tables with an obvious CSV-friendly flat shape). Each name is the exact base
# filename `strata_national_url`/`strata_national_s3_path` expect (no extension, "national-" prefix
# included), the same convention STRATA_NATIONAL_JOINED_TABLE already uses.
NATIONAL_STRATA_SOURCE_TABLES = (
    "national-carbonplan-tract-table",
    "national-cdc-wonder-heat-mortality",
    "national-cdc-wonder-tract-table",
    "national-census-aiannh",  # parquet-only
    "national-census-tract-table",
    "national-census-tracts",  # parquet-only
    "national-census-tribal-subdivisions",  # parquet-only
    "national-census-tribal-tracts",  # parquet-only
    "national-cvi-tract-table",
    "national-drought-gov-tract-table",
    "national-epht-heat-tract-table",
    "national-fpa-fod-tract-table",
    "national-mtbs-tract-table",
    "national-nasa-heat-tract-table",
    "national-nchs-tract-table",
    "national-nifc-tract-table",
    "national-noaa-ghcn-stations",
    "national-noaa-ghcn-tract-table",
    "national-ruca-tract-table",
    "national-rucc-tract-table",
    "national-svi-tract-table",
    "national-tribal-tract-table",
    "national-usdm-drought-tract-table",
    "national-usfs-wildfire-tract-table",
    "national-usgs-combined-tract-table",
)


def reference_url(region: str, layer: str, base: str = HTTPS_BASE) -> str:
    """HTTPS URL for a reference-package parquet file, for DuckDB / pandas over-the-wire reads."""
    return f"{base}/reference/{region}/{region}-{layer}.parquet"


def reference_s3_path(region: str, layer: str) -> str:
    """s3:// path (no scheme) for a reference-package parquet file, for anonymous S3FileSystem reads."""
    return f"{S3_BUCKET}/{ROOT}/reference/{region}/{region}-{layer}.parquet"


def strata_url(region: str, table: str, base: str = HTTPS_BASE) -> str:
    """HTTPS URL for a per-region strata table."""
    return f"{base}/strata/{region}/{region}-{table}.parquet"


def strata_s3_path(region: str, table: str) -> str:
    """s3:// path (no scheme) for a per-region strata parquet file, for anonymous S3FileSystem
    reads. Added alongside reference_s3_path (Stage 2 Step 4, src/io.py) so strata tables can be
    read through the same geopandas/pyarrow path as reference layers, rather than introducing a
    second read mechanism (DuckDB/httpfs) into io.py just for this one table family — DuckDB stays
    reserved for Stage 6's heavy joins/aggregations, per PROJECT_BLUEPRINT.md's tools table."""
    return f"{S3_BUCKET}/{ROOT}/strata/{region}/{region}-{table}.parquet"


def strata_national_url(table: str, base: str = HTTPS_BASE) -> str:
    """HTTPS URL for a national strata table (source of truth, 85,396 tracts)."""
    return f"{base}/strata/national/{table}.parquet"


def strata_national_s3_path(table: str) -> str:
    """s3:// path (no scheme) for a national strata parquet file, for anonymous S3FileSystem
    reads. See strata_s3_path's docstring for why this exists alongside strata_national_url."""
    return f"{S3_BUCKET}/{ROOT}/strata/national/{table}.parquet"


def sample_submission_url(region: str, base: str = HTTPS_BASE) -> str:
    return f"{base}/reference/{region}/{region}-{SAMPLE_SUBMISSION_SUFFIX}"
