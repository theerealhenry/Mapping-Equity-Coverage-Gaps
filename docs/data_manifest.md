# Data Manifest

**Author:** Henry Otsyula
**Challenge:** Bias Bounty Mapping Equity Challenge (Zindi)

This document is the single source of truth for what data this project reads, exactly where it
comes from, and what has been directly confirmed about its structure and contents — as opposed to
what the challenge documentation describes. Every fact below was confirmed by directly listing or
reading the live bucket, not inferred from the README's prose. Facts that are still open are
listed explicitly in Section 7 rather than silently assumed.

## 1. Data source and access pattern

All challenge data is read directly from a public Source Cooperative bucket — cloud-native
GeoParquet, no credentials required, no bulk local download by default. Two equivalent access
routes are used depending on which library is reading a given file:

| Library | Route | Constant in `src/config.py` |
|---|---|---|
| DuckDB (httpfs extension) | HTTPS | `HTTPS_BASE` |
| pyarrow / geopandas (anonymous S3) | `s3://` (no scheme) | `S3_BUCKET`, `S3_REGION` |
| obstore (anonymous S3, used for listing) | `s3://` via `obstore.store.S3Store` | `S3_BUCKET`, `S3_REGION` |

Every object path used anywhere in this project is built from the helper functions in
`src/config.py` (`reference_url`, `reference_s3_path`, `strata_url`, `strata_national_url`,
`sample_submission_url`) — no script hardcodes a bucket path independently of these.

## 2. Overture release pin

Overture Maps layers are pinned to release `2026-08-19.0` (`src/config.py`:`OVERTURE_RELEASE`).
All computation in this repository uses that release only; the reference scores this project is
evaluated against were computed against this same release.

## 3. Object manifest

`scripts/build_data_manifest.py` lists every object under `reference/<region>/`,
`strata/<region>/`, `strata/national/`, and `boundaries/` for all four study regions, and records
each object's key, size, ETag, and last-modified timestamp to `docs/data_manifest.csv`. This is a
lightweight governance artifact, not full DVC-style data versioning — appropriate for a fixed,
read-only public bucket where the only real question worth being able to answer cheaply, later, is
"did the upstream data change under us." Re-run it periodically (and always immediately before the
Stage 7 scoring freeze) and diff `docs/data_manifest.csv` against the previous committed version to
catch that.

Confirmed by running it against the live bucket: 317 objects total, 8,078.4 MB. `reference/` holds
exactly 21 objects in every one of the four regions (matching the eastern-ok listing above
exactly). `strata/` holds 44 objects in three of the four regions — **South-Central Texas has only
43**, missing `south-central-tx-census-tribal-subdivisions.parquet`, which every other region has.
This is treated as a real, confirmed fact about the data package (South-Central Texas plausibly has
no census tribal subdivisions in that geography, unlike Eastern Oklahoma's tribal statistical
areas), not a bug in the listing — but it means Stage 6 feature-engineering code must not assume
every region carries an identical strata file set; a per-region file existence check is required
before loading `census-tribal-subdivisions`, not a bare load that would raise `FileNotFoundError`
for South-Central Texas specifically. `strata/national/` holds 48 objects; `boundaries/` holds 10.

## 4. Confirmed facts about the data package

### 4.1 No answer-key file is shipped

A direct listing of `reference/<region>/` for all four regions, searched for anything
gap/coverage/score/answer/solution/target/label-shaped, returned zero matches in every region. The
README's description of a `<region>-coverage-gap.csv` file documents the organizers' internal
scoring convention for transparency, not a file participants have access to. The coverage gap score
is computed from raw counts against the four reference datasets — there is no shortcut.

### 4.2 Two different "sample submission" artifacts exist — do not conflate them

- **The Zindi platform's upload template** (`SampleSubmission 3.csv`, provided on the challenge
  page): 9,379 rows, 17 columns, combined across all four regions, with a `region` column and every
  `_defined`/sub-component column present. This is the exact shape the final combined submission
  must match.
