"""
src/io.py — Stage 2, Step 4.

The single place every layer this project reads is actually loaded from disk/the bucket. Every
public loader in this module composes the same three steps, in the same order, every time:

  1. Read the raw GeoParquet/CSV (via geopandas/pyarrow, anonymous S3 by default).
  2. `src.geometry.normalize_geographic_crs` — the geometry column comes out tagged exactly
     `OGC:CRS84`, never left ambiguous between that and `EPSG:4326` (Stage 2 Step 2).
  3. `src.schemas.validate_layer` — the attribute columns are checked against their pandera
     contract (Stage 2 Step 3), for layer types that have one.

Pipeline code (Stage 5 onward) should always go through this module rather than calling
`geopandas.read_parquet`/`pandas.read_csv` directly — that is the entire point of Gate A ("no
pipeline code runs against real data until... every layer's pandera schema contract passes"): a
loader that skips step 2 or step 3 would defeat Stage 2's work silently, the same class of failure
this whole stage exists to prevent.

Scope: this module loads whole layers, schema-checked, for the seven reference layer types
`src/schemas.py` currently covers, plus strata tables and the sample-submission CSV (see below).
It deliberately does NOT do column or bbox pushdown / partial reads — reading a subset of a
layer's columns would make full-schema validation (several of `src/schemas.py`'s schemas are
`strict=True`, requiring every documented column) meaningless to run against the partial result.
Column/bbox-pushdown, chunked/batched reads for the largest layers (south-central-tx's ~11.5M-row
`overture-buildings`, confirmed in `docs/data_manifest.md` Section 4.5), and the heavy spatial
joins/aggregations themselves are Stage 6's job, explicitly reserved for DuckDB per
PROJECT_BLUEPRINT.md's tools table — not this module's.

CRS handling note: `src.geometry.normalize_geographic_crs` (called by every loader below) raises
if a layer's CRS comes back as `None` after reading — deliberately strict, per Stage 2 Step 2. This
was verified directly before relying on it here, not merely assumed: `geopandas.read_parquet`
correctly resolves a file whose GeoParquet metadata OMITS the `crs` key entirely (the actual
spec-compliant way to declare "implied default = CRS84") to `OGC:CRS84` automatically — confirmed
against a hand-built fixture with the key removed. `.crs` only comes back `None` for a file whose
metadata explicitly carries a literal `"crs": null`, which is not what a spec-conformant producer
does when omitting the field, and is the only real scenario in which `load_reference_layer`'s
`normalize_geographic_crs` call would legitimately raise on real data. If that ever happens against
the live bucket, it is a genuinely notable finding about the data package worth its own entry in
`docs/data_manifest.md`, not evidence this module is broken.

`load_sample_submission`'s HTTPS read works through `pandas.read_csv` alone via Python's stdlib
`urllib` — this project's `requirements.txt` does not pin `requests` or `fsspec`, and a request
against an unreachable HTTPS URL was confirmed to fail with a genuine network error
(`urllib.error.URLError`), not an import/dependency error, so no new dependency is needed here.
**Update, Stage 2 Step 7**: a real run against the live bucket hit `HTTPError: HTTP Error 403:
Forbidden` — confirmed directly to be this bucket's HTTPS front end rejecting `pandas.read_csv`'s
default plain-urllib User-Agent specifically (`Python-urllib/x.y`), not a broken URL or a genuine
access restriction, since the identical URL fetched with an ordinary browser-like client returned
the CSV normally. `load_reference_layer`/`load_strata_table` were never affected by this because
they read via anonymous S3, a different transport that never goes through urllib. Fixed by sending
a custom `User-Agent` (`_SAMPLE_SUBMISSION_USER_AGENT`) via `pandas.read_csv`'s `storage_options`
argument — still no new dependency, `storage_options` is threaded straight into
`urllib.request.Request`'s own `headers` argument by pandas' plain-urllib code path.

Strata tables and the sample-submission CSV are NOT covered by a `src/schemas.py` pandera schema
(Stage 2 Step 3 scoped exactly the seven reference layer types PROJECT_BLUEPRINT.md names, not
these) — loading them here does NOT run full-schema validation, only the same GEOID-dtype guard
this module applies everywhere a GEOID column is expected (see `_assert_geoid_is_string`). This is
a deliberate, documented scope boundary, not an oversight: claiming these are pandera-validated
when they are not would overstate what Stage 2 actually confirmed, the same discipline
`src/schemas.py` applies to its own scope. If a strata pandera schema is added later, it belongs
in `src/schemas.py`'s registry and this module's strata loaders should start calling it, the same
way the reference-layer loader already does.
"""

