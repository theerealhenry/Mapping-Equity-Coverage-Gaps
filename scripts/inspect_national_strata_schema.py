"""
scripts/inspect_national_strata_schema.py — Stage 3, Step 1.

Direct, footer-only schema inspection of `national-strata-tract-table.parquet` (the joined national
strata table Stage 3's data dictionary is built from) and every one of the 25 other tables under
`strata/national/` it is assembled from (`src.config.NATIONAL_STRATA_SOURCE_TABLES`). This is the
raw material every later Stage 3 step works from — column-to-domain mapping (Step 2), coverage/
null-semantics profiling (Step 3), and the final `docs/DATA_DICTIONARY.md`/`docs/schema_catalog.csv`
build (Step 8) all start from the exact, confirmed column list this script produces, not from
PROJECT_BLUEPRINT.md's "232 columns spanning population, SVI, CVI, rurality, heat, wildfire,
drought, and tribal domains" prose description.

Uses `pq.ParquetFile(path, filesystem=...).schema_arrow` — reads only the parquet footer, never the
actual column data — the same technique already proven in `scripts/inspect_overture_sources.py` and
`scripts/verify_bucket.py`. No full download, no row-level read, safe to run against every one of
the 26 tables (including `national-strata-tract-table` itself, whose row count is not yet directly
confirmed by this project — `src/io.py`'s docstring cites "85,396 tracts" for the national strata
tables in general, but that specific figure has not yet been re-verified against this exact table by
this script; this run is also that re-verification).

Deliberately inspects only each table's `.parquet` form, not its `.csv` sibling (21 of the 26 tables
ship both, per `docs/data_manifest.csv`) — every loader this project has (`src/io.py`) reads
Parquet, and a CSV re-export of the same table is not expected to carry different columns; if this
script's per-region Stage 6 successor ever needs to cross-check that assumption, it is a one-line
addition, not a redesign, since `inspect_table_schema` takes an arbitrary path and doesn't care
which format it names.

Design: the same testable-core / thin-real-path-wrapper pattern used throughout this project's
scripts (see `scripts/inspect_overture_sources.py`'s `inspect_sources_at_path`,
`scripts/audit/audit_bucket.py`'s pure core functions). `inspect_table_schema` takes an already-
constructed filesystem and a path — no network-specific setup — so it is directly unit-testable
against a local parquet fixture (`tests/test_inspect_national_strata_schema.py`) without needing
S3 access. `inspect_national_table` is the one-line wrapper that supplies the real bucket path via
`src.config.strata_national_s3_path`.

Deliberately read-only and non-blocking on a single table's failure: one missing or malformed table
must not prevent every other table's schema from being reported — the same reasoning
`scripts/audit/audit_bucket.py`'s per-region/layer isolation already applies, here applied per
table instead of per region/layer.

Run with:
    python scripts/inspect_national_strata_schema.py

Writes `docs/national_strata_schema_raw.csv` — one row per column for every table that inspected
successfully, PLUS one explicit sentinel row for any table that failed to inspect at all (an
`error_message` column, empty for a real column row, populated for a table-level failure) — so a
table's absence from this project's later Stage 3 steps is always because it was checked and
recorded as failed, never because it silently fell out of the file. Also prints a summary to
stdout, including four specific risk checks worth surfacing immediately rather than only left to a
human scanning 200+ CSV rows: any table missing an exact `GEOID` column, any table with a
plausible GEOID-like column under a DIFFERENT name/case (`geoid`, `GEOID10`, `FIPS`, ...) that a
case-sensitive exact match would otherwise silently miss, any table whose `GEOID` column is not a
string-like Arrow type (this project's single most-cited real risk — an integer GEOID silently
drops a leading-zero state FIPS, see `docs/risk_register.md`'s GEOID-as-integer entry and
`src/schemas.py`'s `_fixed_digit_string_column`), and any table with a duplicate column name in its
own schema (which would otherwise silently corrupt a naive `dict(columns)` lookup downstream).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pyarrow.fs import FileSystem, S3FileSystem

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import (  # noqa: E402
    NATIONAL_STRATA_SOURCE_TABLES,
    S3_REGION,
    STRATA_KEY_COLUMN,
    STRATA_NATIONAL_JOINED_TABLE,
    strata_national_s3_path,
)

DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "national_strata_schema_raw.csv"

# GEOID-like string Arrow types this project already treats as a safe, non-truncating GEOID dtype
# (see src/schemas.py's _fixed_digit_string_column, which requires plain `str`/`string` — never an
# int type). Kept narrow and explicit rather than "anything not an int type", since the point of
# this check is to flag exactly the failure mode already documented as this project's costliest
# real risk, not to pass judgment on every possible Arrow type.
_STRING_LIKE_ARROW_TYPES = frozenset({"string", "large_string", "string_view"})


# -------------------------------------------------------------------------------------------
# Pure core function — no I/O beyond the passed-in filesystem, fully unit-testable
# -------------------------------------------------------------------------------------------


def inspect_table_schema(filesystem: FileSystem, path: str, *, label: str = "") -> dict:
    """Footer-only schema inspection for one parquet table: column names/dtypes, in file order,
    plus the table's row count from parquet metadata (also footer-only — never reads column data).

    Returns a dict with `columns` (a list of `(name, arrow_dtype_str)` tuples, in schema order) and
    `num_rows` on success, or `error` (a string) if the table could not even be opened — a missing
    or malformed table is a real, expected possibility in this bucket (South-Central Texas is
    already confirmed, docs/data_manifest.md Section 3, to be missing a file every other region
    has), so this never raises: the caller decides what to do with an error, the same convention
    `scripts/audit/audit_bucket.py`'s pure core functions already use.
    """
    result: dict = {"label": label}
    try:
        pf = pq.ParquetFile(path, filesystem=filesystem)
    except Exception as exc:  # noqa: BLE001 — surfacing the failure is the point here
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    schema = pf.schema_arrow
    result["num_rows"] = pf.metadata.num_rows
    result["columns"] = [(schema.field(i).name, str(schema.field(i).type)) for i in range(len(schema.names))]
    return result


# -------------------------------------------------------------------------------------------
# Thin, network-touching wrapper
# -------------------------------------------------------------------------------------------


def inspect_national_table(
    filesystem: FileSystem, table: str, *, path_fn=strata_national_s3_path
) -> dict:
    """Inspects one `strata/national/<table>.parquet` file. `path_fn` defaults to the real
    `src.config.strata_national_s3_path`; overriding it is how this wrapper's path-construction
    logic is tested without needing a real S3 path to resolve.

    Note (the same early-binding gotcha `tests/test_audit_bucket.py`'s module docstring documents
    for `audit_bucket.py`'s `loader=` keyword): `path_fn`'s default is bound to
    `strata_national_s3_path` at function-DEFINITION time, an ordinary Python semantics fact —
    monkeypatching `scripts.inspect_national_strata_schema.strata_national_s3_path` after this
    module has been imported will NOT change what a call without an explicit `path_fn=` uses. Pass
    `path_fn=` explicitly to inject a fake, as every test in this file does; don't rely on
    monkeypatching the imported name."""
    path = path_fn(table)
    result = inspect_table_schema(filesystem, path, label=table)
    result["table"] = table
    result["key"] = path
    return result


# -------------------------------------------------------------------------------------------
# Risk checks — surfaced prominently, not just left to a human scanning 200+ CSV rows
# -------------------------------------------------------------------------------------------

_GEOID_ALIAS_HINTS = ("geoid", "fips")
"""Lower-cased substrings that make a column name a PLAUSIBLE GEOID alias worth a human's attention
— not a claim that it IS one. Across 26 tables sourced from CDC, NOAA, USFS, and the Census Bureau,
a differently-cased or differently-named key column (`geoid`, `GEOID10`, `FIPS`, `fips_code`) is a
real possibility, not a hypothetical: `STRATA_KEY_COLUMN`'s exact-case, exact-name match
(`missing_geoid` below) would silently miss every one of these. Deliberately broad (a substring
match, not a fixed alias list) since the point is to surface candidates for a human to check in
Step 2, not to guess which one is correct."""


def schema_risk_findings(results: list[dict]) -> dict:
    """Four specific, high-value checks across every successfully-inspected table's schema:

    - `missing_geoid`: no column named exactly `STRATA_KEY_COLUMN` ("GEOID"). Informational on its
      own — some national tables are legitimately indexed by something else entirely (e.g.
      `national-noaa-ghcn-stations`, station-indexed, not tract-indexed) — cross-check against
      `possible_geoid_alias` below before concluding a table has no usable key at all.
    - `possible_geoid_alias`: for tables in `missing_geoid`, any column whose lower-cased name
      contains a hint in `_GEOID_ALIAS_HINTS` — surfaced separately, not merged into
      `missing_geoid`, so "no key column at all" and "key column present under a different name"
      are never conflated into one ambiguous finding.
    - `unsafe_geoid_dtype`: an exact-match `GEOID` column that is NOT a safe string-like Arrow type
      — this project's single most-cited real risk (an integer GEOID silently drops a leading-zero
      state FIPS; see `docs/risk_register.md`'s GEOID-as-integer entry and `src/schemas.py`'s
      `_fixed_digit_string_column`).
    - `duplicate_column_names`: any table whose own schema repeats a column name. Checked
      explicitly, BEFORE the other three checks build a `dict(columns)` lookup for that table
      (which would otherwise silently collapse to the last occurrence and hide exactly this
      finding) — a table with this problem is excluded from the GEOID checks above entirely
      (reported here instead), rather than checked against a lookup already known to have thrown
      away information.

    Accepts either `"table"` (the real `inspect_national_table` wrapper's key) or `"label"` (the
    bare `inspect_table_schema` core function's key) per result dict, falling back to
    `"<unknown>"` rather than raising, since this is a reporting function that should never itself
    be the reason a run fails. Kept as a pure function over already-computed `results` so it's
    testable without re-running any I/O.
    """
    missing_geoid: list[str] = []
    possible_geoid_alias: dict[str, list[str]] = {}
    unsafe_geoid_dtype: dict[str, str] = {}
    duplicate_column_names: dict[str, list[str]] = {}

    for r in results:
        if "error" in r:
            continue
        name = r.get("table", r.get("label", "<unknown>"))
        column_names = [c[0] for c in r["columns"]]

        seen: set[str] = set()
        dupes: list[str] = []
        for c in column_names:
            if c in seen and c not in dupes:
                dupes.append(c)
            seen.add(c)
        if dupes:
            duplicate_column_names[name] = dupes
            continue  # a dict(columns) lookup below would be unreliable for this table — skip it

        columns = dict(r["columns"])
        if STRATA_KEY_COLUMN not in columns:
            missing_geoid.append(name)
            aliases = [
                c for c in column_names if any(hint in c.lower() for hint in _GEOID_ALIAS_HINTS)
            ]
            if aliases:
                possible_geoid_alias[name] = aliases
            continue

        dtype = columns[STRATA_KEY_COLUMN]
        if dtype not in _STRING_LIKE_ARROW_TYPES:
            unsafe_geoid_dtype[name] = dtype

    return {
        "missing_geoid": missing_geoid,
        "possible_geoid_alias": possible_geoid_alias,
        "unsafe_geoid_dtype": unsafe_geoid_dtype,
        "duplicate_column_names": duplicate_column_names,
    }


# -------------------------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------------------------


_CSV_COLUMNS = [
    "source_table",
    "column_name",
    "position",
    "arrow_dtype",
    "table_num_rows",
    "error_message",
]

# Columns that must survive a batch containing at least one failed table's sentinel row (None in
# column_name/position/arrow_dtype/table_num_rows) as clean integers, not silently upcast to
# float64 the moment pandas sees a None anywhere in the column across the batch — the identical
# fix, for the identical reason, as scripts/audit/audit_bucket.py's `_INT_COLUMNS`/`build_report`.
# Confirmed necessary here the same way it was confirmed necessary there: without this cast, one
# failed table in the run is enough to turn every other table's "position" values from "0", "1",
# "2"... into "0.0", "1.0", "2.0" in the CSV.
_NULLABLE_INT_CSV_COLUMNS = ("position", "table_num_rows")


def _build_report(results: list[dict]) -> pd.DataFrame:
    """Builds the output DataFrame: one row per column for every successfully-inspected table,
    plus exactly one sentinel row for every table that failed to inspect at all (column_name/
    position/arrow_dtype/table_num_rows all None, error_message populated) — so a failed table is
    always a visible row in docs/national_strata_schema_raw.csv, never a silent gap. Uses nullable
    Int64 for the integer columns (see _NULLABLE_INT_CSV_COLUMNS) so a batch that includes any
    failed table still renders every OTHER table's integer values cleanly."""
    rows: list[dict] = []
    for r in results:
        table = r.get("table", r.get("label", "<unknown>"))
        if "error" in r:
            rows.append(
                {
                    "source_table": table,
                    "column_name": None,
                    "position": None,
                    "arrow_dtype": None,
                    "table_num_rows": None,
                    "error_message": r["error"],
                }
            )
            continue
        for position, (name, dtype) in enumerate(r["columns"]):
            rows.append(
                {
                    "source_table": table,
                    "column_name": name,
                    "position": position,
                    "arrow_dtype": dtype,
                    "table_num_rows": r["num_rows"],
                    "error_message": "",
                }
            )

    report = pd.DataFrame(rows, columns=_CSV_COLUMNS)
    for col in _NULLABLE_INT_CSV_COLUMNS:
        report[col] = report[col].astype("Int64")
    return report


def main() -> int:
    filesystem = S3FileSystem(anonymous=True, region=S3_REGION)
    tables = [STRATA_NATIONAL_JOINED_TABLE, *NATIONAL_STRATA_SOURCE_TABLES]

    results: list[dict] = []
    for table in tables:
        print(f"Inspecting {table} ...")
        r = inspect_national_table(filesystem, table)
        results.append(r)
        if "error" in r:
            print(f"  ERROR: {r['error']}")
            continue
        print(f"  {len(r['columns'])} column(s), {r['num_rows']:,} row(s)")

    report = _build_report(results)
    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(DEFAULT_OUTPUT_PATH, index=False)
    n_failed_tables = int(report["error_message"].astype(bool).sum())
    print(
        f"\nWrote {len(report)} row(s) across {len(tables)} table(s) "
        f"({n_failed_tables} failed-table sentinel row(s)) to {DEFAULT_OUTPUT_PATH}"
    )

    joined = next((r for r in results if r.get("table") == STRATA_NATIONAL_JOINED_TABLE), None)
    print("\n" + "=" * 90)
    print(f"{STRATA_NATIONAL_JOINED_TABLE} — the joined table Stage 3's dictionary describes")
    print("=" * 90)
    if joined is None or "error" in joined:
        print(f"  COULD NOT INSPECT: {joined.get('error') if joined else 'not found in results'}")
    else:
        print(f"  {len(joined['columns'])} columns confirmed (PROJECT_BLUEPRINT.md's prose says 232).")
        print(f"  {joined['num_rows']:,} rows confirmed (src/io.py's docstring cites 85,396 tracts).")

    print("\n" + "=" * 90)
    print("Schema risk checks across every successfully-inspected table")
    print("=" * 90)
    risk = schema_risk_findings(results)

    if risk["duplicate_column_names"]:
        print(f"  {len(risk['duplicate_column_names'])} table(s) with a DUPLICATE column name in")
        print("  their own schema (excluded from the GEOID checks below — see each entry):")
        for table, dupes in risk["duplicate_column_names"].items():
            print(f"    - {table}: {dupes}")
    else:
        print("  No table has a duplicate column name in its own schema.")

    if risk["missing_geoid"]:
        print(f"\n  {len(risk['missing_geoid'])} table(s) with NO exact 'GEOID' column (review each")
        print("  — some national tables are legitimately indexed by something else, e.g. weather")
        print("  stations; check 'possible GEOID alias' below first):")
        for table in risk["missing_geoid"]:
            alias_note = risk["possible_geoid_alias"].get(table)
            suffix = f"  -> possible alias column(s): {alias_note}" if alias_note else ""
            print(f"    - {table}{suffix}")
    else:
        print("\n  Every successfully-inspected table has an exact 'GEOID' column.")

    if risk["unsafe_geoid_dtype"]:
        print(
            f"\n  {len(risk['unsafe_geoid_dtype'])} table(s) with a GEOID column that is NOT a "
            "safe string-like dtype — this project's single most-cited real risk "
            "(integer GEOID silently drops a leading-zero state FIPS):"
        )
        for table, dtype in risk["unsafe_geoid_dtype"].items():
            print(f"    - {table}: GEOID is {dtype!r}")
    else:
        print("\n  Every table's exact GEOID column (where present) is a safe string-like Arrow dtype.")

    errors = [r for r in results if "error" in r]
    if errors:
        print(f"\n{len(errors)} table(s) failed to inspect entirely — see ERROR lines above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