- **Each region's bucket-hosted `<region>-sample-submission.csv`**
  (`reference/<region>/<region>-sample-submission.csv`): a much narrower file — columns `GEOID,
  transport_gap, building_gap, poi_gap, coverage_gap_score`, no `region` column, no sub-component
  columns. This is each region's manifest of which GEOIDs must be scored, not the upload format.
  Every value in every gap column, in every sampled row, is literally `0.0` — confirmed directly,
  not inferred — meaning this file is an inert placeholder/manifest, not a partial answer leak.
  `eastern-ok-sample-submission.csv` is confirmed at exactly 1,192 rows by a direct programmatic
  read, matching the published eastern-ok scored-tract count; `01_eda.ipynb` (Stage 5) asserts this
  row count as one of its automated self-checks.

Working plan: use each region's bucket manifest to know which GEOIDs to compute, then assemble the
final combined submission in the 17-column shape the Zindi template demonstrates.

### 4.3 GEOID is pre-joined on exactly one layer

`<region>-census-cbp.parquet` ships as tract polygons with `GEOID, STATEFP, COUNTYFP, TRACTCE,
cbp_estab, cbp_estab_res, cbp_estab_bus, bbox, geometry` already attached — it is itself a
tract-polygon table, not a feature layer requiring a join. Every other layer this project reads —
Overture buildings, Overture roads, Overture POIs, Microsoft buildings, TIGER roads, and all four
HIFLD facility layers (fire stations, EMS stations, schools, hospitals) — is bare geometry with no
tract identifier at all, and needs an explicit spatial join against tract polygons
(`strata/<region>/<region>-census-tracts.parquet`) before it can be aggregated to the tract level.

Confirmed real schemas (footer-only reads, no full download):

- `overture-buildings`: fields include `subtype`, `class`, `sources` (a list of structs, each with
  its own `confidence` — confidence is not a flat column on this layer).
- `overture-roads`: `subtype` and `class` fields exist exactly as needed for the
  `subtype="road"` + `class in (motorway, trunk, primary, secondary)` filter.
- `overture-pois`: `categories` is `struct<primary, alternate>`; `confidence` is a flat top-level
  column on this layer (unlike buildings).
- `microsoft-buildings`: schema is `height, confidence, bbox, geometry` — nothing else, confirming
  it is purely a footprint-count source.
- `census-tiger-roads`: `LINEARID, FULLNAME, RTTYP, MTFCC, bbox, geometry` — `MTFCC` present
  exactly as needed for the `S1100`/`S1200` filter.
- `hifld-fire-stations` / `ems-stations` / `schools` / `hospitals`: all share the schema
  `permanent_identifier, name, ftype, fcode, admintype, address, city, state, zipcode, gnis_id,
  bbox, geometry`.

### 4.4 Real Overture `categories.primary` values, and why exact-match matters

Every documented facility category string is confirmed present exactly as named:
`fire_department`, `ambulance_and_ems_services`, `elementary_school`, `middle_school`,
`high_school`, `school`, `private_school`, `public_school`, and `hospital` (present but
deliberately excluded from the facilities term of the POI gap — Overture over-counts hospitals
roughly 12x relative to the HIFLD reference, which would otherwise make that term never show a
deficit).

The same live sample also surfaced real near-miss categories that a substring or fuzzy match on
these strings would wrongly count: `driving_school`, `dance_school`, `cosmetology_school`,
`fire_protection_service`, `firework_retailer`, `animal_hospital`, `emergency_pet_hospital`,
`fireplace_service`, `fire_and_water_damage_restoration`, `ems_training` (distinct from
`ambulance_and_ems_services`), and — the sharpest example — `security_systems`, which contains the
literal substring "ems". **Exact-match on `categories.primary` against the documented string list
is required, not optional.** This is concrete, real evidence, cited directly in the methodology's
edge-case handling section (`docs/methodology.md` Section 5).

### 4.5 `transport_gap` is not comparable across regions