from __future__ import annotations

import functools

import geopandas as gpd
import pandas as pd
from pyarrow.fs import FileSystem, FileType, S3FileSystem

from src.config import (
    REGIONS,
    S3_REGION,
    STRATA_KEY_COLUMN,
    reference_s3_path,
    sample_submission_url,
    strata_national_s3_path,
    strata_s3_path,
)
from src.geometry import normalize_geographic_crs
from src.schemas import validate_layer

EXPECTED_SAMPLE_SUBMISSION_COLUMNS = frozenset(
    {STRATA_KEY_COLUMN, "transport_gap", "building_gap", "poi_gap", "coverage_gap_score"}
)
"""Confirmed in docs/data_manifest.md Section 4.2 — the per-region bucket-hosted sample-submission
CSV's real column set (distinct from the Zindi platform's 17-column upload template, which this
module does not read). Presence-checked, not a full pandera schema — see the module docstring."""

_SAMPLE_SUBMISSION_USER_AGENT = "bias-bounty-mapping-equity/1.0 (+https://data.source.coop)"
"""Sent as the User-Agent header on a real HTTP(S) `load_sample_submission` read only — see that
function's docstring for why: this bucket's HTTPS front end was confirmed to return `403
Forbidden` for pandas.read_csv's default plain-urllib User-Agent, while the same URL succeeds with
an ordinary, identifiable client string. Any descriptive, non-default value is sufficient; this one
is not required to match a specific format by the bucket, it just needs to not look like the
default `Python-urllib/x.y` the front end appears to be blocking."""


# -------------------------------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _s3_filesystem() -> S3FileSystem:
    """The real, anonymous, us-west-2 S3 filesystem every public loader below reads through by
    default. Constructed lazily and cached (not at import time, not per call) so importing this
    module never itself attempts a connection, and repeated loads in the same process reuse one
    filesystem object rather than constructing a new one every call."""
    return S3FileSystem(anonymous=True, region=S3_REGION)


def _require_known_region(region: str) -> None:
    """Fails fast with the exact set of valid regions, rather than letting an invalid region
    silently build a path to an object that doesn't exist and fail later with a confusing
    file-not-found error two layers of abstraction away from the actual mistake."""
    if region not in REGIONS:
        raise ValueError(f"Unknown region {region!r}. Valid regions: {REGIONS}.")


def _read_geoparquet(filesystem: FileSystem, path: str, *, context: str) -> gpd.GeoDataFrame:
    """Core GeoParquet read, factored out from every public loader below so it can be tested
    against a local fixture file/filesystem (`pyarrow.fs.LocalFileSystem`) without needing network
    access — the same testable-core / thin-real-path-wrapper pattern used throughout this
    project's scripts (see scripts/inspect_overture_sources.py's `inspect_sources_at_path`).

    Wraps whatever pyarrow/geopandas raise into a message that names the layer/path being loaded
    (`context`) — a bare `FileNotFoundError: [Errno 2] ...` with no indication of which of this
    project's dozens of layer files was being read is not an actionable error.

    Missing-file detection deliberately does NOT rely on catching `FileNotFoundError` around the
    read call itself: that assumes pyarrow's S3 backend raises exactly that exception type for a
    missing key, which was only ever confirmed against `pyarrow.fs.LocalFileSystem` (this
    project's automated tests have no network access to verify the S3 backend directly) and is not
    documented as guaranteed by pyarrow. Instead this calls `filesystem.get_file_info(path)`
    first — the one part of pyarrow's filesystem interface whose missing-path behavior IS
    documented as backend-agnostic ("a non-existing or unreachable file returns a FileStat object
    ... FileType of value NotFound", not an exception) — and raises `FileNotFoundError` itself,
    deterministically, before ever attempting the read. This matters concretely: callers of
    `load_strata_table` are explicitly told to catch `FileNotFoundError` for the real,
    already-confirmed case of south-central-tx missing `census-tribal-subdivisions.parquet`
    (`docs/data_manifest.md` Section 3) — that contract has to hold against the real S3 backend on
    Henry's machine, not just against the LocalFileSystem fixtures this module's own tests use."""
    info = filesystem.get_file_info(path)
    if info.type == FileType.NotFound:
        raise FileNotFoundError(f"{context}: no object found at {path!r}")
    try:
        return gpd.read_parquet(path, filesystem=filesystem)
    except Exception as exc:  # noqa: BLE001 — re-raised with context, not swallowed
        raise RuntimeError(f"{context}: failed to read GeoParquet at {path!r}: {exc}") from exc


