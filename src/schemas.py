"""
src/schemas.py — Stage 2, Step 3.

One pandera `DataFrameSchema` per reference layer type this project reads (Overture buildings,
Overture roads, Overture POIs, Microsoft buildings, TIGER roads, HIFLD facilities, CBP — the seven
layer types named in PROJECT_BLUEPRINT.md's Stage 2 deliverables). This is the senior-level upgrade
over "we looked at the schema once during verification and it seemed fine"
(`docs/data_manifest.md` Section 4.3): a load whose real column shape has drifted from what this
file documents now fails LOUDLY, with a specific, actionable pandera error, at load time — not
silently downstream in an aggregation that produces a plausible-but-wrong number.

Checked by `src/io.py` (Stage 2 Step 4) on every load via `validate_layer()` below — not intended
to be called ad hoc by pipeline code, which should go through `io.py` instead.

Scope and honesty about what is/isn't enforced
------------------------------------------------------------------------------------------------
Every column name and every constraint marked "confirmed" below was directly checked against the
live bucket (footer-only parquet schema reads plus sampled batches — see
`docs/data_manifest.md` Section 4.3/4.5, `scripts/verify_bucket.py`,
`scripts/inspect_overture_sources.py`), not assumed from the challenge README's prose.

Four layer types (Microsoft buildings, TIGER roads, the four HIFLD facility files sharing one
schema, and CBP) were confirmed to have their ENTIRE column set documented — for these, the schema
is `strict=True`: an unexpected extra or missing column is itself a signal something changed
upstream and should fail loudly, not be silently ignored. `strict=True` in pandera also rejects any
undeclared column — including `geometry`/`bbox` — so every column actually present in these layers
is deliberately declared below, even where its dtype/nullability is intentionally left
unconstrained (see "Passthrough columns" below); a column present in the real data but silently
missing from this schema would otherwise break validation for a reason that has nothing to do with
this project's actual data-quality concerns.

The three Overture layer types (buildings, roads, POIs) were confirmed only for the specific
fields this project's pipeline depends on — Overture's full schema carries many more columns this
project never reads (alternate names, extended source metadata, etc.) — so those three schemas are
deliberately `strict=False`: only the confirmed, depended-upon columns are checked, and unrelated
columns pass through unexamined. Claiming `strict=True` for a schema this project has not
exhaustively confirmed would overstate what's actually been verified — against this project's own
"confirm the real numbers, don't assume" discipline.

Several individual constraints below (nullability of `height`/`confidence`/count columns, the
dtype of HIFLD's `ftype`/`fcode`/`gnis_id`) were NOT directly confirmed by a null-count or dtype
check against every row of the live bucket — that full pass is Stage 2 Step 5's job
(`scripts/audit/audit_bucket.py`, run across all four regions). Where this file makes a judgment
call ahead of that audit, it is marked "ASSUMPTION, not yet audit-confirmed" inline, and the
assumption is always on the permissive side (nullable=True, no dtype constraint) so this schema
cannot itself break the pipeline over something Step 5 hasn't checked yet — Step 5 is expected to
TIGHTEN these constraints once it has the real null/dtype counts, not loosen them.

Passthrough columns
------------------------------------------------------------------------------------------------
`geometry` is declared in every schema below (required so `strict=True` schemas don't reject it)
but deliberately carries no dtype or content constraint — pandera's pandas backend has no native
understanding of shapely geometry objects, and CRS/spatial-validity checking is `src/geometry.py`'s
job (Stage 2 Step 2), not this module's. `io.py` calls both: this module for attribute-column
contracts, then `src.geometry.normalize_geographic_crs` for the geometry column. A handful of other
columns below (HIFLD's `ftype`, `fcode`, `gnis_id`) are passthrough for a different reason — their
real dtype was not directly confirmed here — see the inline comments on each.

`bbox`: originally assumed present (as a required passthrough column) in every `strict=True`
schema, on the theory that these reference layers followed the same bbox-covering-struct
convention some GeoParquet producers use. Stage 2 Step 5's real audit run (all four regions)
directly disproved this for every one of the four strict=True layer types — `bbox` does not exist
in the real Microsoft buildings, TIGER roads, HIFLD, or CBP files, and every one of these schemas'
OTHER declared columns matched the real column set exactly. `bbox` is kept declared in each of
these four schemas, but with `required=False`: this tolerates it if some future data refresh ever
does add it back, without requiring it now that it's confirmed absent. Overture's three
`strict=False` schemas never declared `bbox` in the first place and were unaffected by this.

Validating a GeoDataFrame through one of these schemas was confirmed to preserve its
GeoDataFrame-ness (not silently downgrade it to a plain DataFrame) — `schema.validate(gdf)` returns
a GeoDataFrame, so downstream `src.geometry` calls keep working on the validated result.

Microsoft buildings' `confidence` sentinel (-1.0)
------------------------------------------------------------------------------------------------
Stage 2 Step 5's real audit run showed every region's Microsoft buildings file failing the plain
[0, 1] confidence check, with thousands of rows at exactly -1.0. Direct external research against
Microsoft's own GlobalMLBuildingFootprints README on GitHub confirmed this is documented, not
malformed: "For structures released before this update, we use -1 as a placeholder value." This
schema now tolerates -1.0 specifically for Microsoft buildings via
`_unit_interval_column(allow_placeholder_negative_one=True)`. This allowance is intentionally
scoped to Microsoft buildings only — `OVERTURE_POIS_SCHEMA`'s own `confidence` column (a
semantically different field, sourced from Overture, never documented to use this sentinel) keeps
the strict, un-loosened `_unit_interval_column()` default and must continue to reject -1.0.

Bounding pandera's failure-case listings (`n_failure_cases`)
------------------------------------------------------------------------------------------------
Once `validate_layer()` moved to `lazy=True` (see below), a real worst case surfaced: a single
failing Check can list every failing value it finds, unbounded — confirmed directly against the
real Microsoft buildings confidence failure, where 1285+ repeated "-1.0" entries alone consumed an
entire 8000-character truncation budget in `scripts/audit/audit_bucket.py`, silently hiding
whether any other column also had a problem. This is a pandera behavior, not a pandas repr
truncation (only pandera's own simple `not_nullable` checks happen to stay short on their own).
Every `Check(...)` in this module that can plausibly fail on real bucket data now passes
`n_failure_cases=_N_FAILURE_CASES` to cap the examples it lists, so one runaway column can no
longer crowd out every other violation in a `lazy=True` report.
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera import Check, Column, DataFrameSchema

from src.config import (
    LAYER_CENSUS_CBP,
    LAYER_CENSUS_TIGER_ROADS,
    LAYER_HIFLD_EMS_STATIONS,
    LAYER_HIFLD_FIRE_STATIONS,
    LAYER_HIFLD_HOSPITALS,
    LAYER_HIFLD_SCHOOLS,
    LAYER_MICROSOFT_BUILDINGS,
    LAYER_OVERTURE_BUILDINGS,
    LAYER_OVERTURE_POIS,
    LAYER_OVERTURE_ROADS,
)
from src.features import STRATA_FEATURE_COLUMNS

# Re-exported so callers can catch pandera's validation failures without importing pandera
# themselves. Confirmed empirically (not merely documented) that pandera can raise either
# `SchemaError` (singular — a single check failure, non-lazy) or `SchemaErrors` (plural — an
# aggregate, either from a `strict=True` structural violation or ANY `lazy=True` call, even one
# with only a single violation) depending on the failure and how `.validate()` was called — both
# are caught by catching this tuple. `validate_layer()` below (the real call path `src/io.py` uses)
# always validates with `lazy=True`, so in practice it always raises `SchemaErrors`; the individual
# schema objects in this file are still called directly, non-lazily, in tests/test_schemas.py,
# where either shape can occur — this tuple covers both call paths.
SchemaValidationError = (pa.errors.SchemaError, pa.errors.SchemaErrors)


# -------------------------------------------------------------------------------------------
# Shared column-building helpers
# -------------------------------------------------------------------------------------------

GEOID_LENGTH = 11
"""An 11-digit Census tract GEOID: 2-digit state FIPS + 3-digit county FIPS + 6-digit tract code.
Confirmed against `MARICOPA_NM_TRACT_GEOID` ("35023970000", `src/config.py`) and every GEOID
sampled directly from the bucket during verification."""

_N_FAILURE_CASES = 10
"""Every Check below caps its reported failure-case examples to this many. AUDIT-CONFIRMED
necessary (Stage 2 Step 5's real run, review pass afterward), not a speculative hardening: a real
run against Microsoft buildings' `confidence` column produced a SINGLE check's failure-case listing
that was, on its own, an unbounded comma-joined dump of every failing value -- 1000+ repeats of the
same value before hitting `_MAX_ERROR_MESSAGE_LENGTH`'s cap, at which point the aggregate message
was truncated mid-check and could no longer even show whether any OTHER column also had a problem.
This directly undercut the reason `validate_layer` was switched to `lazy=True` in the first place
(surfacing every independent violation in one pass) -- an earlier assumption that pandera's own
Series-repr truncation would keep every check's contribution small turned out to be true only for
simple nullability checks, not for `Check.in_range`/`Check.str_length`/a custom element-wise
`Check`'s own failure-case listing, which pandera does NOT bound on its own. `n_failure_cases`
(a documented pandera `Check` constructor parameter) fixes this at the source: confirmed directly
that it caps the listed examples per check regardless of how many rows actually fail, so a handful
of representative examples is always enough to diagnose the problem, and multiple independent
violations can always coexist within `_MAX_ERROR_MESSAGE_LENGTH`'s budget instead of one violation
silently consuming all of it."""


def _fixed_digit_string_column(length: int, *, nullable: bool = False) -> Column:
    """A fixed-length, all-digit string column contract — used for GEOID and its component FIPS
    codes (STATEFP, COUNTYFP, TRACTCE). String dtype is required, never coerced from int: an
    integer GEOID silently drops a leading-zero state FIPS (e.g. Maricopa's "04..." becomes
    "4..."), corrupting every downstream join — this is `docs/risk_register.md`'s
    GEOID-as-integer entry, and this schema is one of the two places (alongside `src/io.py`) that
    guards against it directly."""
    return Column(
        str,
        checks=[
            Check.str_length(length, length, n_failure_cases=_N_FAILURE_CASES),
            Check(
                lambda s: s.str.fullmatch(r"\d+"),
                element_wise=False,
                error="must be all digits",
                n_failure_cases=_N_FAILURE_CASES,
            ),
        ],
        nullable=nullable,
        coerce=False,
    )


def _passthrough_column(*, nullable: bool = True, required: bool = True) -> Column:
    """A column declared for presence (and, in a `strict=True` schema, to avoid pandera rejecting
    it as undeclared) but with no dtype or content constraint — see the module docstring's
    "Passthrough columns" section for when and why this is used instead of a typed Column."""
    return Column(nullable=nullable, required=required)


def _unit_interval_column(*, nullable: bool = True, allow_placeholder_negative_one: bool = False) -> Column:
    """A confidence-style float column expected in [0, 1]. `nullable=True` is deliberately
    permissive by default — nullability was not directly confirmed by a null-count check against
    every row (that is Stage 2 Step 5's job) — see the module docstring.

    `allow_placeholder_negative_one`: AUDIT-CONFIRMED necessary for Microsoft buildings specifically
    (Stage 2 Step 5's real run against all four regions failed every one of them on this exact
    check). Externally confirmed, not guessed from the data pattern alone: Microsoft's own
    GlobalMLBuildingFootprints README documents "For structures released before this update, we use
    -1 as a placeholder value" for `confidence`
    (https://github.com/microsoft/GlobalMLBuildingFootprints/blob/main/README.md) — -1.0 is a
    deliberate, documented sentinel for "not computed," not malformed data. Defaults to False and
    must be opted into per-schema rather than changed globally: this is a Microsoft-buildings-
    specific convention, not a general "confidence" contract — OVERTURE_POIS_SCHEMA's confidence
    column (the only other user of this helper) already passes its audit cleanly with the strict
    [0, 1] check and must not be silently loosened by a finding that has nothing to do with it."""
    check = (
        Check(
            lambda s: (s == -1.0) | s.between(0, 1),
            element_wise=False,
            error="must be -1.0 (Microsoft's documented placeholder) or in [0, 1]",
            n_failure_cases=_N_FAILURE_CASES,
        )
        if allow_placeholder_negative_one
        else Check.in_range(0, 1, n_failure_cases=_N_FAILURE_CASES)
    )
    return Column(float, checks=[check], nullable=nullable)


def _nonnegative_count_column(*, nullable: bool = True) -> Column:
    """A count column (e.g. establishment counts) expected to be >= 0. No dtype constraint —
    pandas may read an all-integer parquet count column as int64 or, if it contains nulls, as
    float64; both are accepted here since only non-negativity is the actual pipeline-relevant
    invariant. `nullable=True` is the same permissive-by-default choice as `_unit_interval_column`
    — see the module docstring."""
    return Column(checks=[Check.ge(0, n_failure_cases=_N_FAILURE_CASES)], nullable=nullable, required=True)


# -------------------------------------------------------------------------------------------
# Overture layers — strict=False: only pipeline-depended-upon columns are confirmed/enforced
# -------------------------------------------------------------------------------------------

OVERTURE_BUILDINGS_SCHEMA = DataFrameSchema(
    {
        # subtype: AUDIT-CONFIRMED nullable (Stage 2 Step 5, scripts/audit/audit_bucket.py, real
        # run against all four regions) -- this schema originally declared subtype non-null on the
        # (wrong) assumption that every Overture buildings-theme feature carries one; the real run
        # failed with "non-nullable series 'subtype' contains null values" in all four regions,
        # directly disproving that assumption. Corrected to nullable=True here. The exact null
        # RATE is not yet known -- the schema failure itself prevented audit_layer's null_coverage
        # step from ever running for this layer (see docs/data_manifest.md's Step 5 findings
        # section) -- re-running the audit after this fix will surface the real percentage.
        # class nullability remains an ASSUMPTION, not yet audit-confirmed for the same reason
        # (many real-world Overture buildings lack a `class` tag) -- left permissive.
        "subtype": Column(str, nullable=True),
        "class": Column(str, nullable=True),
        # sources: list<struct<...>> — the 10-field struct signature and per-region dataset
        # value distribution are directly confirmed (Stage 2 Step 1, docs/data_manifest.md 4.5).
        # Its internal struct shape is NOT re-validated here — that is
        # scripts/inspect_overture_sources.py's job, kept as the single place that understands
        # the struct's internals rather than duplicating that logic into a pandera Check. This
        # column is only checked for presence here.
        "sources": _passthrough_column(nullable=True),
        "geometry": _passthrough_column(),
    },
    strict=False,
)

OVERTURE_ROADS_SCHEMA = DataFrameSchema(
    {
        # subtype/class confirmed present and exactly as needed for the
        # subtype="road" + class in (motorway, trunk, primary, secondary) filter
        # (docs/data_manifest.md 4.3). `class` is NOT restricted to those four values here — the
        # raw reference layer carries every road class (residential, service, footway, ...); the
        # four-class filter is Stage 6 `gaps.py` logic applied on top of this schema, not a
        # property of the raw layer itself.
        "subtype": Column(str, nullable=False),
        "class": Column(str, nullable=True),
        "geometry": _passthrough_column(),
    },
    strict=False,
)

OVERTURE_POIS_SCHEMA = DataFrameSchema(
    {
        # categories: struct<primary, alternate> — confirmed present (docs/data_manifest.md 4.3
        # and 4.4, which also confirms real `categories.primary` values including the documented
        # facility strings and the near-miss categories that motivate exact-match filtering in
        # Stage 6). Nested struct sub-fields are not independently validated by pandera here;
        # presence only. nullable=True is deliberate, ASSUMPTION not yet audit-confirmed: Overture's
        # own POI schema permits a place with no known category, and this project has not directly
        # confirmed a zero-null count for `categories` across the live bucket (that is Stage 2
        # Step 5's job) — nullable=False here would crash this layer's ENTIRE load the first time
        # a single real row lacks a category, which is a plausible, not a hypothetical, failure
        # mode. Kept permissive for the same reason every other under-confirmed constraint in this
        # file is: this schema must not itself break the pipeline over something Step 5 hasn't
        # checked yet.
        "categories": _passthrough_column(nullable=True),
        # confidence: a FLAT top-level column on this layer (unlike buildings, where confidence
        # lives inside each `sources` element) — confirmed in docs/data_manifest.md 4.3.
        "confidence": _unit_interval_column(),
        "geometry": _passthrough_column(),
    },
    strict=False,
)


# -------------------------------------------------------------------------------------------
# Fully-documented layers — strict=True: the complete column set was confirmed, so an unexpected
# extra or missing column is itself a signal worth failing loudly on.
# -------------------------------------------------------------------------------------------

MICROSOFT_BUILDINGS_SCHEMA = DataFrameSchema(
    {
        # AUDIT-CONFIRMED (Stage 2 Step 5, real run across all four regions): the real column set
        # is "height, confidence, geometry" -- NO bbox column, contradicting docs/data_manifest.md
        # 4.3's original "height, confidence, bbox, geometry" claim. bbox is kept declared here but
        # required=False, not removed outright: it is defensively tolerated if a future refresh of
        # this data ever does carry it, but strict=True no longer demands it, since it is
        # confirmed absent in every region audited. See the module docstring's "bbox" note.
        "height": Column(float, nullable=True),  # nullability: ASSUMPTION, not yet audit-confirmed
        # confidence: Microsoft's own GlobalMLBuildingFootprints README documents -1 as a deliberate
        # placeholder value "for structures released before this update" (confirmed by direct
        # external research against the project's README on GitHub, Stage 2 Step 5). This is not
        # malformed data, so -1.0 must be tolerated alongside the normal [0, 1] range here.
        "confidence": _unit_interval_column(allow_placeholder_negative_one=True),
        "bbox": _passthrough_column(required=False),
        "geometry": _passthrough_column(),
    },
    strict=True,
)

CENSUS_TIGER_ROADS_SCHEMA = DataFrameSchema(
    {
        # AUDIT-CONFIRMED (Stage 2 Step 5, real run across all four regions): the real column set
        # is "LINEARID, FULLNAME, RTTYP, MTFCC, geometry" -- NO bbox column, contradicting
        # docs/data_manifest.md 4.3's original claim that included bbox. See the module
        # docstring's "bbox" note and MICROSOFT_BUILDINGS_SCHEMA's comment for why bbox is kept
        # declared but required=False rather than removed outright.
        "LINEARID": Column(str, nullable=False),
        "FULLNAME": Column(str, nullable=True),  # plausibly null for unnamed/local roads
        "RTTYP": Column(str, nullable=True),  # Census route-type code; commonly blank for local roads
        # MTFCC: confirmed present "exactly as needed for the S1100/S1200 filter"
        # (docs/data_manifest.md 4.3). The 5-character length is the standard Census MTFCC
        # convention (not independently re-confirmed against every row in this file — see Stage 2
        # Step 5), included because getting this wrong would silently break the transport_gap
        # filter this column exists for.
        "MTFCC": Column(
            str, checks=[Check.str_length(5, 5, n_failure_cases=_N_FAILURE_CASES)], nullable=False
        ),
        "bbox": _passthrough_column(required=False),
        "geometry": _passthrough_column(),
    },
    strict=True,
)

HIFLD_FACILITY_SCHEMA = DataFrameSchema(
    {
        # AUDIT-CONFIRMED (Stage 2 Step 5, real run across all four regions, all four HIFLD
        # files): the real column set is "permanent_identifier, name, ftype, fcode, admintype,
        # address, city, state, zipcode, gnis_id, geometry" -- NO bbox column, contradicting
        # docs/data_manifest.md 4.3's original claim that included bbox. Every other column in
        # this real, confirmed list matches exactly what was already declared below, unchanged.
        # See the module docstring's "bbox" note and MICROSOFT_BUILDINGS_SCHEMA's comment for why
        # bbox is kept declared but required=False rather than removed outright. Six of these
        # twelve columns (permanent_identifier, ftype, fcode, admintype, zipcode, gnis_id — plus
        # bbox/geometry, which are passthrough in every schema in this file for the reasons in the
        # module docstring) are left as passthrough here because their real dtype was not
        # directly confirmed: HIFLD commonly encodes identifier/feature-type/zip fields as
        # numeric codes in some exports and as strings in others, and asserting a specific dtype
        # ahead of that confirmation risks a false failure on real data. Only name/address/city/
        # state are typed as `str` below — a genuinely safe assumption for free-text address
        # fields. This schema's primary value-add for HIFLD is presence + exact-column-set
        # enforcement (strict=True), not deep per-column typing on every field — genuinely useful
        # on its own, and honestly scoped rather than overstated.
        "permanent_identifier": _passthrough_column(nullable=True),
        "name": Column(str, nullable=True),
        "ftype": _passthrough_column(nullable=True),
        "fcode": _passthrough_column(nullable=True),
        "admintype": _passthrough_column(nullable=True),
        "address": Column(str, nullable=True),
        "city": Column(str, nullable=True),
        "state": Column(str, nullable=True),
        "zipcode": _passthrough_column(nullable=True),
        "gnis_id": _passthrough_column(nullable=True),
        "bbox": _passthrough_column(required=False),
        "geometry": _passthrough_column(),
    },
    strict=True,
)


CENSUS_CBP_SCHEMA = DataFrameSchema(
    {
        # AUDIT-CONFIRMED (Stage 2 Step 5, real run across all four regions): the real column set
        # is "GEOID, STATEFP, COUNTYFP, TRACTCE, cbp_estab, cbp_estab_res, cbp_estab_bus,
        # geometry" — NO bbox column, contradicting docs/data_manifest.md 4.3's original claim
        # that included bbox — the only reference layer that ships pre-joined to tract polygons
        # (Section 4.3). See the module docstring's "bbox" note and MICROSOFT_BUILDINGS_SCHEMA's
        # comment for why bbox is kept declared but required=False rather than removed outright.
        "GEOID": _fixed_digit_string_column(GEOID_LENGTH),
        # STATEFP/COUNTYFP/TRACTCE lengths follow the standard Census FIPS convention (2/3/6
        # digits respectively) — a well-established external convention, not independently
        # re-derived from a bucket-specific check in this file.
        "STATEFP": _fixed_digit_string_column(2),
        "COUNTYFP": _fixed_digit_string_column(3),
        "TRACTCE": _fixed_digit_string_column(6),
        "cbp_estab": _nonnegative_count_column(),
        "cbp_estab_res": _nonnegative_count_column(),
        "cbp_estab_bus": _nonnegative_count_column(),
        "bbox": _passthrough_column(required=False),
        "geometry": _passthrough_column(),
    },
    strict=True,
)


# -------------------------------------------------------------------------------------------
# Stage 6, Step 6/7 — the assembled per-region tract-features table
# (`data/processed/<region>-tract-features.parquet`), Step 3's raw ingredients + candidate gaps,
# Step 4's strata join, and Step 5's derived columns, GEOID-indexed.
# -------------------------------------------------------------------------------------------

TRACT_FEATURES_LAYER = "tract-features"
"""Not a `src.config` `LAYER_*` bucket-reference constant — this is a processed OUTPUT table this
project builds itself (Step 6), not something read from the challenge's data package. Registered
in `LAYER_SCHEMAS` under this literal string anyway, exactly as the guideline asks, so Step 6's
assembly script can validate through the same `validate_layer()` path as every other layer."""

# Step 3's raw count/length columns — every one is a non-negative count or length; `cbp_estab_bus`
# is the one column allowed a genuine null (CBP non-disclosure — see build_stage6_step3_ingredients
# .py's fillna comment), every other raw column is a join-derived count that is 0, never null, for
# a tract absent from a spatial join.
_RAW_COUNT_LENGTH_COLUMNS = (
    "overture_transport_length_m",
    "tiger_transport_length_m",
    "overture_building_count_centroid",
    "overture_building_count_intersection",
    "microsoft_building_count_centroid",
    "microsoft_building_count_intersection",
    "overture_poi_count_fire",
    "hifld_count_fire",
    "overture_poi_count_ems",
    "hifld_count_ems",
    "overture_poi_count_schools",
    "hifld_count_schools",
    "overture_places_count",
)

# Step 3's candidate capped-ratio gap columns — every one is a `_capped_ratio` output: [0, 1],
# nullable (undefined stays NaN, R-005 — never silently zeroed).
_GAP_RATIO_COLUMNS = (
    "transport_gap",
    "building_gap_centroid",
    "building_gap_intersection",
    "poi_gap_fire",
    "poi_gap_ems",
    "poi_gap_schools",
    "poi_gap_establishments",
)

# Step 3's `*_defined` booleans — one per gap column above, never null (a tract's definedness is
# always knowable, unlike the gap value itself).
_DEFINED_COLUMN_NAMES = (
    "transport_defined",
    "building_gap_centroid_defined",
    "building_gap_intersection_defined",
    "poi_gap_fire_defined",
    "poi_gap_ems_defined",
    "poi_gap_schools_defined",
    "poi_gap_establishments_defined",
)

# Step 5's derived columns that Step 6 can actually assemble from Step 3 + Step 4 alone (no new
# raw ingredient needed): the 4 dispatch-blind-reachability candidates ([0, 1]; threshold_and is
# {0.0, 1.0} but that is a subset of [0, 1], so the same range check covers it) and the
# component-dominance/definedness trio. `confidence_reporting_rate`/`mean_reported_confidence`,
# `source_provenance_vector`'s columns, and `distance_to_tract_boundary_m` are DEFERRED — see
# Step 6's assembly script docstring for why (their raw per-record inputs, confidence/source lists
# and facility point geometries, are not gathered by Step 3's ingredients script and are out of
# this step's scope) — they are intentionally NOT declared here, not silently dropped from a
# larger declared set.
_DISPATCH_BLIND_COLUMNS = (
    "dispatch_blind_threshold_and",
    "dispatch_blind_normalized_euclidean",
    "dispatch_blind_product",
    "dispatch_blind_dari",
)

TRACT_FEATURES_SCHEMA = DataFrameSchema(
    {
        "GEOID": _fixed_digit_string_column(GEOID_LENGTH),
        "region": Column(str, nullable=False),
        **{
            col: Column(checks=[Check.ge(0, n_failure_cases=_N_FAILURE_CASES)], nullable=False)
            for col in _RAW_COUNT_LENGTH_COLUMNS
        },
        # cbp_estab_bus: the one raw column with a genuine null (CBP non-disclosure) — see
        # build_stage6_step3_ingredients.py's fillna comment.
        "cbp_estab_bus": Column(checks=[Check.ge(0, n_failure_cases=_N_FAILURE_CASES)], nullable=True),
        **{col: _unit_interval_column() for col in _GAP_RATIO_COLUMNS},
        **{col: Column(bool, nullable=False) for col in _DEFINED_COLUMN_NAMES},
        **{col: _unit_interval_column() for col in _DISPATCH_BLIND_COLUMNS},
        "dominant_component": _passthrough_column(nullable=True),
        "n_components_defined": Column(checks=[Check.ge(0, n_failure_cases=_N_FAILURE_CASES)], nullable=False),
        "undefined_components": Column(str, nullable=False),
        # Step 4's strata join — a curated, flagship ~60-column subset of `national-strata-
        # tract-table` (src.features.STRATA_FEATURE_COLUMNS is the single source of truth for
        # WHICH columns; this schema only re-uses its keys, not its per-column feature_role, since
        # pandera has no concept of that metadata — feature_role enforcement is
        # assert_competition_only's job, not this schema's). Declared as passthrough (no dtype/
        # range constraint): these columns' dtypes and value ranges were confirmed at the SOURCE
        # (docs/schema_catalog.csv, Stage 3) but not independently re-audited here — the same
        # ASSUMPTION-not-yet-audit-confirmed honesty convention this file already uses elsewhere
        # (see module docstring) rather than overstating what Step 6 itself verified.
        **{col: _passthrough_column(nullable=True) for col in STRATA_FEATURE_COLUMNS},
    },
    strict=False,
    # strict=False, matching the Overture layers' precedent: this table's column set is large and
    # partly sourced from a 232-column upstream table via STRATA_FEATURE_COLUMNS — an unconfirmed
    # extra column here is far more likely to be a benign future addition than a real drift signal,
    # unlike the four fully-audited reference layers above where strict=True is earning its keep.
)

# The frozen, schema-level allowlist of column names Stage 7's `build_submission.py` is permitted
# to read with `feature_role=competition` — see `assert_competition_only` in `src/features.py`.
# EMPTY today, deliberately: Step 0 Ambiguity 2 resolved that per-variant candidate gap values are
# computed in Stage 6 (this table) but the WINNING variant is only frozen in Stage 7's calibration
# — until that freeze happens, no column in this table has actually earned `feature_role=
# competition` yet, not even `transport_gap` (a single-variant gap the calibration could still
# reject in favor of a different formula). This is the fail-closed, least-privilege framing Step 7
# asks for: Stage 7 widening this set is an explicit, reviewable code change to this exact
# constant, not a default any column falls into by omission.
COMPETITION_ALLOWED_COLUMNS: frozenset[str] = frozenset()


# -------------------------------------------------------------------------------------------
# Registry — the single source of truth `src/io.py` (Stage 2 Step 4) looks up schemas from.
# -------------------------------------------------------------------------------------------

LAYER_SCHEMAS: dict[str, DataFrameSchema] = {
    LAYER_OVERTURE_BUILDINGS: OVERTURE_BUILDINGS_SCHEMA,
    LAYER_OVERTURE_ROADS: OVERTURE_ROADS_SCHEMA,
    LAYER_OVERTURE_POIS: OVERTURE_POIS_SCHEMA,
    LAYER_MICROSOFT_BUILDINGS: MICROSOFT_BUILDINGS_SCHEMA,
    LAYER_CENSUS_TIGER_ROADS: CENSUS_TIGER_ROADS_SCHEMA,
    LAYER_HIFLD_FIRE_STATIONS: HIFLD_FACILITY_SCHEMA,
    LAYER_HIFLD_EMS_STATIONS: HIFLD_FACILITY_SCHEMA,
    LAYER_HIFLD_SCHOOLS: HIFLD_FACILITY_SCHEMA,
    LAYER_HIFLD_HOSPITALS: HIFLD_FACILITY_SCHEMA,
    LAYER_CENSUS_CBP: CENSUS_CBP_SCHEMA,
    TRACT_FEATURES_LAYER: TRACT_FEATURES_SCHEMA,
}
"""Maps a `src.config` `LAYER_*` name to its pandera schema. Deliberately does NOT cover every
`LAYER_*` constant in `src/config.py` — `overture-roads-unfiltered`, `overture-rail`,
`overture-infrastructure`, and `census-acs-housing` have no confirmed schema yet and are out of
Stage 2 Step 3's scope (the seven layer types PROJECT_BLUEPRINT.md names for this step); calling
`validate_layer()` on one of those raises a clear `NotImplementedError` rather than silently
skipping validation — see `validate_layer` below."""


def validate_layer(df, layer: str):
    """Validates `df` (a GeoDataFrame or DataFrame) against the schema registered for `layer` in
    `LAYER_SCHEMAS`, returning the validated object (GeoDataFrame-ness is preserved — confirmed
    empirically, see the module docstring). This is the function `src/io.py` calls on every load.

    Raises `NotImplementedError` for a `layer` with no registered schema (rather than silently
    skipping validation) — a layer this project reads but Stage 2 Step 3 hasn't scoped a schema
    for yet is a gap worth surfacing loudly, not passing through unchecked.

    Raises one of `SchemaValidationError` (`pandera.errors.SchemaError` or `SchemaErrors`) if
    `df` fails its schema's contract.

    Validates with `lazy=True` — confirmed directly (Stage 2 Step 5's real audit run, and the
    review pass afterward) that pandera's DEFAULT (`lazy=False`) stops at the very FIRST failing
    check and raises immediately, even when a schema has multiple independent violations at once
    (e.g. two missing required columns): only the first is ever reported, and every subsequent
    check is never even evaluated. That directly caused the exact "fix bbox, re-run, discover
    subtype; fix subtype, re-run, discover the next thing" cycle this project hit for real against
    the live bucket. `lazy=True` runs every check and returns ALL violations together in one
    aggregate `SchemaErrors`, at negligible extra cost relative to the network I/O these layers
    already require — confirmed this does not change which exception TYPES can be raised (already
    covered by the `SchemaValidationError` tuple above) nor does it risk unbounded error-message
    growth (pandera's own Series repr already truncates long value listings on its own, and
    scripts/audit/audit_bucket.py additionally caps every stored error message regardless).
    """
    schema = LAYER_SCHEMAS.get(layer)
    if schema is None:
        raise NotImplementedError(
            f"validate_layer: no pandera schema registered for layer {layer!r}. Registered "
            f"layers: {sorted(LAYER_SCHEMAS)}. If this layer is newly in scope, add a schema to "
            "src/schemas.py and register it in LAYER_SCHEMAS rather than skipping validation."
        )
    return schema.validate(df, lazy=True)