The challenge documentation states this directly: Overture and TIGER draw the primary/secondary
highway classification boundary differently per region, producing a ratio between the two sources
that ranges 0.71–1.59 across the four study regions, for reasons that have nothing to do with
actual mapping effort. This has a direct downstream consequence: any pooled analysis across regions
(Stage 8's explanatory model, Stage 9's hypothesis mining) that treats `transport_gap` as directly
comparable across regions risks partly learning a classification-scheme artifact rather than a
genuine equity signal. Region is carried as an explicit control feature through every stage for
exactly this reason (see `PROJECT_BLUEPRINT.md` Section 3, Stage 6).

### 4.6 Confirmed region tract counts

| Region | Scored tracts | Total tract membership |
|---|---|---|
| Maricopa County, AZ | 1,593 (1,592 AZ + 1 NM tract, `35023970000`, Hidalgo County Tract 9700) | 1,593 |
| Northern California | 591 | 591 |
| Eastern Oklahoma | 1,192 | 1,192 |
| South-Central Texas | 6,003 | 6,010 |
| **Total scored** | **9,379** | — |

Published per-region **transport-only-undefined** percentages (self-checked in Stage 5, before
building/POI definedness logic exists): eastern-ok 21.2%, maricopa-az 54.5%, northern-ca 36.9%,
south-central-tx 28.4%.

Published per-region **any-of-three-components-undefined** percentages — a genuinely different
statistic, self-checked separately in Stage 7 once building/POI definedness logic exists: eastern-ok
21%, northern-ca 37%, south-central-tx 28%, maricopa-az 55% (rounded). These two statistics are
close for three of the four regions but must never be treated as interchangeable — they are checked
against two separate self-validation steps at two different stages.

## 5. Competition mechanics (confirmed from the live challenge page)

- Deadline: October 31, 2026 (challenge started August 28, 2026).
- Public leaderboard: ~30% of the 9,379-tract test set; private leaderboard: the remaining ~70%, a
  random partition of the same fixed tract list.
- 10 submissions per day, 300 submissions total for the challenge.
- The two submissions selected before the deadline are scored on the private leaderboard; if none
  are explicitly selected, the two best public-leaderboard submissions are used automatically.
- A top-10 finish at close triggers a 48-hour window to submit code for review.
- Every submission automatically receives a Bias Scorecard, but it does not affect leaderboard
  ranking — the leaderboard is decided by RMSE alone. Best Bias Discovery is judged separately, from
  a written methodology submission.
- The scored coverage-gap computation must use only the datasets provided for the challenge.
  Additional public data sources are permitted only for the Best Bias Discovery prize, and must be
  documented there with URL and retrieval date.
- Custom packages in the submission notebook are not accepted — only public, freely available
  packages, matching this project's own dependency policy.

## 6. Local caching policy — no bulk download by default

The pipeline reads directly from the bucket (bbox/column pushdown via DuckDB, or targeted reads via
pyarrow/geopandas) rather than bulk-downloading every layer up front. Where a stage genuinely
benefits from a local cache (feature engineering onward), intermediate results are written to
`data/interim/` and `data/processed/` as parquet — both gitignored, both fully regeneratable from
the bucket and this repository's code, never a required input to reproduce the project from a clean
clone.

## 7. Still open — tracked, not silently assumed

- Exact schema of `<region>-census-acs-housing.parquet` (housing units, used only as a sanity
  check) — not yet directly inspected beyond the README's description. Confirmed at Stage 2/5.
- Whether `cbp_estab` is exactly equal to `cbp_estab_bus` in every row, or differs in edge cases —
  a one-line equality check, planned for the Stage 5 EDA pass, not a blocker before then.
- The exact structure of Overture's `sources` field (its dataset-name granularity and value set) —
  confirmed only that it is a list of structs, each carrying its own `confidence`, distinct from
  POIs where `confidence` is a flat column. This gates the source-provenance feature vector built in
  Stage 6, so it is confirmed directly before that stage, not assumed from the README.
- Full schema/null/geometry-validity inspection across all four regions' `reference/` and `strata/`
  folders — Stage 1 (this stage) only inventories object keys/sizes/ETags; the deeper validation
  pass across every region and layer is Stage 2's job (`scripts/audit/audit_bucket.py`).