def _assert_geoid_is_string(df: pd.DataFrame, *, context: str) -> None:
    """Guards the one most-documented, most-consequential pitfall in this whole project
    (`docs/risk_register.md`'s GEOID-as-integer entry, `docs/data_manifest.md` Section 4.3): an
    integer GEOID column has already silently dropped a leading-zero state FIPS by the time it
    reaches this function — Maricopa's "04..." becomes "4...", corrupting every downstream tract
    join. Applied everywhere a `STRATA_KEY_COLUMN` ("GEOID") column is expected but is not already
    covered by a `src/schemas.py` pandera contract (CBP's GEOID is — see
    `_fixed_digit_string_column` there; this is io.py's equivalent guard for strata tables and the
    sample-submission CSV, neither of which has a pandera schema yet — see the module docstring).

    A no-op if `STRATA_KEY_COLUMN` is not present in `df` at all — some strata tables may
    legitimately not carry a GEOID column; that is a presence question for the caller, not this
    function's concern."""
    if STRATA_KEY_COLUMN not in df.columns:
        return
    if not pd.api.types.is_string_dtype(df[STRATA_KEY_COLUMN]):
        raise ValueError(
            f"{context}: {STRATA_KEY_COLUMN!r} column has dtype "
            f"{df[STRATA_KEY_COLUMN].dtype!r}, expected a string dtype. An integer GEOID has "
            "already silently lost a leading-zero state FIPS by this point (e.g. Maricopa's "
            "'04...' becomes '4...'), corrupting every downstream tract join — this must be fixed "
            "at the source, not coerced here."
        )


# -------------------------------------------------------------------------------------------
# Public loaders
# -------------------------------------------------------------------------------------------


def load_reference_layer(
    region: str, layer: str, *, filesystem: FileSystem | None = None
) -> gpd.GeoDataFrame:
    """Loads `reference/<region>/<region>-<layer>.parquet`, CRS-normalized (Stage 2 Step 2) and
    schema-validated (Stage 2 Step 3). This is the ONLY sanctioned way pipeline code should read a
    reference layer — see the module docstring.

    Raises `ValueError` for an unknown `region`, `FileNotFoundError`/`RuntimeError` (wrapped, with
    context) for a read failure, `ValueError` for a CRS this project's data is not expected to be
    in (`src.geometry.normalize_geographic_crs`), and `NotImplementedError` for a `layer` with no
    registered pandera schema yet (`src.schemas.validate_layer`) — none of these are caught here;
    they are meant to stop the caller, per Gate A's "fail loudly" design.

    `filesystem` defaults to the real anonymous S3 filesystem; overriding it (e.g. with a
    `pyarrow.fs.LocalFileSystem` pointed at a fixture) is how this function is tested without
    network access — production callers should never need to pass this.
    """
    _require_known_region(region)
    fs = filesystem if filesystem is not None else _s3_filesystem()
    path = reference_s3_path(region, layer)
    gdf = _read_geoparquet(fs, path, context=f"load_reference_layer({region!r}, {layer!r})")
    gdf = normalize_geographic_crs(gdf)
    gdf = validate_layer(gdf, layer)
    return gdf


def load_strata_table(
    region: str, table: str, *, filesystem: FileSystem | None = None
) -> gpd.GeoDataFrame:
    """Loads `strata/<region>/<region>-<table>.parquet`, CRS-normalized and GEOID-dtype-guarded
    (see `_assert_geoid_is_string`) but NOT pandera-schema-validated — see the module docstring
    for why that is a deliberate scope boundary, not an oversight.

    Raises `ValueError` for an unknown `region` or a GEOID dtype violation,
    `FileNotFoundError`/`RuntimeError` for a read failure — including the documented,
    already-confirmed case of `south-central-tx-census-tribal-subdivisions.parquet` genuinely not
    existing (`docs/data_manifest.md` Section 3): callers loading a strata table that is not
    guaranteed to exist in every region must check for that themselves (e.g. by catching
    `FileNotFoundError`), this function does not silently paper over a missing file.
    """
    _require_known_region(region)
    fs = filesystem if filesystem is not None else _s3_filesystem()
    path = strata_s3_path(region, table)
    gdf = _read_geoparquet(fs, path, context=f"load_strata_table({region!r}, {table!r})")
    gdf = normalize_geographic_crs(gdf)
    _assert_geoid_is_string(gdf, context=f"load_strata_table({region!r}, {table!r})")
    return gdf


def load_strata_national_table(
    table: str, *, filesystem: FileSystem | None = None
) -> gpd.GeoDataFrame:
    """Loads `strata/national/<table>.parquet` (the 85,396-tract national source of truth),
    CRS-normalized and GEOID-dtype-guarded — otherwise identical in behavior to
    `load_strata_table`, see its docstring."""
    fs = filesystem if filesystem is not None else _s3_filesystem()
    path = strata_national_s3_path(table)
    gdf = _read_geoparquet(fs, path, context=f"load_strata_national_table({table!r})")
    gdf = normalize_geographic_crs(gdf)
    _assert_geoid_is_string(gdf, context=f"load_strata_national_table({table!r})")
    return gdf


def load_sample_submission(region: str, *, url: str | None = None) -> pd.DataFrame:
    """Loads `reference/<region>/<region>-sample-submission.csv` — the region's manifest of which
    GEOIDs must be scored (docs/data_manifest.md Section 4.2; NOT the Zindi platform's 17-column
    upload template, which this function does not read). GEOID is forced to string dtype at read
    time (`dtype={STRATA_KEY_COLUMN: str}`) rather than guarded after the fact, since
    `pandas.read_csv` — unlike a GeoParquet's already-typed columns — would otherwise infer an
    all-digit GEOID column as int64 by default; `_assert_geoid_is_string` still runs afterward as
    a second, independent check rather than trusting the dtype= argument alone.

    Raises `ValueError` for an unknown `region`, a GEOID dtype violation, or a response missing
    any of `EXPECTED_SAMPLE_SUBMISSION_COLUMNS`; `RuntimeError` (wrapped, with context) for a read
    failure.

    `url` defaults to the real bucket URL for `region`; overriding it (a local CSV path) is how
    this function is tested without network access.

    A real HTTP(S) read sends a custom `User-Agent` header (see `_SAMPLE_SUBMISSION_USER_AGENT`
    below) — confirmed necessary directly against a genuine failure: `pandas.read_csv`'s default
    plain-`urllib` request (User-Agent `Python-urllib/3.x`) was rejected by this bucket's HTTPS
    front end with `HTTPError: HTTP Error 403: Forbidden`, while the identical URL fetched with an
    ordinary browser-like User-Agent returned the CSV normally — a front-end/CDN policy blocking
    the default urllib client identity, not a broken URL, missing file, or genuine access
    restriction (`load_reference_layer`/`load_strata_table` are unaffected because they read via
    anonymous S3, a completely different transport that never goes through urllib at all). The
    header is applied only when `resolved_url` is an actual http(s) URL: confirmed directly that
    passing `storage_options` for a local file path raises `ValueError: storage_options passed
    with file object or non-fsspec file path` in this project's pinned pandas version, which would
    otherwise break every existing test in `tests/test_io.py` that calls this function with a
    local `url=` fixture path instead of the real bucket URL.
    """
    _require_known_region(region)
    resolved_url = url if url is not None else sample_submission_url(region)
    context = f"load_sample_submission({region!r})"
    read_kwargs: dict = {"dtype": {STRATA_KEY_COLUMN: str}}
    if resolved_url.startswith(("http://", "https://")):
        read_kwargs["storage_options"] = {"User-Agent": _SAMPLE_SUBMISSION_USER_AGENT}
    try:
        df = pd.read_csv(resolved_url, **read_kwargs)
    except Exception as exc:  # noqa: BLE001 — re-raised with context, not swallowed
        raise RuntimeError(f"{context}: failed to read sample-submission CSV at {resolved_url!r}: {exc}") from exc

    missing = EXPECTED_SAMPLE_SUBMISSION_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"{context}: sample-submission CSV at {resolved_url!r} is missing expected column(s) "
            f"{sorted(missing)}. Present columns: {list(df.columns)}."
        )
    _assert_geoid_is_string(df, context=context)
    return df
