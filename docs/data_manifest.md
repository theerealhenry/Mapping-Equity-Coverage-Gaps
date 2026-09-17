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
  it is purely a footprint-count source. **Correction (Stage 2 Step 5 full audit, Section 4.8):**
  `bbox` was never actually present in any of the four regions' real files — this footer-only spot
  check missed that at the time. `src/schemas.py` originally required it and every real load failed
  as a result; the schema now declares `bbox` `required=False` and this section is left as-is,
  uncorrected in place, specifically so the discrepancy between the original spot check and the
  full audit stays visible rather than silently smoothed over.
- `census-tiger-roads`: `LINEARID, FULLNAME, RTTYP, MTFCC, bbox, geometry` — `MTFCC` present
  exactly as needed for the `S1100`/`S1200` filter. **Correction (Stage 2 Step 5 full audit,
  Section 4.8):** same `bbox` correction as `microsoft-buildings` above — confirmed absent in all
  four regions' real files.
- `hifld-fire-stations` / `ems-stations` / `schools` / `hospitals`: all share the schema
  `permanent_identifier, name, ftype, fcode, admintype, address, city, state, zipcode, gnis_id,
  bbox, geometry`.

### 4.4 Real Overture `categories.primary` values, and why exact-match matters

Every documented facility category string is confirmed present exactly as named:
`fire_department`, `ambulance_and_ems_services`, `elementary_school`, `middle_school`,
`high_school`, `school`, `private_school`, `public_school`, and `hospital` (present but
deliberately excluded from the facilities term of the POI gap — Overture over-counts hospitals
relative to the HIFLD reference, which would otherwise make that term never show a deficit).
**Correction (Stage 6 Step 9 cross-check, 2026-09-17):** this section previously read "roughly 12x
... everywhere," a figure quoted from the challenge's own data README rather than measured directly
against this project's own pipeline output. Recomputing the raw Overture-vs-HIFLD hospital count in
all four regions gives 7.58x (maricopa-az), 8.54x (northern-ca), 5.43x (eastern-ok), and 7.19x
(south-central-tx) — a real spread of 5.43x-8.54x, not a fixed 12x. The figure is corrected here to
that measured range because the exclusion decision (R-004) should rest on this project's own
verified numbers, not an unverified figure carried over from someone else's documentation; the
qualitative conclusion is unaffected — every region overcounts by a wide enough margin that
including hospitals would still make the facilities term never show a real deficit.

The same live sample also surfaced real near-miss categories that a substring or fuzzy match on
these strings would wrongly count: `driving_school`, `dance_school`, `cosmetology_school`,
`fire_protection_service`, `firework_retailer`, `animal_hospital`, `emergency_pet_hospital`,
`fireplace_service`, `fire_and_water_damage_restoration`, `ems_training` (distinct from
`ambulance_and_ems_services`), and — the sharpest example — `security_systems`, which contains the
literal substring "ems". **Exact-match on `categories.primary` against the documented string list
is required, not optional.** This is concrete, real evidence, cited directly in the methodology's
edge-case handling section (`docs/methodology.md` Section 5).

### 4.5 Overture `sources` field — confirmed structure and dataset value set (all 4 regions)

`scripts/inspect_overture_sources.py` was run against the live bucket for `overture-buildings` and
`overture-roads` in all four regions (8 inspections total). Result: **CONSISTENT** — every
region/layer has the identical Arrow struct signature, confirming the field's shape does not vary
by region:

```
sources: list<struct<property: string, dataset: string, license: string, record_id: string,
                      update_time: string, confidence: double, between: list<element: double>,
                      provider: string, resource: string, version: string>>
```

10 fields — richer than the 5-field structure assumed from the eastern-ok-only spot check recorded
in an earlier pass. Zero empty/null `sources` rows in any of the 8 region/layer combinations
sampled (100,000-row sample per layer, or the full layer where smaller).

Real per-region/layer `dataset` value counts, from the 100,000-row sample (or full layer total
where noted), most common first:

| Region / layer | Total rows | Top `dataset` values in sample (count) | Max sources per row |
|---|---|---|---|
| maricopa-az / overture-buildings | 2,908,224 | OpenStreetMap 61,724; Microsoft ML Buildings 53,672; USGS Lidar 44,974; Esri Community Maps 1,500; Google Open Buildings 773 | 2 |
| maricopa-az / overture-roads | 494,492 | OpenStreetMap 129,848; TomTom 42 | 30 |
| northern-ca / overture-buildings | 1,164,724 | Microsoft ML Buildings 87,653; OpenStreetMap 25,005; Esri Community Maps 1,937 | 2 |
| northern-ca / overture-roads | 191,836 | OpenStreetMap 123,741; TomTom 65 | 29 |
| eastern-ok / overture-buildings | 2,551,694 | Microsoft ML Buildings 96,400; OpenStreetMap 13,649 | 2 |
| eastern-ok / overture-roads | 520,550 | OpenStreetMap 131,391; TomTom 59 | 42 |
| south-central-tx / overture-buildings | 11,463,801 | Microsoft ML Buildings 62,150; Google Open Buildings 40,640; OpenStreetMap 7,225 | 2 |
| south-central-tx / overture-roads | 1,937,009 | OpenStreetMap 121,597; TomTom 114 | 25 |

Notes:

- `overture-buildings` total row counts for eastern-ok (2,551,694) and `overture-roads`
  (520,550) exactly match the figures already confirmed in earlier bucket verification work — an
  independent cross-check that both runs are reading the same live data correctly.
- The building-source mix genuinely differs by region: `USGS Lidar` appears only in maricopa-az;
  `Google Open Buildings` is a meaningful contributor in south-central-tx and a minor one in
  maricopa-az, but does not appear at all in the northern-ca or eastern-ok building samples. This
  means a source-provenance feature (e.g. `source_entropy`) will carry real, non-degenerate
  cross-region signal once built in Stage 6 — it is not measuring the same thing everywhere.
  `overture-roads` is OpenStreetMap-dominated in every region with a small, consistent TomTom
  presence (tens to ~100 per 100k-row sample).
- `south-central-tx-overture-buildings` has a much larger total row count (11.46M) than the other
  three regions combined-scale layers — worth remembering for Stage 6 performance planning
  (batched/sampled reads, not full in-memory loads).
- Max elements observed in a single row's `sources` list: 2 for buildings (every region), but up to
  42 for roads (eastern-ok) — road segments are corroborated by substantially more upstream sources
  than buildings are, consistent with roads being a older/heavier-consensus OSM-tagged feature type.

This closes the corresponding "still open" item from Section 7 below — the `sources` field
structure and dataset value set are now confirmed directly against the live bucket, not assumed
from the README or a single-region spot check.

### 4.6 `transport_gap` is not comparable across regions

The challenge documentation states this directly: Overture and TIGER draw the primary/secondary
highway classification boundary differently per region, producing a ratio between the two sources
that ranges 0.71–1.59 across the four study regions, for reasons that have nothing to do with
actual mapping effort. This has a direct downstream consequence: any pooled analysis across regions
(Stage 8's explanatory model, Stage 9's hypothesis mining) that treats `transport_gap` as directly
comparable across regions risks partly learning a classification-scheme artifact rather than a
genuine equity signal. Region is carried as an explicit control feature through every stage for
exactly this reason (see `PROJECT_BLUEPRINT.md` Section 3, Stage 6).

**Real per-region ratios, confirmed live (Stage 5 Step 5, 2026-09-07 — full detail in Section
4.22):** `maricopa-az` 1.296, `northern-ca` 1.173, `eastern-ok` 0.719, `south-central-tx` 1.542 —
all four fall inside the documented band, closing this Stage 5 exit criterion. `eastern-ok` sits
only 0.009 above the band's floor (0.71), the tightest margin of the four regions and the only one
where TIGER's named-highway network substantially exceeds Overture's (38,506.6 km vs. 27,673.2 km,
Overture covering ~72% of TIGER's length). This is the third independent piece of evidence — after
Section 4.9's Overture `subtype`/`class` null-rate finding (94.2% in `eastern-ok`, the highest of
any region) and Section 4.21's filter-retention-rate finding (TIGER 0.35%-1.62% vs. Overture
11.42%-18.27% of each source's own network, by region) — that `eastern-ok`'s mapping completeness
gap is real and consistent across multiple, unrelated measurements, not an artifact of any single
metric.

### 4.7 Confirmed region tract counts

| Region | Scored tracts | Total tract membership |
|---|---|---|
| Maricopa County, AZ | 1,593 (1,592 AZ + 1 NM tract, `35023970000`, Hidalgo County Tract 9700) | 1,593 |
| Northern California | 591 | 591 |
| Eastern Oklahoma | 1,192 | 1,192 |
| South-Central Texas | 6,003 | 6,010 |
| **Total scored** | **9,379** | — |

Published per-region **transport-only-undefined** counts and percentages: eastern-ok 253/1,192 =
21.2%, maricopa-az 869/1,593 = 54.6%, northern-ca 218/591 = 36.9%, south-central-tx 1,704/6,003 =
28.4%. (Maricopa's precise value is 54.55%, which rounds to 54.6%, not 54.5% — a rounding slip
caught and corrected during this stage's review; the corresponding figure in
`PROJECT_BLUEPRINT.md` was fixed to match.) **Confirmed exactly, not just within rounding
tolerance, on live data in all four regions (Stage 5 Step 4, 2026-09-07)** — see Section 4.22 for
the full account, including a genuine root-cause correction to the definedness test itself
(bare spatial-join existence undercounted `eastern-ok` by 2 tracts; the fix generalizes to all
four regions, confirmed independently in Section 4.24).

Published per-region **any-of-three-components-undefined** percentages — a genuinely different
statistic, self-checked separately in Stage 7 once building/POI definedness logic exists: eastern-ok
21%, northern-ca 37%, south-central-tx 28%, maricopa-az 55% (rounded). These two statistics are
close for three of the four regions but must never be treated as interchangeable — they are checked
against two separate self-validation steps at two different stages.

### 4.8 Full audit pass across all four regions (Stage 2 Step 5)

`scripts/audit/audit_bucket.py` was run against every region × layer combination this project
reads — 4 regions × 11 layers/strata = 44 combinations — and the result recorded to
`docs/audit_findings.csv`. This is the deeper validation pass that Section 3's object listing does
not attempt: real column shapes, real null rates, real geometry validity, and real row counts,
checked against every row of every layer, not sampled. On the final run, **44/44 combinations
loaded and validated cleanly.** Two earlier runs surfaced real schema mismatches, both fixed in
`src/schemas.py` and both recorded here rather than silently corrected away:

- **`bbox` absent on four `strict=True` layers.** Microsoft buildings, TIGER roads, all four HIFLD
  facility files, and CBP were originally declared with `bbox` as a required column (Section 4.3's
  original footer-only spot check assumed it, following the GeoParquet bbox-covering-struct
  convention some producers use). The full audit disproved this directly: `bbox` does not exist in
  any of these files, in any region. `bbox` is kept declared in each schema but `required=False`,
  so it is tolerated if a future data refresh adds it back, without demanding it now that it is
  confirmed absent.
- **Overture buildings' `subtype` is genuinely nullable.** Originally declared `nullable=False`; the
  audit found real nulls in every region (see the finding below), so this is now `nullable=True`.
- **Microsoft buildings' `confidence` carries a documented `-1.0` placeholder.** The audit found
  thousands of rows at exactly `-1.0` in every region, which the original `[0, 1]` range check
  rejected outright. Direct external research against Microsoft's own GlobalMLBuildingFootprints
  README (github.com/microsoft/GlobalMLBuildingFootprints) confirmed this is intentional, not
  malformed data: *"For structures released before this update, we use -1 as a placeholder value."*
  `src/schemas.py` now tolerates `-1.0` specifically for Microsoft buildings' `confidence` column;
  Overture POIs' own, unrelated `confidence` column keeps the strict `[0, 1]` check and still
  rejects `-1.0`, since Overture never documented this convention.

**Row count reconciliation.** Every region's `strata/census-tracts` row count matches its expected
package total exactly: Maricopa 1,593; Northern California 591; Eastern Oklahoma 1,192;
South-Central Texas 6,010. South-Central Texas's package total (6,010) does not equal its scored
tract count (6,003, per Section 4.7 and the challenge README) — this is the seven documented `99xx`
water tracts the README states are dropped from the scored list for having no scorable reference
data. The audit confirms the package genuinely ships all 6,010, so this is expected package
behavior, not a data or pipeline bug — but it is a real trap for Stage 3 onward: any join must key
off `reference/<region>/<region>-sample-submission.csv` (the authoritative scored-tract list), never
off the raw `strata/census-tracts` row count, or South-Central Texas's coverage-gap computation will
silently include seven tracts that were never meant to be scored.

**Structural integrity.** Zero duplicate GEOIDs and zero null, invalid, or empty geometries across
every layer that carries a GEOID or a geometry column, in all four regions — no exceptions.

**Microsoft buildings' small residual geometry defect.** 97 invalid geometries total across
16,772,446 Microsoft buildings rows (18 in Maricopa, 4 in Northern California, 6 in Eastern
Oklahoma, 69 in South-Central Texas) — roughly 1 in every 173,000 rows. This is negligible at
current scale and is not being fixed at the audit stage (the audit is read-only, by design); it is
recorded here as a known, quantified, non-blocking defect so Stage 6's building-footprint join
logic can decide deliberately whether to drop or repair these rows rather than discover them by
surprise.

**Overture buildings' `subtype`/`class` null-rate gradient — a genuine Best Bias Discovery
candidate.** Null rates for `subtype` (and near-identically for `class`, its companion field) climb
sharply across regions in a pattern that tracks urbanization/mapping intensity, not random noise:
62.1% in Maricopa (the dense urban region), 80.3% in South-Central Texas, 88.3% in Northern
California (the wildfire corridor), and 94.2% in Eastern Oklahoma (tribal statistical areas). In
other words, a building footprint is far more likely to exist with no category information at all
in exactly the regions this challenge is asking about — the wildfire corridor and tribal lands —
than in the comparatively well-resourced urban region. This is a genuine, previously-unconfirmed
finding, distinct from the coverage-gap metrics the challenge already scores, and is a strong
candidate to carry forward explicitly into Stage 8's explanatory modeling and Stage 9's bias-mining
write-up: does this null-rate gradient correlate with SVI, tribal-land status, or hazard exposure
independently of the coverage-gap score itself? If so, it is a second, independent axis of mapping
inequity this project can document beyond the challenge's own scored metric.

**HIFLD `admintype` is 100% null everywhere.** All four facility types (fire stations, EMS stations,
hospitals, schools), in all four regions — the column exists in the schema but carries no real data
in this bucket. No feature should be built on it.

**TIGER roads `FULLNAME`/`RTTYP` are 36–49% null by region**, and the two columns' null rates track
each other almost exactly within each region (e.g. Eastern Oklahoma: 47.37% vs 47.37%) — consistent
with the expected explanation that unnamed/local roads simply lack both a name and a route-type
code, rather than two independent data-quality problems.

### 4.9 Live notebook re-run of the full audit (Stage 2 Step 7) — every Section 4.8 finding reconfirmed, plus three new precision facts

`notebooks/00_data_audit.ipynb` was built to turn the Stage 2 Step 5/6 audit work into a
reproducible, narrated notebook, then executed end-to-end against the live bucket with the
`bias-bounty` conda environment. Every cell ran without error and every in-notebook assertion
passed. This section records what that run confirmed, and — where the notebook computed
something more precise than the CLI script's original output — the more precise figure. Nothing
in Section 4.8 above is superseded; this section is a second, independent confirmation of it plus
additional detail the CLI run did not surface.

**Schema-fix regression proof (six checks, no network, run first).** Before re-running the live
audit, the notebook proves in-memory, against hand-built fixtures, that the three schema fixes
from Section 4.8 are (a) still in effect and (b) correctly scoped:

1. `PASS` — bbox absent is tolerated on Microsoft buildings (`strict=True`).
2. `PASS` — Overture buildings tolerates a null `subtype`.
3. `PASS` — Microsoft buildings' `confidence` tolerates the documented `-1.0` placeholder.
4. `PASS` — Microsoft buildings' `confidence` still rejects a genuinely invalid value (`-0.5`) —
   confirming the `-1.0` allowance did not loosen the range check generally.
5. `PASS` — Overture POIs' `confidence` still rejects `-1.0` — confirming the Microsoft-specific
   sentinel allowance did not leak into the one other layer with a flat `confidence` column.
6. `PASS` — `n_failure_cases` correctly bounds a lazy-validation failure listing (a synthetic
   200-row, all-`-0.5` fixture produces only 10 reported examples, not 200) — a check added during
   this stage's own review of the notebook, confirming the audit's failure-reporting mechanism
   itself won't flood output on a real large-scale failure.

**Full live audit: 44/44, reconfirmed.** All four regions × eleven layers/strata combinations
returned `status == "ok"` on this run, matching Section 4.8's final CLI result exactly. Real row
counts read directly off this run (previously only spot-quoted in earlier sections, now recorded
in full): Maricopa County — `census-cbp` 1,593; `census-tiger-roads` 313,994;
`hifld-ems-stations` 15; `hifld-fire-stations` 520; `hifld-hospitals` 100; `hifld-schools` 1,939;
`microsoft-buildings` 2,610,544; `overture-buildings` 2,908,224; `overture-pois` 300,046;
`overture-roads` 494,492. Northern California — `census-cbp` 591; `census-tiger-roads` 156,515;
`hifld-ems-stations` 30; `hifld-fire-stations` 561; `hifld-hospitals` 41; `hifld-schools` 974;
`microsoft-buildings` 1,138,335; `overture-buildings` 1,164,724; `overture-pois` 116,897;
`overture-roads` 191,836. Eastern Oklahoma — `census-cbp` 1,192; `census-tiger-roads` 353,691;
`hifld-ems-stations` 125; `hifld-fire-stations` 1,139; `hifld-hospitals` 135; `hifld-schools`
1,736; `microsoft-buildings` 2,404,448; `overture-buildings` 2,551,694; `overture-pois` 207,369;
`overture-roads` 520,550. South-Central Texas — `census-cbp` 6,010; `census-tiger-roads` 986,610;
`hifld-ems-stations` 422; `hifld-fire-stations` 2,408; `hifld-hospitals` 490; `hifld-schools`
7,940; `microsoft-buildings` 10,619,119; `overture-buildings` 11,463,801; `overture-pois`
1,300,334; `overture-roads` 1,937,009. `strata/census-tracts` row counts match Section 4.7 exactly
in all four regions (1,593 / 591 / 1,192 / 6,010).

**Row-count reconciliation — the sample-submission GEOID list is now proven, not just documented,
to be the required join key.** The notebook implements `reconcile_scored_tracts()` as a pure
set-difference function, self-tests it against three synthetic cases (exact match, a
South-Central-Texas-shaped 7-extra case, and a deliberately broken missing-tract case) before
running it live for all four regions:

| Region | `strata_tract_count` | `scored_tract_count` | `extra_in_strata_count` | `missing_from_strata_count` |
|---|---|---|---|---|
| Maricopa County, AZ | 1,593 | 1,593 | 0 | 0 |
| Northern California | 591 | 591 | 0 | 0 |
| Eastern Oklahoma | 1,192 | 1,192 | 0 | 0 |
| South-Central Texas | 6,010 | 6,003 | 7 | 0 |

`missing_from_strata_count == 0` in every region is asserted as a hard self-check — no region has
a scored tract that is absent from the raw strata table, which is the dangerous direction of
mismatch. The seven South-Central Texas extras are sampled directly: `48007990000`, `48061990000`,
`48261990000`, `48273...` (truncated in the notebook's own display, consistent with the
`99xx`-suffixed water-tract pattern already documented in Section 4.8). This reconfirms, against
the complete live data rather than a spot check, that **any script that builds the final
submission must filter to each region's `sample-submission.csv` GEOID list, not the raw strata
table** — the concrete, load-bearing rule this notebook was explicitly built to re-verify per this
stage's own instructions.

**Geometry deep dive — invalid geometries normalized per row count for the first time.** Section
4.8 above records raw invalid-geometry counts (18 / 4 / 6 / 69 across Maricopa / Northern
California / Eastern Oklahoma / South-Central Texas). Because the four regions' Microsoft
buildings row counts differ by an order of magnitude, the raw counts alone are not directly
comparable across regions. The notebook computes the normalized rate for the first time:

| Region | `row_count` | `invalid_geometry_count` | `invalid_per_million_rows` |
|---|---|---|---|
| Maricopa County, AZ | 2,610,544 | 18 | 6.90 |
| Northern California | 1,138,335 | 4 | 3.51 |
| Eastern Oklahoma | 2,404,448 | 6 | 2.50 |
| South-Central Texas | 10,619,119 | 69 | 6.50 |

Normalized, the four regions sit in a narrow 2.50–6.90-per-million-row band with no
region-size or rurality pattern — Eastern Oklahoma (the most rural, tribal-land-heavy region) has
the *lowest* normalized rate, and South-Central Texas (by far the most rows) sits mid-band rather
than highest. Every sampled invalid geometry, in every region, is a `Self-intersection` per
`shapely.validation.explain_validity` (five examples per region recorded directly in the notebook
output, with real coordinates, e.g. Maricopa `Self-intersection[-111.95979160921
33.0617785241733]`). **Conclusion: this defect does not correlate with the vulnerability axes this
project cares about and is not being carried forward as a Best Bias Discovery candidate** — it
reads as noise intrinsic to Microsoft's building-footprint extraction pipeline, not a
region-differentiated signal. It remains a known, quantified, non-blocking defect for Stage 6's
join logic to handle deliberately (drop or repair), exactly as Section 4.8 already states.

**Null-rate deep dive — Overture buildings gradient reconfirmed exactly; HIFLD `admintype`
reconfirmed exactly; TIGER roads now fully quantified with an unexpected divergence from the
Overture gradient's regional ordering.**

- Overture buildings `subtype`/`class`: this run reproduces Section 4.8's figures to one decimal
  place against the complete live data (not a sample): Maricopa 62.1% / 62.7%, South-Central Texas
  80.3% / 80.5%, Northern California 88.3% / 88.5%, Eastern Oklahoma 94.2% / 94.4% (`subtype` /
  `class`). `class` sits within 0.2–0.6 percentage points of `subtype` in every region, confirming
  the two columns move together as effectively one signal.
- HIFLD `admintype`: reconfirmed at exactly 100.0% null across all four facility layers (fire
  stations, EMS stations, schools, hospitals) in all four regions — sixteen of sixteen cells at
  100.0%, with zero exceptions. No feature should be built on this column; this is now confirmed
  against the complete live dataset, not a spot check.
- TIGER roads `FULLNAME`/`RTTYP`: Section 4.8 previously only quoted one region's figure (Eastern
  Oklahoma, ~47.37% for both). The full live run now gives all four regions for both columns:

  | Region | `FULLNAME` null % | `RTTYP` null % |
  |---|---|---|
  | Maricopa County, AZ | 36.29 | 36.29 |
  | Northern California | 48.57 | 48.57 |
  | Eastern Oklahoma | 47.37 | 47.37 |
  | South-Central Texas | 40.41 | 40.49 |

  The two columns track each other almost exactly in every region — the largest gap between them,
  anywhere, is 0.07 percentage points (South-Central Texas), computed directly by the notebook.
  This reconfirms Section 4.8's "the two columns move together" claim with the full precision
  needed to treat them as one signal, not two, in any Stage 6 feature.

  **New fact, not previously recorded:** the TIGER null-rate gradient's regional ordering
  (Maricopa < South-Central Texas < Eastern Oklahoma < Northern California, i.e. Northern
  California has the *highest* TIGER null rate) does **not** match the Overture subtype/class
  gradient's ordering (Maricopa < South-Central Texas < Northern California < Eastern Oklahoma,
  i.e. Eastern Oklahoma has the *highest* Overture null rate). Both gradients agree that Maricopa
  is lowest and South-Central Texas is second-lowest, but they disagree on which of Northern
  California or Eastern Oklahoma is worst. This means the two gradients are not simply the same
  underlying "rural areas get less mapping attention" factor read off two different columns — if
  they were, the ordering would match exactly. Whether they are two independent phenomena (a
  private building-data-provider attribution practice vs. a government road-naming/addressing
  convention) or two correlated-but-distinct expressions of a shared cause is an open question,
  carried forward into `docs/bias_discovery.md`'s candidate list for Stage 8/9 testing — a
  tract-level correlation between the two null rates (not just the four region averages recorded
  here) is the natural first test.

**Structural integrity self-checks — reconfirmed.** Four explicit assertions, run directly against
this live data, all passed: zero duplicate GEOIDs across all eight GEOID-bearing region/layer
combinations; zero null geometries anywhere; zero invalid geometries in every layer except
`microsoft-buildings` (fully accounted for above, and only there); zero empty geometries anywhere.
This matches Section 4.8's structural-integrity claim exactly, now reconfirmed independently by a
second, notebook-based implementation of the same checks rather than only the original CLI script.

**New governance artifact.** The notebook writes its own live findings to `docs/audit_findings.csv`
(same path `scripts/audit/audit_bucket.py` writes to, so either can be re-run and diffed against
the previous committed version) and additionally writes a compact cross-region rollup — one row
per region, combining the reconciliation, geometry, and null-rate headline numbers above — to
`docs/audit_notebook_summary.csv`. The rollup is the single table most worth citing directly in the
Best Bias Discovery methodology write-up, since it puts every region-comparison number from this
section side by side in one place.

**Why this run matters beyond restating Section 4.8.** Section 4.8 was produced by a one-shot
command-line script; this run is the same audit logic re-implemented, narrated, and executed
top-to-bottom inside a version-controlled notebook, with its own independent regression proof
(the six schema checks above) run immediately before the live audit rather than assumed from a
prior session. Getting an identical 44/44 result, identical reconciliation numbers, and identical
Overture/HIFLD null-rate figures from a second, independent implementation is meaningful
confirmation that Section 4.8's findings are properties of the data, not artifacts of the original
script. The one genuinely new fact this run adds — the TIGER/Overture gradient ordering
divergence — was only visible because this run computed all four regions' TIGER figures side by
side, which the original CLI-script pass never displayed together in one table.

## 4.10 Gate A exit-criteria sign-off (Stage 2 Step 9)

`PROJECT_BLUEPRINT.md` Section 2 states Gate A's exit criteria exactly: *"every layer in every
region has a passing schema contract; every known null/geometry-validity issue is documented with a
decision (drop, impute, or accept and note in the risk register); the CRS utility in
`src/geometry.py` has its own passing unit test before any other geometry code is written against
it; the `sources` field's real structure is confirmed."* Each of the four is checked below against
direct evidence, not asserted from memory of having done the work.

1. **Every layer in every region has a passing schema contract.** Confirmed twice, independently:
   the command-line audit (`scripts/audit/audit_bucket.py`, Section 4.8) and the narrated notebook
   re-run (`notebooks/00_data_audit.ipynb`, Section 4.9) both return **44/44** region/layer
   combinations at `status == "ok"`, with identical row counts and identical schema-regression
   results between the two runs. Re-verified a third time during this sign-off, in a completely
   independent, freshly-provisioned Python 3.11 environment (not Henry's development machine): the
   full test suite — including every schema/CRS/audit-logic unit test — passes cleanly there too
   (175 passed, 2 skipped; the 2 skips are a sandbox-only DuckDB spatial-extension download
   restriction, unrelated to any project code, and were already documented as such).
2. **Every known null/geometry-validity issue is documented with a decision.** Seven real findings,
   each with an explicit, recorded decision, not a silent pass-through: `bbox` absent on four
   `strict=True` layers → schema declares it `required=False` (Section 4.8); Overture buildings'
   `subtype` genuinely nullable → schema changed to `nullable=True` (Section 4.8); Microsoft
   buildings' `confidence` carries a documented `-1.0` sentinel → tolerated specifically for that
   column, externally verified against Microsoft's own README (Section 4.8); 97 invalid Microsoft
   buildings geometries (2.50–6.90 per million rows, normalized in Section 4.9) → accepted as a
   known, quantified, non-blocking defect, explicitly deferred to Stage 6's join logic rather than
   silently fixed at the audit stage; HIFLD `admintype` 100% null everywhere → decision recorded as
   "no feature should be built on it" (Section 4.8); TIGER `FULLNAME`/`RTTYP` null rates track each
   other almost exactly (max gap 0.07 pp, Section 4.9) → treated as one signal, not two, in any
   future feature; South-Central Texas's 6,010-vs-6,003 tract count gap → decision recorded as "any
   join must key off the sample-submission GEOID list, never the raw strata row count" (Section
   4.8, reconfirmed with exact `missing_from_strata_count == 0` evidence in Section 4.9). Per
   `PROJECT_BLUEPRINT.md`'s own stage plan, the formal `docs/risk_register.md` document that
   consolidates these is a Stage 11 deliverable (Section 3, Stage 11) — its exit-criteria mention
   here describes the category of acceptable decision ("accept and note in the risk register"), not
   a claim that the standalone file already exists at Stage 2. Every decision above is already
   captured, with full reasoning, in this document and in `src/schemas.py`'s inline comments, ready
   to be consolidated (not re-derived) when Stage 11 builds the standalone register.
3. **The CRS utility in `src/geometry.py` has its own passing unit test before any other geometry
   code is written against it.** `src/geometry.py`'s own module docstring records this directly: it
   was delivered as Stage 2 Step 2's CRS-handling half specifically so it could be tested and frozen
   before Stage 6's spatial-assignment logic (point-in-polygon, centroid/intersection, line-clip)
   is added to the same file — and that Stage 6 logic is confirmed, by direct inspection of the
   file during this sign-off, to still not exist yet ("Not yet implemented" is the literal last
   section of the file). `tests/test_geometry.py`'s 37 tests all pass (confirmed directly in the
   independent environment re-run above). A repository-wide search for every other place CRS
   transforms or forbidden CRS literals could plausibly appear (`ST_Transform`, `.to_crs(`, the
   substring `4326`) confirms zero production code paths outside `src/geometry.py` construct a CRS
   transform independently — every "4326" match anywhere else in the repository is inside
   `tests/test_geometry.py`/`tests/test_io.py` (testing this module's own normalization logic) or
   prose in `src/io.py`'s and `PROJECT_BLUEPRINT.md`'s docstrings describing the pitfall this module
   exists to prevent. `src/io.py`'s three geometry-bearing loaders (`load_reference_layer`,
   `load_strata_table`, `load_strata_national_table`) each call
   `src.geometry.normalize_geographic_crs` directly, confirmed by direct inspection. `src/geometry.py`
   remains, verifiably, the sole home of CRS-handling logic in this codebase — the criterion is met
   both in the literal chronological sense (it predates a Stage 6 that hasn't started) and in the
   architectural sense (nothing else duplicates or bypasses it).
4. **The `sources` field's real structure is confirmed.** Section 4.5 records the full 10-field
   struct signature and per-region/layer `dataset` value distributions, directly confirmed against
   all four regions × `overture-buildings`/`overture-roads` (8 inspections total,
   `scripts/inspect_overture_sources.py`), zero null `sources` rows found in any of the 8
   region/layer combinations sampled.

**All four Gate A exit criteria are met. Gate A ("Data Trusted") is closed.** Stage 3 (data
dictionary) may proceed without reservation.

**Additional fixes made during this sign-off review**, beyond re-confirming the four criteria
above — found while deliberately re-reading every file touched by Stages 0–2 end to end, not just
the four items the gate names:

- **`scripts/audit/audit_bucket.py`'s `_build_report` function was private (leading underscore) but
  already imported directly by `tests/test_audit_bucket.py` and by
  `notebooks/00_data_audit.ipynb` (as `ab._build_report`)** — a real fragility flagged, but
  deliberately left unfixed, during Stage 2 Step 7's review pending an explicit decision, since it
  touched an already-tested, already-committed file. Resolved now: promoted to a public
  `build_report`, with both call sites (the test file's import and the notebook cell) updated to
  match. Confirmed via `hasattr(audit_bucket_module, "_build_report") is False` and a full test-suite
  re-run (175 passed, 2 skipped, unchanged) that this was a clean rename, not a behavior change.
- **`src/cli.py`'s `cmd_audit` was still a Stage-0-era stub that unconditionally raised
  `NotImplementedError`**, even though Stage 2 fully built and tested the real audit
  (`scripts/audit/audit_bucket.py`). Since `src/cli.py` is documented as "the one interface every
  stage of the project is actually run through" and the `Makefile`'s own `audit` target already
  calls `python -m src.cli audit`, this stub would have made the project's own canonical entry
  point and `make audit` both fail for a stage that is, in reality, fully working — exactly the
  kind of thing a code reviewer notices in the first five minutes. Fixed: `cmd_audit` now forwards
  its parsed `--region`/`--layers`/`--skip-strata`/`--output` flags to
  `scripts.audit.audit_bucket.main()` (a lazy, function-local import, so `python -m src.cli --help`
  still never pulls in pandera/pyarrow for a subcommand that isn't being run). `tests/test_scaffold.py`
  updated to match: "audit" removed from the "every subcommand is a stub" parametrized test (with a
  comment explaining why), and four new tests added confirming the flag-forwarding logic is correct
  without ever touching the network (`scripts.audit.audit_bucket.main` is monkeypatched out).
- **`README.md`'s Status section was a generic "work in progress" pointer** with no concrete
  statement of what is actually done. For a project explicitly competing for Best Documentation,
  a reviewer's first-five-minutes read of the README should not require opening
  `PROJECT_BLUEPRINT.md` just to learn Gate A is closed. Updated to state Stage 0–2 completion,
  Gate A's closure, the double-independent-confirmation fact, and the current test count directly.
- **`docs/reproducibility.md`'s "How to run each stage" section was an empty placeholder** even
  though Stage 2's subcommand is now real. Filled in with the actual `python -m src.cli audit`
  usage, its flags, and a pointer to the notebook as the narrated equivalent.

None of these were required to satisfy Gate A's four literal criteria — all four were already met
before this pass found them. They are the kind of small, cumulative gaps ("the canonical CLI command
for a finished stage doesn't actually work," "a private function is relied on outside its own file
without anyone deciding that's acceptable," "the README undersells work that's actually done") that
do not fail a specific gate but do erode the impression of engineering rigor this project is
explicitly trying to build for the Best Documentation and Best Bias Discovery prizes, and for the
portfolio purpose of this repository. Fixing them now, while Stage 2 is still fresh and cheap to
touch, is deliberately cheaper than leaving them to be discovered during Stage 11's documentation
push or, worse, during a live 48-hour code-review window.

## 4.11 Stage 3 Step 1 — national strata schema inspection (26/26 tables, footer-only)

`scripts/inspect_national_strata_schema.py` was run against every table under `strata/national/`
(the joined `national-strata-tract-table` plus the 25 tables it is built from,
`src/config.py`:`NATIONAL_STRATA_SOURCE_TABLES`) using footer-only Parquet schema reads (no data
download). Result written to `docs/national_strata_schema_raw.csv`: **26/26 tables inspected
successfully, zero failures, 1,269 total column rows.**

**Headline facts reconfirmed directly, independent of `PROJECT_BLUEPRINT.md`'s prose and
`src/io.py`'s docstring.** `national-strata-tract-table` has exactly **232 columns** and **85,396
rows** — both figures now confirmed against the live bucket schema, not carried forward from
either document unverified.

**`national-cdc-wonder-heat-mortality` is a national reference table, not a tract-indexed one — by
design, not a data gap.** Its 13 columns (`series, group, level, deaths, deaths_suppressed,
population, database, era, icd_codes, definition, geography, source, national_only_reason`) contain
no `GEOID` and no geography-key alias. The column `national_only_reason` states why directly: CDC
WONDER suppresses heat-mortality counts below a reporting threshold at finer geographies, so only
national-level rows (82 of them, one per demographic/era stratum) are released. This table has zero
column-name overlap with the 232-column joined table, confirming it is correctly excluded from the
tract join rather than missing a key it should have. Data-dictionary decision: `level = national`,
not joinable to tracts, included in the dictionary as reference/context only.

**Four other low-row-count tables are legitimate boundary/membership files at a different geographic
level, not attribute gaps.** `national-census-aiannh` (867 rows), `national-census-tribal-
subdivisions` (484), and `national-census-tribal-tracts` (493) each carry a proper `GEOID` plus TIGER
boundary fields (`ALAND`, `AWATER`, `INTPTLAT`/`INTPTLON`, `geometry`, `bbox`) — one row per tribal
area / tribal subdivision / tribal census tract, not per Census tract. `national-noaa-ghcn-stations`
(78,849 rows) is station-indexed (`station_id`, `lat`, `lon`) with its own `GEOID` identifying the
containing tract. Data-dictionary decision: `level` set to `tribal-area` / `tribal-subdivision` /
`tribal-tract` / `weather-station` respectively for these four tables, not `census-tract`.

**The joined table is a curated subset of its 25 source tables, and every one of its 232 columns is
traceable by exact name.** Summed individually, the 25 source tables carry far more columns than
232 (several exceed it alone — `national-nasa-heat-tract-table` 174, `national-drought-gov-tract-
table` 161, `national-cdc-wonder-tract-table` 124, `national-usfs-wildfire-tract-table` 98).
Cross-checking every joined column's name against every source table's columns found **zero
unmatched columns** — all 232 trace to at least one source table. Of those, **223 map to exactly one
source table unambiguously**; the remaining **9 are shared join-key/geography fields** that
legitimately appear across many source tables: `GEOID`, `STATEFP`, `ALAND`, `AWATER`, `INTPTLAT`,
`INTPTLON`, `COUNTYFP`, `state_usps`, `tract_vintage`. All nine point to `national-census-tract-
table` as the join's backbone table — it is the only source carrying every one of those nine fields
together, alongside `NAMELSAD`. Data-dictionary/Step 2 rule: attribute the 223 unambiguous columns
1:1 by name; attribute the 9 shared key/geography columns to `national-census-tract-table`.

**One benign cross-table dtype inconsistency.** The shared key columns above take on both Arrow
`string` and `large_string` across different source tables (e.g. `GEOID` is `string` in some tables,
`large_string` in others). Both are string-like and functionally equivalent — this is not the
"unsafe dtype" class the script's own risk check watches for — but a naive `dtype ==` comparison
across tables would falsely flag it as a mismatch. Recorded here so it is not mistaken for a defect
later.

**One nested (non-scalar) column exists, and it was correctly dropped from the join.**
`national-usfs-wildfire-tract-table` carries `usfs_CWiRRZ_frac`, typed `list<element: double>` — the
only non-scalar column found across all 26 tables. It does not appear among the joined table's 232
columns, confirming the join deliberately keeps only flat/scalar columns. Data-dictionary decision:
recorded as `excluded from join: list-typed`, to be revisited only if a future feature explicitly
needs to unpack it.

**Structural risk checks, all clean.** Zero within-table duplicate column names across all 26
tables; zero unsafe (non-string) `GEOID` dtypes among tables that carry an exact `GEOID` column.

This closes Stage 3 Step 1. Step 2 (column-to-domain mapping) proceeds using the two rules
established here: the 223-unambiguous/9-shared-backbone attribution scheme, and the four
non-tract-level tables' corrected `level` values.

## 4.12 Stage 3 Step 2 — column-to-domain mapping (232/232 columns, zero unresolved)

`scripts/map_column_domains.py` applies Step 1's attribution rule (Section 4.11) and a
column-to-domain classification to every one of `national-strata-tract-table`'s 232 columns,
writing `docs/column_domain_map.csv`. It runs entirely offline against the already-committed
`docs/national_strata_schema_raw.csv` — no bucket access, no network — since every fact it needs
was already confirmed against the live bucket in Step 1.

**Result: 232/232 columns cleanly attributed and classified, zero unresolved.** Domain counts:
wildfire 85, heat 58, drought 28, rurality 15, cvi 13, geography 10, svi 9, tribal 9, population 5.

**A ninth domain bucket, `geography`, was added deliberately alongside the blueprint's eight named
domains** (population, SVI, CVI, rurality, heat, wildfire, drought, tribal). The nine shared
join-key/geography columns identified in Step 1 (`GEOID`, `STATEFP`, `COUNTYFP`, `state_usps`,
`ALAND`, `AWATER`, `INTPTLAT`, `INTPTLON`, `tract_vintage`) plus `state_name` carry no analytical
signal about any hazard or vulnerability axis — they identify a tract, they do not measure anything
about it — so classifying them under `population` (the nearest named domain) would have diluted
that domain's meaning for Step 5's `allowed_for_bias` classification later. `national-census-tract-
table` is the only table split at the column level: its five genuine population columns
(`pop_total`, `pop_urban`, `pop_rural`, `pct_urban`, `ur_class`) are `population`; its remaining ten
columns are `geography`.

**One real naming trap, caught by reading actual columns rather than trusting the table name.**
`national-carbonplan-tract-table`'s name suggests a carbon-emissions dataset. Its real columns —
`carbonplan_bp_*` (burn probability), `carbonplan_crps_*`/`carbonplan_rps_*` (conditional/rate of
spread) — are a wildfire-risk projection product (CarbonPlan's wildfire risk data), not a
carbon/climate dataset. Classified `wildfire`, not `heat`. This is exactly the kind of table this
project would have mis-classified if Step 2 had assigned domains from table names alone instead of
reading each table's actual column list — worth carrying into the write-up as a concrete example of
why this stage does the column-level read rather than the shortcut.

**Every column is traceable to a single source table with no genuinely ambiguous cases.** Of the
232 columns, 223 map to exactly one source table by exact name match; the remaining 9 are the shared
backbone columns above, all attributed to `national-census-tract-table` per Step 1's finding that it
is the only source table carrying all nine together. `scripts/map_column_domains.py`'s own
`find_unresolved()` check — which would flag a column matching more than one non-backbone source
table, matching zero source tables, or landing in a table with no domain assignment — returns zero
rows against the real, live-confirmed schema (enforced by `tests/test_map_column_domains.py`'s
real-data regression tier, which reads the same committed CSV this script does).

**Review pass, before closing Step 2.** A dedicated review of `scripts/map_column_domains.py` and
`tests/test_map_column_domains.py` found two real gaps, both fixed and re-verified:

- **`TABLE_DOMAIN`'s completeness against `src/config.py`'s canonical `NATIONAL_STRATA_SOURCE_TABLES`
  list was never actually checked by a test.** The existing real-data test tier only proves that
  every column *actually appearing in the 232-column join* gets a valid domain — it says nothing
  about the four source tables that contribute zero joined columns (`national-cdc-wonder-heat-
  mortality`, `national-census-aiannh`, `national-census-tribal-subdivisions`, `national-census-
  tribal-tracts`) but are still meant to carry a correct domain entry for Stage 3 Step 8's full,
  all-26-table dictionary later. A typo in one of those four tables' keys inside `TABLE_DOMAIN`
  would have gone completely undetected — demonstrated directly: renaming
  `national-usgs-combined-tract-table` to a typo'd `national-usgs-combined-tract-tabel` shows the
  existing join-column test would still have caught it (since that table does feed joined columns),
  but the same class of typo on one of the four non-joined tables would not have been caught by
  anything. Fixed by adding `test_table_domain_exactly_covers_the_canonical_national_strata_source_
  table_list`, which asserts `set(TABLE_DOMAIN.keys()) == set(NATIONAL_STRATA_SOURCE_TABLES)`
  exactly — currently true, and now a typo or a future added/removed table will fail loudly instead
  of silently.
- **A missing `--schema-csv` file crashed with a raw pandas traceback instead of a clear message.**
  `main()` now catches `FileNotFoundError` specifically and prints a one-line message pointing back
  to `inspect_national_strata_schema.py` (Step 1) as the script to re-run, returning exit code 2
  rather than letting an unhandled exception propagate. Covered by a new test asserting the exact
  exit code, the absence of a partial output file, and the message content.

Two minor test-file cleanups were also made: an unused `monkeypatch` fixture parameter was removed
from one test, and a redundant CSV write (the fixture was written to disk once, then immediately
overwritten by a second, filtered write before ever being read) was removed. Neither affected test
correctness — both were caught during the same close read as the two real gaps above. The full test
file now numbers 26 tests (24 originally, plus the two added during this review); the project-wide
suite stands at 222 passed, 2 skipped (the same sandbox-only DuckDB spatial-extension skip
documented since Stage 0).

This closes Stage 3 Step 2. Step 3 (coverage/null-semantics profiling per domain, against real data
per study region) proceeds using `docs/column_domain_map.csv`'s column→source_table→domain mapping
as its grouping key.

## 4.13 A latent `src/io.py` loader bug, found while starting Stage 3 Step 3

Stage 3 Step 3 (coverage/null-semantics profiling) is the first point this project needed to load
real row-level data from `national-strata-tract-table` rather than only its schema (Step 1) or
column names (Step 2). Attempting that surfaced a bug that had been sitting undetected since Stage 2
Step 4: `load_strata_national_table` calls `geopandas.read_parquet`, which unconditionally requires
GeoParquet geo-metadata and raises `ValueError: Missing geo metadata in Parquet/Feather file` on any
file that lacks a `geometry` column. Directly re-checking `docs/national_strata_schema_raw.csv`
confirms only 5 of the 26 tables under `strata/national/` carry `geometry` at all (`national-census-
aiannh`, `national-census-tracts`, `national-census-tribal-subdivisions`, `national-census-tribal-
tracts`, `national-noaa-ghcn-stations`); the other 21 — including `national-strata-tract-table`
itself — are flat attribute tables with no geometry whatsoever. `load_strata_national_table` was
never able to load the joined table, or any of those 20 other flat tables, against the real bucket.

This was masked by `tests/test_io.py`'s own test for the function: its fixture attached a synthetic
`geometry` column to a file named `national-strata-tract-table.parquet`, which passed but was never
representative of the real file's actual shape. The test proved the function works on a
geometry-bearing file; it never proved it works on the specific file it was named after. Reproduced
directly against an honest, non-geometry fixture before fixing anything, to confirm the failure mode
exactly: `RuntimeError: ... failed to read GeoParquet ...: Missing geo metadata in Parquet/Feather
file`.

**Fixed** by adding `load_national_strata_attribute_table` to `src/io.py` — a second loader, using
plain `pyarrow.parquet`/`pandas` rather than `geopandas`, for the 21 flat tables. `load_strata_
national_table` is unchanged and remains correct for the 5 tables that genuinely carry geometry.
`tests/test_io.py`'s misleading test was corrected to use one of those 5 real geometry-bearing
tables (`national-census-tracts`) instead of the joined table; a new test proves `load_strata_
national_table` correctly raises against a realistically-shaped flat fixture (documenting the bug
rather than hiding it), and four new tests cover the new loader (a successful flat read, an integer-
GEOID rejection, a table with no GEOID column at all tolerated correctly, and a missing-file case).
Full suite: 251 passed, 2 skipped (same sandbox-only DuckDB skip as always) after this fix.

This is exactly the class of gap the project's Gate A review process exists to catch before it
blocks real work — caught here the moment Stage 3 actually needed the function to work, rather than
being discovered later during Stage 6 feature engineering (which will also need to load these same
flat national tables) or, worse, during a live code-review window.

## 4.14 Stage 3 Step 3 — coverage and null-semantics profiling per domain, per region

`scripts/profile_coverage_and_nulls.py` computes, for every one of the 232 joined-table columns and
separately for the national scope and each of the four study regions (scoped by each region's
`sample-submission.csv` GEOID list, per the Section 4.8 rule — never the raw strata row count): null
count/rate, distinct-value count, and (for numeric columns) min/max/mean, written to `docs/coverage_
null_profile.csv`; a domain x region mean-null-rate rollup to `docs/coverage_null_domain_region_
summary.csv`; and, for each of the 19 `<prefix>_covered` boolean flags, a check of whether the flag
actually explains its measurement columns' null pattern, to `docs/covered_flag_consistency.csv`.

**The covered-flag grouping problem, and how it was solved.** A naive rule — "a flag's members are
every column sharing its name prefix" — breaks on two real cases, found by reading the actual 19
flags' real column neighbors rather than assuming the pattern holds uniformly: `national-cdc-wonder-
tract-table`'s single flag is named `cdcw_covered`, but every one of its 15 real measurement columns
is named `hwd_*` (heat/weather-data trend columns) — a prefix rule would have wrongly matched
`cdcw_covered` to only its 3 metadata neighbors (`cdcw_grain`, `cdcw_window_start`, `cdcw_window_
end`) and left all 15 real measurements unchecked. Conversely, two tables carry TWO covered flags
each (`national-nasa-heat-tract-table`: `gehe_covered`/`uhe_covered`; `national-drought-gov-tract-
table`: `pmdi_covered`/`spi_covered`) — grouping by source table alone would wrongly merge each
pair's measurements together. The algorithm implemented: a source table with exactly one covered
flag assigns it every other column from that table (correctly handles the `cdcw_covered`/`hwd_*`
mismatch, since it never depends on name similarity); a source table with more than one flag splits
by each flag's own name prefix instead (correctly separates `gehe_*` from `uhe_*`, and — since
`spi_covered`'s prefix is `spi` with no trailing underscore — correctly still claims `spi03_*`/
`spi12_*`, which do not contain the literal substring `spi_`). Verified directly against the real,
committed `docs/column_domain_map.csv`: all 19 flags get a non-empty group, `cdcw_covered`'s group
includes `hwd_*` columns, and the two multi-flag tables' groups are fully disjoint.

**Status: run against the live bucket; all 232 columns profiled across the national scope and all**
**four study regions.** The national table loaded 85,396 rows (matching Step 1's confirmed count
exactly), and each region's scoped row count matched its `sample-submission.csv` GEOID count exactly
(Eastern Oklahoma 1,192; Maricopa 1,593; Northern California 591; South-Central Texas 6,003) — no
missing-GEOID warning fired in any region, confirming Section 4.9's finding still holds. Outputs:
`docs/coverage_null_profile.csv` (232 columns x 5 scopes), `docs/coverage_null_domain_region_summary.
csv`, `docs/covered_flag_consistency.csv` (19 flags x 5 scopes).

**Finding 1 — every one of the 22 flagged flag/scope exceptions is a metadata artifact, not a data
problem.** `covered_flag_consistency.csv` flags a flag/scope pair whenever `flag == False` but at
least one of its member columns is still non-null. In all 14 distinct flag/scope combinations where
this occurred, `n_covered_false_but_some_member_non_null` matched `n_covered_false` exactly — meaning
every single "uncovered" tract still had a non-null value in at least one member column. Tracing each
case to the specific column responsible (by cross-referencing against `coverage_null_profile.csv`'s
per-column null rates) shows the responsible column is always a table-level metadata field —
`edition`, `version`, `year_min`/`year_max`, `threshold`, `window_start`/`window_end`, or
`calibration` — that is populated for every row in the source table regardless of whether that
tract's actual measurement is covered. In other words: the source tables stamp their own vintage/
methodology metadata on every row unconditionally, and the `_covered` flags correctly describe only
the substantive measurement columns, not these constant companions. This is expected behavior, not a
bug in the flags or in this profiling script — but it means a naive "count non-null member columns"
approach to auditing coverage would overstate real coverage, so Step 5's `allowed_for_scoring`/
`allowed_for_bias` classification (Stage 3 Step 5) should exclude these metadata columns from any
per-tract coverage computation.

**Finding 2 — the four `_ever` wildfire-history flags default to `False` for uncovered tracts instead
of propagating unknown-ness, a genuine equity risk.** `fod_ever`, `mtbs_wildfire_ever`, `nifc_
wildfire_ever`, and `usgs_wildfire_ever` are booleans with zero nulls in every scope — every tract,
covered or not, gets an explicit `True`/`False`. For tracts where the underlying `_covered` flag is
`False` (i.e., no real fire-history record was ever located for that tract), the `_ever` column still
reads `False`, which reads identically to "confirmed no fire history" rather than "unknown." Because
fire-record coverage itself tends to be sparser in the least-monitored rural and tribal tracts, this
column shape risks systematically undercounting wildfire history precisely where monitoring is
weakest — a coverage gap disguising itself as a negative finding. This is a strong, concrete, and
quantifiable candidate for the Best Bias Discovery submission: it is a real, present-in-the-data
mechanism by which a coverage gap becomes an incorrect "no risk" signal for the exact communities the
challenge is asking about.

**Finding 3 — `spi_calibration` is completely dead: 100% null in every scope, national included.**
Not a regional artifact; this column carries zero information anywhere in the dataset. Flagged as a
drop candidate for Step 5.

**Finding 4 — `rucc_covered` and `ghcn_covered` are constants nationally** (`n_distinct == 1`, always
`True`) and so carry no discriminative signal for coverage-gap or bias analysis; noted for Step 5's
classification pass rather than treated as an error.

**Finding 5 — `ruca_primary`'s sentinel value of 99 (RUCA's own documented "water tract / no
population data" code) appears only in the `national` and `south-central-tx` scopes** (max = 99 in
both; max = 10 in Eastern Oklahoma, Maricopa, and Northern California). This independently
corroborates Section 4.8/4.9's already-documented finding that South-Central Texas's scored tract
list includes seven `99xx`-suffixed water tracts — the two findings were produced by entirely
different methods (Stage 2's GEOID-suffix inspection vs. Stage 3's column-value profiling) and agree
exactly.

**Finding 6 — `uhe_covered` (Urban Heat Exposure coverage) varies sharply and directly with rurality:
57.97% null in Eastern Oklahoma versus 30.76% null in Maricopa County.** Eastern Oklahoma is the
project's most rural, most tribal-land-dense region; Maricopa is dense urban/suburban. This is a
second strong, quantified Best Bias Discovery candidate, independent of Finding 2 and independent of
the challenge's own scored coverage-gap metric — it demonstrates, from the raw data alone and before
any SVI/tribal-boundary cross-referencing, that heat-exposure monitoring coverage itself tracks
urban/rural divide in exactly the direction the challenge's own hypothesis predicts.

**Review pass, before running against the live bucket.** A dedicated review of `scripts/profile_
coverage_and_nulls.py`, `src/io.py`'s new loader, and both test files found four real issues, all
fixed and re-verified — two of them were live bugs, not just missing coverage:

1. **A real crash, not yet triggered only because today's domain map happens to avoid it.** If
   `identify_covered_flag_groups` ever returns an empty dict — impossible against the real,
   committed 232-column domain map (it has 19 flags), but not guaranteed for an arbitrary
   `--domain-map` — `consistency_records` stayed empty and `pd.DataFrame.from_records([])` built a
   DataFrame with NO columns at all. `main()`'s very next line filters that frame by column name
   (`consistency_df["n_covered_true_but_all_members_null"]`), which raised `KeyError` instead of
   simply finding zero exceptions. Reproduced directly with a domain map containing no `_covered`
   columns before fixing anything. Fixed by passing an explicit column list to `pd.DataFrame.from_
   records`, so an empty result still has the right shape.
2. **A second real bug, also latent rather than yet-triggered: one covered flag's name could be
   swallowed into another flag's own member list.** The multi-flag branch (for the two source
   tables carrying more than one `_covered` column) excluded only the current flag from a candidate
   member list (`c != flag`), not every flag column in that table. Demonstrated directly: given
   three columns `alpha_covered`, `alpha_beta_covered`, `alpha_value` in one table, the old code put
   `alpha_beta_covered` — itself a flag — into `alpha_covered`'s member list, and left `alpha_beta_
   covered`'s own group empty. Not triggered by any of today's 19 real flags (verified: no real
   flag's name is a prefix of another flag's name within the same source table), but there is no
   reason this function should silently mis-handle that shape if a future table's naming ever
   collided this way. Fixed by excluding every flag column in the table, not just the current one;
   confirmed the fix produces byte-identical real-data output (all 19 group memberships unchanged)
   to before the fix.
3. **A test-realism gap that could have hidden a real dtype bug.** Every existing fixture for the
   new `load_national_strata_attribute_table` loader was written via `pandas.DataFrame.to_parquet`,
   which embeds pandas metadata that `pyarrow`'s reader uses to restore nullable `Int64`/`boolean`
   extension dtypes on read. The real bucket's files were almost certainly not produced that way.
   Reproduced the realistic case directly (a plain `pyarrow.Table` written with no pandas metadata):
   an Arrow integer column with nulls comes back as plain `float64` (not nullable `Int64`), and an
   Arrow `bool` column with nulls comes back as `object` dtype holding Python `True`/`False`/`None`
   (not `numpy.bool_`, not pandas' nullable `boolean` dtype). Confirmed `null_profile` and `covered_
   flag_consistency`'s existing logic already handles both cases correctly by coincidence (`==
   True`/`== False` and `.isna()` both work correctly on the object-dtype case; `is_bool_dtype`
   correctly excludes both shapes from numeric stats) — but nothing was testing this realistic shape
   before this review, so a future refactor could have broken it silently. Fixed by adding this
   dtype behavior explicitly to `load_national_strata_attribute_table`'s docstring in `src/io.py`,
   and adding four new tests (one in `test_io.py` through the real loader, three in `test_profile_
   coverage_and_nulls.py` directly against `null_profile`/`covered_flag_consistency`) that construct
   fixtures the same realistic way and assert the correct behavior explicitly.
4. **`_sentinel_note` stopped at the first matching sentinel, and — a bug introduced and caught
   within this same review, while fixing that — an initial attempt to report every match would have
   double-reported the same value under two different labels** (`-1` and `-1.0` both matching and
   both getting listed, since a numeric comparison doesn't distinguish int/float literals). Fixed by
   listing every `SENTINEL_CANDIDATES` value once, as a float, and having `_sentinel_note` collect
   every distinct match rather than returning on the first. Also broadened the candidate list to
   include large positive placeholders (`9999`, `99999`), a common coded-missing convention for
   year- or percentage-shaped columns that this joined table has several of.

Two smaller defensive additions made at the same time, not bugs but gaps worth closing given this
step's importance: `main()` now warns (without blocking the run) if the live table's row count ever
differs from Step 1's confirmed 85,396, and warns per-region if a sample-submission GEOID is ever
not found in the national table (Stage 2 already confirmed this never happens today — `missing_
from_strata_count == 0` in every region, Section 4.9 — but a silent mismatch would otherwise corrupt
every downstream null-rate figure for that region without any indication).

All four real issues were reproduced concretely before being fixed, not just reasoned about, and
every fix is covered by a dedicated regression test. `tests/test_io.py` grew from 29 to 30 tests;
`tests/test_profile_coverage_and_nulls.py` grew from 24 to 32. Full project suite: 260 passed, 2
skipped (same sandbox-only DuckDB skip as always), zero third-party mentions on a final scan.

## 4.15 Stage 3 Step 5 — role, allowed_for_scoring, and allowed_for_bias classification

`scripts/classify_columns.py` assigns every one of `national-strata-tract-table`'s 232 columns a
`role`, an `allowed_for_scoring` flag, and an `allowed_for_bias` flag, each with a stated reason,
written to `docs/column_classification.csv`. Unlike every step since Step 3, **this step needs no
live bucket access at all** — its three inputs (`docs/column_domain_map.csv` from Step 2,
`docs/coverage_null_profile.csv` from Step 3, and `scripts.confirm_domain_vintages.
VINTAGE_COLUMNS_BY_SOURCE_TABLE` from Step 4) are all already-committed, real data, so it was built,
run, and verified in full before this section was written — nothing here is provisional pending a
run Henry still has to do.

**`allowed_for_scoring` is False for all 232 columns, with zero exceptions, and this is a table-level
rule, not 232 individual judgment calls.** It follows directly from how the challenge's own
documentation organizes the data, confirmed against three separate sources: the repository
`README.md` ("`reference/` the map data you score" vs. "`strata/` tract-keyed demographic /
vulnerability / hazard strata"), the `The Dataset` project doc ("Coverage gap reference datasets" —
Overture, TIGER Roads, Microsoft Buildings, ACS housing, HIFLD, CBP — listed entirely separately from
"Bias API strata datasets" — SVI, CVI, RUCA, tribal, USDM, USFS, HeatRisk), and the `Evaluation`
project doc (submissions are scored by RMSE against the coverage-gap formula computed from
`reference/`; the Bias Score is a separate, non-ranking scorecard). `national-strata-tract-table`
lives entirely under `strata/`. One scope clarification worth stating precisely: the Reference
Reconstruction Engine's tract geometry (needed to spatially assign Overture features to tracts) comes
from `national-census-tracts.parquet`, a separate geometry-only file — not one of the 232 columns
classified here, and out of this step's scope; nothing about that file's necessity changes the
`allowed_for_scoring=False` answer for every column of `national-strata-tract-table` itself.

**Role taxonomy** (8 roles, assigned by an explicit, hand-verified priority order — not inferred
from domain or dtype alone, since Step 4 already proved that unreliable): `identifier` (5: `GEOID`,
`STATEFP`, `COUNTYFP`, `state_usps`, `state_name`), `geometry_measure` (4: `ALAND`, `AWATER`,
`INTPTLAT`, `INTPTLON`), `population` (5: `pop_total`, `pop_urban`, `pop_rural`, `pct_urban`,
`ur_class`), `identity_metadata` (4: `aiannh_geoid`, `aiannh_name`, `uhe_city_name`,
`uhe_city_country` — descriptive labels naming an external entity a tract was matched to or
overlaps, not a measurement of the tract itself), `vintage_metadata` (35: Step 4's list, minus the
2 identity-metadata columns above — see the real bug below), `coverage_flag` (19: every `<prefix>_
covered` boolean), `derived_ever_flag` (4: `fod_ever`, `mtbs_wildfire_ever`, `nifc_wildfire_ever`,
`usgs_wildfire_ever`), and `measurement` (156: everything else — every substantive numeric or
categorical per-tract value, including the descriptive-label companions to a numeric classification
code, e.g. `ruca_primary_desc`, `rucc_desc`, `nchs_2013_label`, `svi_rank_universe`,
`aiannh_kind`, `usfs_CWiRRZ_majority_label`/`_zone4_label` — all confirmed, via their real
n_distinct in `docs/coverage_null_profile.csv`, to carry real per-tract variance, not to be disguised
constants). Counts sum to exactly 232, locked in by a real-data regression test.

**`allowed_for_bias` combines a role-based default with a hard, data-driven override that fires
first regardless of role**: any column with `n_distinct <= 1` in the national scope (Step 3's real
profiling — a column literally identical across all 85,396 tracts) is forced to `False`, because a
constant cannot explain variance in anything, whatever its role would otherwise suggest. This is a
live computation against Step 3's real output, not a hand-maintained exception list, so it cannot
drift out of sync with the data. It correctly re-derives, independently, two things Step 3 had
already found by inspection (`rucc_covered`/`ghcn_covered` always `True` nationally — Section 4.14
Finding 4) plus one new one this step's own build surfaced: `hwd_maxtemp_never_defined` is `False`
for every tract nationally (unlike its `hwd_heatindex_never_defined`/`hwd_heatstress_never_defined`
siblings, which do vary) — a real measurement, just one with zero variance in this dataset. Beyond
that override, defaults are: `identifier` → False (a join key, not a signal); `vintage_metadata` →
False (describes the source dataset's methodology, not the tract — though in practice every real
vintage-metadata column is already caught by the zero-variance override first, confirmed by a
dedicated regression test); `geometry_measure`, `population`, `coverage_flag`, `identity_metadata`,
and `measurement` → True by default; `derived_ever_flag` → True, but with a mandatory-pairing note
in its reason text (must be interpreted jointly with its own `_covered` flag, per Section 4.14
Finding 2's documented equity risk). Net result against the real data: 189 of 232 columns
`allowed_for_bias=True`, 43 `False` (5 identifiers, 35 vintage-metadata columns, `rucc_covered`,
`ghcn_covered`, and `hwd_maxtemp_never_defined`) — every one of the 43 has a specific, printed reason,
not just a bare flag.

**A real bug, caught on this step's own first real run, not by inspection.** `uhe_city_name` and
`uhe_city_country` are members of Step 4's `VINTAGE_COLUMNS_BY_SOURCE_TABLE` — but only because Step
4 added them there for a narrower, different reason (so its extraction script would pull their live
values while investigating which "uhe" dataset this table actually comes from), not because they are
genuine vintage/edition/methodology metadata. The first version of `classify_role` checked
`vintage_columns` membership before `IDENTITY_METADATA_COLUMNS`, so both columns were silently
misclassified as `vintage_metadata` and force-blocked from bias analysis — which would have quietly
disqualified the exact evidence behind Section 4.14's Tijuana/cross-border `uhe_*` finding from ever
being used in Stage 8/9's analysis. Caught immediately by actually running the script against the
real data and reading its console output line by line, not by only reading the code. Fixed by
checking `IDENTITY_METADATA_COLUMNS` first; a dedicated regression test
(`test_identity_metadata_wins_over_vintage_membership`) locks this in, and the real-data test that
originally masked it (asserting the vintage-metadata row count equalled the raw vintage-column list's
length) was corrected to account for the 2-column difference explicitly rather than loosened.

**A second, retroactive correction to Step 4 itself, also caught by this step.** Building this step's
zero-variance check (cross-referencing every column's real `n_distinct` against the vintage list)
surfaced `epht_metric` — a genuine constant-string methodology-metadata column in
`national-epht-heat-tract-table`, structurally identical to `epht_threshold` — that Step 4's original
keyword-based sweep had missed entirely (its regex never included "metric"). This is documented in
full, with a stronger permanent regression test added to `tests/test_confirm_domain_vintages.py`, in
`docs/data_vintage_confirmation.md`'s own correction note; `epht_metric` is now correctly included in
`VINTAGE_COLUMNS_BY_SOURCE_TABLE` and classified here with `role=vintage_metadata`,
`allowed_for_bias=False`.

`tests/test_classify_columns.py`: 30 tests, all passing, including five real-data regression tests
against the actual committed 232-column table (exact row count, every role firing at least once and
summing to 232, every vintage-metadata column forced False, the known zero-variance flags forced
False, and the identity-metadata/vintage-list overlap resolved correctly). Full project suite: 308
passed, 2 skipped (same sandbox-only DuckDB skip as always), zero third-party mentions on a final
scan. `docs/column_classification.csv` (232 rows) is the deliverable Step 6 (candidate_hypotheses
tagging) and Step 8 (the data dictionary build) will both read from.

**Independent review pass.** Before moving on, this step's deliverables were reviewed a second time,
adversarially, specifically looking for bugs, incorrect logic, and overlooked edge cases rather than
re-describing what was already built. The concrete checks performed and their results:

- Re-ran `scripts/classify_columns.py` from a clean checkout and diffed the output byte-for-byte
  against the committed `docs/column_classification.csv` — identical. Independently re-verified the
  43-column `allowed_for_bias=False` breakdown arithmetically (5 identifiers + 35 vintage-metadata +
  `rucc_covered` + `ghcn_covered` + `hwd_maxtemp_never_defined` = 43).
- Checked `docs/column_domain_map.csv` for duplicate `column_name` values across its 19 source
  tables (a potential collision hazard for the `n_distinct_by_column` dict keyed only by column
  name) — none found; all 232 column names are unique. Checked the same for
  `docs/coverage_null_profile.csv`'s national-scope rows — also unique.
- Confirmed how `n_distinct` is computed upstream (`series.nunique(dropna=True)` in
  `scripts/profile_coverage_and_nulls.py`): an all-null column reports `n_distinct=0`, which the
  `<= 1` override correctly catches (`spi_calibration` is exactly this case — 0 distinct values,
  forced `allowed_for_bias=False`) rather than being a silent edge case that only handles the
  "exactly one repeated value" scenario.
- Verified all 19 real columns that end in `_covered` are genuinely boolean-dtype coverage flags
  (matching what the code assumes purely from the name suffix) and confirmed every
  `derived_ever_flag` column (`fod_ever`, `mtbs_wildfire_ever`, `nifc_wildfire_ever`,
  `usgs_wildfire_ever`) has a corresponding `_covered` flag from the same source table, so the
  mandatory joint-interpretation caveat in its `bias_reason` is always actually satisfiable.
- Found and fixed one real (if minor) code-quality defect: `scripts/classify_columns.py` imported
  `VINTAGE_COLUMNS_BY_SOURCE_TABLE` from `scripts/confirm_domain_vintages` but never used it (only
  `all_vintage_columns()`, which wraps it, is actually called) — an unused import that a linter would
  flag and that added confusion about what the module actually depends on. Removed it; behavior is
  unchanged (confirmed via the same byte-for-byte diff above).
- Found a real, previously untested gap: `IDENTIFIER_COLUMNS`, `GEOMETRY_MEASURE_COLUMNS`,
  `POPULATION_COLUMNS`, `EVER_FLAG_COLUMNS`, and `IDENTITY_METADATA_COLUMNS` are all hand-typed sets,
  not derived from the data — exactly the same kind of hand-maintained list that already produced two
  real bugs this session (the `uhe_city_name`/`uhe_city_country` priority-order bug and the missed
  `epht_metric` vintage column). A typo in one of these sets would not raise an error anywhere; the
  mistyped name would simply never match a real column, and the real column would silently fall
  through to a later, wrong role. No such typo exists today (independently verified: every element of
  all five sets is present in the real 232-column domain map), but nothing previously would have
  caught one if introduced in a future edit. Added
  `test_every_hand_typed_column_set_member_actually_exists_in_the_real_domain_map` as a permanent
  regression guard.
- Added one further defensive real-data test,
  `test_real_run_every_coverage_flag_column_is_actually_boolean_dtype`, locking in that every column
  the `_covered`-suffix heuristic currently classifies as `coverage_flag` really is boolean —
  documenting and guarding the one naming-convention-based (rather than dtype-based) assumption in
  the classifier, so a future non-boolean column that happened to end in `_covered` would fail loudly
  here instead of being silently misclassified.

No incorrect classifications, scoring-eligibility leaks, or bias-eligibility miscalls were found in
this review pass — every finding was either a code-quality cleanup or a new safety net for a failure
mode that has not (yet) occurred. `tests/test_classify_columns.py` now has 32 tests; full project
suite: 310 passed, 2 skipped, zero third-party mentions on a final re-scan.

## 4.16 Stage 3 Step 6 — candidate_hypotheses tagging

`scripts/tag_candidate_hypotheses.py` fills in the fourth and final per-column governance field the
data dictionary needs: for every column of `national-strata-tract-table`, which of this project's
own ten pre-registered Bias Discovery candidates (`PROJECT_BLUEPRINT.md`'s Stage 9 table) does that
column actually feed, if any? Like Steps 2 and 5, this needs no live bucket access — it runs entirely
against already-committed data (`docs/column_domain_map.csv` from Step 2, `docs/
column_classification.csv` from Step 5), applying the fixed candidate pool from the blueprint rather
than inventing anything new.

**The tagging is a governance/traceability record, not a prediction of which candidate wins.**
Tagging a column means "this is raw material a candidate would draw on if it survives Stage 8's
funnel," not "this candidate will appear in the final writeup." Stage 9's Gate D confirms two or
three of the ten and drops the rest; nothing here pre-commits to an outcome.

**The rule, applied uniformly:** `allowed_for_bias=False` (43 columns) always means no tags,
regardless of role or domain — a column Step 5 already ruled out of bias analysis cannot un-rule
itself back in here. For the 189 `allowed_for_bias=True` columns, tags come from role first
(`coverage_flag` → Measurement Eligibility Bias; `derived_ever_flag` → that plus Component
Dominance; `geometry_measure` → Tribal Sub-type + Edge Effect and Dispatch-Blind Reachability;
`population` → Population Exposure vs. Disparity, Component Dominance, and Dispatch-Blind
Reachability; `identity_metadata` → four explicit, named per-column rules), then for the large
`measurement` role bucket, from domain (svi/cvi/wildfire/heat/drought → the three generic
vulnerability-covariate candidates; rurality → those plus Dispatch-Blind Reachability; tribal → all
of the above plus Tribal Sub-type + Edge Effect and Population Exposure), with two column-specific
additions on top: the nine real CVI pillar/sub-score columns also get CVI Pillar Decomposition
(`cvi_overall` and `cvi_xwalk_coverage` do not — decomposing past the composite is the whole point),
and the eight actual RUCA/RUCC/NCHS classification columns also get RUCA/RUCC/NCHS Disagreement
(`ruca_pop_density` does not — it's a covariate, not part of the three-system comparison).

**Real result**: 189/232 columns tagged (exactly the `allowed_for_bias=True` set — verified to be
the identical set, not just the same count), 43 blank. Per-candidate column counts: Measurement
Eligibility Bias 176, Source Provenance x Vulnerability 157, Component Dominance 164, Dispatch-Blind
Reachability 25, Population Exposure vs. Disparity 14, Tribal Sub-type + Edge Effect 13, CVI Pillar
Decomposition 9, RUCA/RUCC/NCHS Disagreement 8, and — independently confirmed, not just left
unpopulated by omission — **zero** for both Confidence Reporting-Rate vs. Reported-Confidence-Value
and Colonias in South-Central TX.

**Two candidates get zero strata-table columns, on purpose, and this is checked rather than
assumed.** A direct search across all 232 column names for anything suggesting a per-feature
confidence/reliability score (`conf`, `confidence`, `reliab`, `quality`, `moe`, `margin`) turns up
exactly one match, `ghcn_anchor_unreliable` — a GHCN weather-station anchoring data-quality flag,
not a reported-confidence value in the sense the Confidence Reporting-Rate candidate means. That
candidate's actual subject is Overture's own per-feature confidence score on buildings, roads, and
places, which lives in `reference/`, not `strata/`. Colonias in South-Central TX explicitly needs an
external colonias registry per the blueprint itself ("permitted for this prize only") — no strata
column can stand in for that. Both zero counts are locked in by permanent regression tests
(`test_real_run_confirms_the_two_zero_match_candidates_stay_at_zero`), and the flip side is tested
too (`test_real_run_every_candidate_that_is_not_supposed_to_be_zero_actually_has_columns`), so a
future edit that accidentally zeroes out a candidate that should have columns, or accidentally
starts feeding one of these two, fails loudly either way.

**The two explicitly DROPPED Stage 9 candidates (Wildfire-Rebuilt Areas; Heat-Island x SVI) are kept
entirely out of this step's taggable vocabulary** — `DROPPED_CANDIDATES` exists only for
documentation and as a permanent regression target (`test_real_run_no_column_is_ever_tagged_with_a_
dropped_candidate`, plus a second test that drives every rule branch directly rather than just
grepping the source, since a rule could in principle build a dropped name dynamically). A wildfire or
heat measurement column still legitimately feeds the three generic vulnerability-covariate
candidates — that is a different, broader claim than the specific, already-rejected wildfire-rebuild
or heat-island claims, and the two are deliberately kept apart.

**One real, previously untested per-column edge case, caught the same way as Step 5's review-pass
findings — by writing the test before trusting the code, not after.** The `identity_metadata` role
branch originally checked `column_name in IDENTITY_METADATA_TAGS` directly, with no `role ==
"identity_metadata"` guard around it; a column with any other role that happened to share a name
with one of the four hand-typed dict keys would have matched anyway, and — more importantly — an
`identity_metadata` column NOT yet in the dict (a real possibility if a future step adds a fifth
identity-metadata column) would have fallen all the way through to the function's final
`AssertionError` safety net meant only for the identifier/vintage_metadata invariant, crashing
instead of just returning no tags. Reproduced directly by writing
`test_unrecognized_identity_metadata_column_falls_through_without_crashing` and watching it fail
before touching the source. Fixed by making `identity_metadata` its own explicit branch that returns
an empty tag list (with a reason explaining a rule still needs to be added) rather than falling
through to the crash-on-purpose branch, which stays reserved for the one invariant it actually
guards (identifier/vintage_metadata are always `allowed_for_bias=False`, so reaching that branch at
all should be impossible).

`tests/test_tag_candidate_hypotheses.py`: 38 tests, all passing, including nine real-data regression
tests against the actual committed 232-column table. Full project suite: 348 passed, 2 skipped (same
sandbox-only DuckDB skip as always), zero third-party mentions on a final scan.
`docs/column_candidate_hypotheses.csv` (232 rows) is the fourth and final governance field Step 8
(the full data dictionary build) will merge in alongside `role`/`allowed_for_scoring`/
`allowed_for_bias` from Step 5.

**Independent review pass.** Before moving to Step 7, this step's own deliverables were reviewed
adversarially, the same discipline applied to Steps 2 and 5: re-derive the real output independently,
probe every hand-typed rule for a typo or a silent-fallthrough, and only then trust it. Two real
issues were found and fixed, both silent-failure risks rather than anything already wrong in the
committed `docs/column_candidate_hypotheses.csv` (re-confirmed byte-for-byte identical after both
fixes — neither changed a single real tag).

- **A measurement-role column in an unmapped domain would have silently gotten zero candidate
  tags — indistinguishable from a column deliberately left untagged.** `MEASUREMENT_DOMAIN_TAGS.
  get(domain, [])` quietly returned an empty list for any domain it didn't recognize. Today's real
  data never hits this (all seven measurement domains are mapped, confirmed by a new test that
  drives this directly off the real domain map: `test_real_run_every_measurement_domain_present_in_
  the_data_is_mapped`), but a future Step 2 re-run against a refreshed schema that introduced an
  eighth domain would have produced real, allowed-for-bias columns with blank tags and no error
  anywhere pointing at why. Changed `tag_column` to raise loudly instead when a measurement-role
  column's domain has no entry, matching the same "fail loud, not silent" standard as the
  identifier/vintage_metadata guard already in this function.
- **The candidate-counting logic (in `main()`'s printed summary and in several tests) used substring
  search (`series.str.contains(candidate, regex=False)`) over the semicolon-joined
  `candidate_hypotheses` text instead of parsing it into exact tags.** Verified no current candidate
  name is a substring of another (now a permanent regression test,
  `test_no_candidate_name_is_a_substring_of_another_candidate_or_dropped_name`, rather than a
  one-time manual check), so this was not actually miscounting anything today — but it was one
  rename away from silently double-counting a column for two different candidates. Added
  `parse_tags()`/`columns_feeding()`, which split the cell into an exact list instead, and switched
  every counting call site (production and tests) to use them.
- **While fixing `columns_feeding`, found and closed a related latent trap**: `docs/column_
  candidate_hypotheses.csv`'s blank cells (the 43 untagged columns) round-trip through plain
  `pd.read_csv` — the call any downstream script (Step 8's data dictionary build, most likely) would
  reach for first — as float `NaN`, not empty string, unless the reader remembers to pass
  `keep_default_na=False`. `parse_tags()` now explicitly tolerates `NaN`/`None`/empty-string as "no
  tags" so a future consumer of this CSV that doesn't know about that flag still gets the right
  answer instead of a crash. Proved this fix actually matters, not just in theory, by reading the
  real committed CSV back with plain `pd.read_csv` inside a new test and confirming
  `columns_feeding` gives the same per-candidate counts either way
  (`test_columns_feeding_matches_between_a_freshly_built_dataframe_and_the_real_csv_read_back_
  without_keep_default_na`).

No incorrect tags, no dropped-candidate leaks, and no mismatch between `allowed_for_bias=False` and
the blank-tag set were found — every finding here was a safety net for a failure mode that has not
(yet) occurred, in keeping with the same "code review found no wrong answers, but real hardening
gaps" pattern as Step 5's review. `tests/test_tag_candidate_hypotheses.py` now has 45 tests; full
project suite: 355 passed, 2 skipped, zero third-party mentions on a final re-scan.

## 4.17 Stage 3 Step 7 — region-vs-national schema consistency check

**Why this step exists.** Every governance fact Steps 2, 3, 5, and 6 produced (`docs/column_domain_
map.csv`, `docs/coverage_null_profile.csv`, `docs/column_classification.csv`, `docs/column_
candidate_hypotheses.csv`) was built by reading `national-strata-tract-table`, keyed by column NAME.
But the four study regions this project is actually scored on each ship their OWN separately-joined
strata table — `strata/<region>/<region>-strata-tract-table.parquet`, confirmed present in all four
regions' object listings (`docs/data_manifest.csv`) — not a slice of the national one. Nothing before
this step had actually confirmed that a region's own joined table has the same columns, in the same
dtypes, as the national one every governance field was built against. This step is that confirmation.

**Scope, deliberately stated.** This step inspects the one artifact every governance field actually
depends on — each region's own pre-joined `<region>-strata-tract-table` — across all four regions.
It does not re-inspect each region's other ~22-23 individual pre-join source tables (mirroring
`NATIONAL_STRATA_SOURCE_TABLES`); that would only become useful if this step's result raised a
question about HOW a region's joined table was assembled, which is a different question from the one
this step answers (does the column-name-keyed governance data from Steps 2/5/6 transfer safely to
each region).

**What is checked, for each region, against the already-committed national schema** (`docs/
national_strata_schema_raw.csv`, re-used as-is — this step fetches only the region side live, not
the national side again): column set (missing/extra columns by name), Arrow dtype per shared column,
column order (informational only — every script in this project reads columns by name, never
positionally, so a reordered-but-otherwise-identical schema is not itself a functional risk), and row
count against both of this project's two on-record expectations for that region
(`src.config.REGION_TRACT_COUNTS`, total tract membership, and `src.config.SCORED_TRACT_COUNTS`, the
narrower scorable-tract count — these already differ for South-Central Texas specifically, 6,010 vs
6,003, Section 4.7/4.8, so checking both rather than assuming one is itself part of the point).

**This step needs a live bucket read, unlike Steps 2/5/6** — each region's `<region>-strata-tract-
table` schema is a fact this project has never fetched before. `scripts/check_region_national_schema_
consistency.py` does this footer-only (`pq.ParquetFile(...).schema_arrow`/`.metadata.num_rows` — no
full download), reusing Stage 3 Step 1's own `inspect_table_schema` core function rather than
duplicating it. Added `src.config.STRATA_REGION_JOINED_TABLE = "strata-tract-table"` (paired with the
already-existing `strata_s3_path(region, table)` helper) as the named constant for this table family,
matching how `STRATA_NATIONAL_JOINED_TABLE` already names its national counterpart.

**Built and fully unit-tested before ever being run against the live bucket** — all four pure
functions (`load_national_joined_schema`, `compare_schemas`, `check_row_count`, `build_detail_rows`)
and the thin `inspect_region_table` wrapper (tested against a real local parquet fixture via
`pyarrow.fs.LocalFileSystem`, never the real bucket) are covered by `tests/test_check_region_
national_schema_consistency.py`, 25 tests, including `main()` exercised end-to-end via monkeypatched
inputs/outputs — this project's established pattern of never letting a script's first real execution
be against live data. One real, previously-seen bug class was caught and fixed before it could recur
here: the summary and detail CSVs' integer columns (`num_rows`, `national_position`, etc.) would have
silently upcast to `"1.0"`-style floats the moment any single region failed to load and left its own
numeric fields `None` in the same batch — the identical failure mode already fixed twice before in
this project (Stage 3 Step 1's `_NULLABLE_INT_CSV_COLUMNS`, Stage 3 Step 2's `_INT_COLUMNS`) — fixed
here with the same nullable-`Int64`-cast treatment and locked in by a dedicated regression test
(`test_main_integer_columns_never_round_trip_as_floats_when_a_region_fails`).

**Status: built, tested, verified end-to-end against the sandbox's own network restrictions (every
region correctly reports a graceful, non-crashing `ERROR` when the bucket is unreachable, and both
output CSVs still write cleanly with zero detail rows) — run live against the real bucket, findings
below.**

**Independent review pass, before that live run.** Given a region schema is, by definition, data
this project has never inspected before, this step's own review focused on what happens when the
live data surprises it — not just re-confirming today's already-known-clean national side. One real
gap was found and fixed, plus three additional tests added to lock in edge cases that were already
handled correctly but untested.

- **A region's own schema could carry a duplicate column name, and nothing would have caught it.**
  Every comparison function in this script builds a `dict(columns)` lookup at some point, which
  silently keeps only the last occurrence of a repeated name — precisely the failure mode Stage 3
  Step 1 already treats as a real, explicitly-checked risk category for the national tables
  (`duplicate_column_names` in `schema_risk_findings`). This step's whole reason for existing is
  that a region's joined table schema is NOT yet known-safe the way the national one is — so of all
  the checks in this project to skip for the region side, this was the wrong one to skip. Added
  `find_duplicate_column_names()` and wired it into `compare_schemas` as `duplicate_in_national`/
  `duplicate_in_region`, both now part of the `columns_match` pass/fail verdict and the summary CSV
  (`num_duplicate_in_national`/`num_duplicate_in_region`), with an explicit caveat that any other
  finding for a duplicated name is unreliable (since it too came from the same collapsing `dict()`).
  Checked defensively on the national side too, even though it is independently re-confirmed clean
  here (`test_real_national_joined_schema_has_no_duplicate_column_names`) — this function has no
  reason to treat that as an assumption it doesn't check itself.
- **Locked in, as a permanent test rather than a one-time read, the edge case where a region shares
  no columns with national at all**: `order_matches` is vacuously `True` in that case (there is
  nothing shared to be out of order), while `columns_match` is `False` — already correct behavior,
  now with a test making explicit that the two fields must always be read together, never
  `order_matches` alone as a pass signal.
- **Added a permanent test for the exact failure mode this review actually observed running the
  script** (all four regions unreachable from this sandbox): `detail_rows` stays empty, `pd.
  DataFrame([])` has zero columns, and both output CSVs must still write cleanly rather than hitting
  the "empty DataFrame has no columns to filter" crash Stage 3 Step 3's own review pass already
  found and fixed for a structurally identical case. This had already been manually verified working
  by actually running the script in the sandbox, but was not yet a permanent automated regression
  guard.

No incorrect comparison logic was found — `compare_schemas`'s missing/extra/dtype-mismatch/order
computations were all independently re-derived by hand against several constructed cases and matched
the code exactly. `tests/test_check_region_national_schema_consistency.py` now has 33 tests (was
25); full project suite: 388 passed, 2 skipped, zero third-party mentions on a final scan.

**Real, live findings (all four regions).** Every region reports the identical result — this is a
systematic, project-wide fact about how the region packages were built, not a one-off anomaly in any
single region:

- `columns_match = False` for all four regions, with the exact same column-set difference every time:
  **6 columns missing in the region table, 1 extra column present only in the region table.** Zero
  dtype mismatches on any of the 225 shared columns, in any region. `order_matches = True` in all
  four (the shared columns appear in the same relative order nationally and regionally).
- **The 6 missing columns, triaged against `docs/column_classification.csv`:**
  - `state_usps`, `state_name` (role=identifier) and `tract_vintage` (role=vintage_metadata) are all
    already `allowed_for_scoring=False` and `allowed_for_bias=False` — dropped from every region's
    joined table, and their absence costs nothing: no scoring path and no bias-discovery candidate
    was ever going to touch them.
  - `AWATER`, `INTPTLAT`, `INTPTLON` (role=geometry_measure) are the columns that actually matter.
    All three are `allowed_for_bias=True`, feeding **Tribal Sub-type + Edge Effect** and
    **Dispatch-Blind Reachability** — two of the ten candidate hypotheses tagged in Step 6. They are
    absent from every region's joined strata table, meaning the tract-geometry/centroid values those
    two candidates need cannot come from `<region>-strata-tract-table` at all; Stage 6+ analysis for
    those two candidates will need to source AWATER/INTPTLAT/INTPTLON from `<region>-census-tracts`
    instead (confirmed present in `NATIONAL_STRATA_SOURCE_TABLES`'s regional counterpart). This is a
    concrete, useful finding to carry forward, not a defect in this step.
  - No scoring impact whatsoever from any of the 6: `STRATA_NATIONAL_JOINED_TABLE` and
    `STRATA_REGION_JOINED_TABLE` are both governed by the Step 5 blanket rule — every column in a
    strata table, national or regional, is `allowed_for_scoring=False` by construction (the whole
    table lives under `strata/`, never `reference/`). Nothing here can move the leaderboard number.
- **The 1 extra column, `frac_inside_aoi`**, is new — it does not appear in
  `docs/column_domain_map.csv`/`column_classification.csv`/`column_candidate_hypotheses.csv` at all,
  because it was never part of the national schema those were built from. By name it reads as the
  fraction of each tract's area that falls inside the region's area-of-interest boundary, which is
  plausibly relevant to edge-effect and measurement-eligibility bias analysis (a tract that is only
  partially inside the study region is a natural edge case for both). Flagged here as a real, open
  item for Stage 3 Step 8's data-dictionary build to classify properly — not built or acted on now,
  per standing instructions to document rather than implement ahead of being asked.
- **Row counts confirm `REGION_TRACT_COUNTS` — total tract membership — as the correct cardinality
  reference for `<region>-strata-tract-table`, not `SCORED_TRACT_COUNTS`.** All four regions' live row
  counts matched `REGION_TRACT_COUNTS` exactly, and South-Central Texas is the decisive case: its
  strata table has 6,010 rows, matching `REGION_TRACT_COUNTS["south-central-tx"] = 6010`, not
  `SCORED_TRACT_COUNTS["south-central-tx"] = 6003`. The strata table therefore carries every tract in
  the region, including the 7 South-Central Texas tracts that are not scorable — any Stage 6+ script
  computing a scored metric must still filter to the region's `sample-submission.csv` GEOID list
  before aggregating; the strata table alone is not pre-filtered to scored tracts.
- **The two clean results — zero dtype mismatches and `order_matches = True` in every region — rule
  out the riskiest possible failure mode this step existed to catch**: silent type drift between the
  national and regional builds of the same table family. That risk is now closed for all four
  regions.

## 4.18 Stage 3 Step 8 — the full data dictionary build

**Why this step exists.** Steps 1-7 each answered one narrow question about `national-strata-
tract-table`'s 232 columns — what exists, what domain each belongs to, how complete each is,
whether its vintage is current, whether it may be used for scoring or bias analysis, which Bias
Discovery candidate(s) it can feed, and whether the national schema matches what each region ships.
Answering any one question about one column meant opening the right one of seven separate CSVs.
This step does not repeat any of that analysis — it assembles Steps 1-7's already-committed outputs
into one machine-readable catalog (`docs/schema_catalog.csv`) and one human-readable reference
(`docs/DATA_DICTIONARY.md`), built by `scripts/build_data_dictionary.py`, so every fact about every
column lives in one place.

**One genuinely new fact was resolved here, not merely carried over.** Step 7's live region-schema
read found `frac_inside_aoi` — present in all four regions' own joined tables, absent from the
national schema, so it was never seen by Steps 2, 5, or 6 — and deliberately deferred classifying
it, flagging it as an open item for this step. It is resolved here two ways at once: its real
values are read live (column-pruned — GEOID plus `frac_inside_aoi` only — from all four regions,
concatenated to 9,386 real rows), and it is classified using the exact reasoning Steps 5/6 already
applied to the structurally closest existing columns (`AWATER`/`INTPTLAT`/`INTPTLON`,
role=geometry_measure): `allowed_for_scoring=False` (the same table-wide blanket rule — this column
lives in the region-level counterpart of the same `strata/` table family, never `reference/`), and
`allowed_for_bias=True`, tagged **Tribal Sub-type + Edge Effect only** (deliberately not also
Dispatch-Blind Reachability, which is about a tract's physical size/location, not how much of it a
region's own study boundary happens to clip). The reasoning: a tract with a low `frac_inside_aoi`
is only partially inside the study region — the same geometric edge-case Tribal Sub-type + Edge
Effect already exists to examine for tribal lands that straddle a boundary, generalized here to
every tract at a region's edge, tribal or not. Flagged explicitly as a Stage 8/9 judgment call
whether this earns its own place in that candidate's writeup or stays a supporting covariate — not
decided unilaterally here, and not elevated into an eleventh candidate outside the ten-candidate
pool the project blueprint already established.

**Vintage status is transcribed, not re-derived.** `docs/data_vintage_confirmation.md` (Step 4)
already did the real external-research work; `scripts/build_data_dictionary.py`'s
`VINTAGE_STATUS_BY_SOURCE_TABLE` is a hand-typed, one-entry-per-source-table transcription of that
document's own conclusions (vintage is a property of the underlying dataset a source table came
from, not of any individual column within it) — `confirmed` (13 tables), `confirmed_with_
clarification` (6 tables — CDC WONDER's county-not-tract grain, MTBS's one-release-behind status,
EPHT's threshold-confirmed-but-window-unresolved split, CVI's 2010-geography clarification, NASA's
gehe-confirmed/uhe-strengthened split), `unresolved` (2 tables — drought.gov, NOAA GHCN),
`ambiguous_no_marker` (1 table — tribal, no in-file vintage column), `confirmed_but_flagged` (1
table — NCHS, the deliberately-tempered vintage-lag candidate Step 4 already deferred to Stage
8/9), and `not_applicable` (6 tables — the geometry-only boundary/station tables plus the
county-level `national-cdc-wonder-heat-mortality` reference table, none of which contribute
attribute columns to the 232-column joined table, confirmed directly against `docs/column_domain_
map.csv`'s 19 real source_table values). Keys are checked by a permanent regression test against
`src.config.NATIONAL_STRATA_SOURCE_TABLES` — the same hand-typed-set discipline every prior Stage 3
step has used (Steps 4/5/6's own regression tests).

**Design and testing.** Testable-core / thin-real-path-wrapper, the same pattern used throughout
this project. Every merge/render function (`load_national_joined_columns`, `summarize_region_
presence`, `profile_series`, `build_frac_inside_aoi_row`, `build_catalog`, `render_data_dictionary_
markdown`) is pure and fully unit-tested with no network — including a merge-integrity guard
(`validate="one_to_one"` on every join, so a future upstream file silently growing a duplicate row
for one column fails loudly here instead of silently fanning out that column's row). `read_frac_
inside_aoi_column` is the one thin, live-bucket-touching wrapper (column-pruned read, not a full-
table download), tested against a real local parquet fixture via `pyarrow.fs.LocalFileSystem`,
never the real bucket — including the same early-binding regression test every other wrapper in
this project carries (a monkeypatch of the imported `strata_s3_path` name after the module loads
does not affect a call that omits `path_fn=`). One real, previously-seen bug class was checked for
proactively before it could recur here, given this step appends one new row (`frac_inside_aoi`,
whose `national_position` is `pd.NA`) onto 232 rows with real integer positions: verified directly
that the WRITTEN CSV's `national_position` values never round-trip as `"1.0"`-style floats (the
concatenated column stays `object` dtype holding real Python ints plus one `NA`, not `float64` —
confirmed by inspecting the raw file text, not a re-parsed DataFrame, since re-reading any CSV with
a NaN would itself upcast that column to float64 and mask the very bug being checked for), locked
in as a permanent regression test. `tests/test_build_data_dictionary.py` has 23 tests, all passing
against the real, already-committed Step 1-7 outputs (offline, via `--skip-live-read`) as well as
hand-built fixtures. Full project suite: 411 passed, 2 skipped (the same sandbox-only DuckDB
extension-download skip as every previous step), zero third-party mentions on a final scan.

**Status: built and fully tested offline against the real, already-committed Steps 1-7 outputs
(233-row catalog produced correctly with `--skip-live-read`) — awaiting the one live read this step
needs (`frac_inside_aoi`'s real values across all four regions) from Henry's machine.** This section
will be updated with the real live findings — the actual null rate/min/max/mean/distinct-value
count for `frac_inside_aoi` across all four regions — once that run completes.

**Independent review pass, before that live run.** A dedicated review of this step — script, test
suite, and the rendered `DATA_DICTIONARY.md` output itself, not just re-reading what was already
written — found four real gaps, all fixed, plus one documentation-completeness gap the review
surfaced by actually reading the rendered output rather than only the code.

1. **The most significant finding: `build_catalog`'s five `how="left"` merges had no check for a
   MISSING match, only a duplicate one.** `validate="one_to_one"` (used on every merge) guards
   against an upstream file silently growing a duplicate row for a column — but a left join fills a
   column's fields with NaN, silently, if that column has NO row at all in an upstream file, and
   `validate="one_to_one"` says nothing about that failure mode. Every one of Steps 2/3/5/6/7's
   output CSVs is a file this script does not control the shape of; a future stale or partially
   regenerated file could have quietly produced blank role/allowed_for_scoring/candidate_hypotheses
   fields for one column, with nothing catching it. Fixed: `assert_catalog_completeness`, called
   immediately after the five merges, checks a fixed list of fields that must never be null for a
   real national column (deliberately excluding `candidate_hypotheses` itself, which IS legitimately
   blank for 43/232 columns, while still requiring `candidate_hypotheses_reason` — Step 6 always
   fills a reason even for a blank tag) and raises `AssertionError` naming exactly which columns are
   affected. A closely related gap in the same spot: the hand-typed `VINTAGE_STATUS_BY_SOURCE_TABLE`
   lookup used `.get(t, ("not_profiled", ""))` — a default that would silently mask a typo or a
   future source-table rename rather than failing loudly, the opposite of this project's own stated
   discipline. Fixed: the default is now a sentinel (`MISSING_VINTAGE_ENTRY`) checked immediately by
   `assert_no_missing_vintage_status`, which raises with the exact offending source table(s) named.
2. **`main()`'s live-read loop over the four regions had no per-region failure isolation at all** —
   unlike Steps 1 and 7, which explicitly established that one region's read failing must not stop
   the others from being checked. A single network hiccup on any one region would have crashed the
   entire run and produced NO output files, a real regression against a discipline this project
   already committed to twice. Fixed: each region's read is now wrapped individually; a failure is
   reported and that region is excluded from the combined profile rather than aborting the run,
   the whole run aborts (without writing output) only if every region fails, and `profile_scope`
   now names exactly which regions actually contributed to the numbers it reports (never silently
   claims "4 regions" for a number built from 3).
3. **`args.dictionary_output`'s parent directory was never created before writing**, unlike
   `args.catalog_output`'s (which was) — invisible in every test so far because the default and
   every test `tmp_path` already exist as directories, but a real `--dictionary-output` pointing at
   a not-yet-created subdirectory would have raised `FileNotFoundError` on write. Fixed with the
   same `mkdir(parents=True, exist_ok=True)` `args.catalog_output` already had.
4. **Documentation-completeness gap, found by reading the rendered `DATA_DICTIONARY.md` itself, not
   the code**: Step 3's sentinel-value findings (e.g. the Microsoft Building Footprints
   `confidence == -1.0` placeholder, Section 4.8) were fully present in `schema_catalog.csv` but
   completely invisible in the human-readable dictionary — exactly the kind of proactive data-
   quality finding a Best Documentation judge would want surfaced without having to separately open
   a CSV. Fixed: a new "Possible coded-missing sentinel values" section lists every column with a
   non-empty `sentinel_note`. (No such column exists within `national-strata-tract-table` itself
   today — the Microsoft-buildings example lives in a different, `reference/`-layer table — so this
   section renders empty against the real data right now; it is there so a future column carrying
   one is never silently dropped from the human-readable side again.)

`tests/test_build_data_dictionary.py` grew from 23 to 33 tests — 10 new tests covering the
missing-match completeness guard, the vintage-sentinel guard, `profile_scope`'s region-aware text
(full four regions, a partial set, and zero regions), the sentinel-value markdown section (both
present and absent), the dictionary-output mkdir fix, and `main()`'s per-region isolation under a
simulated single-region failure and a simulated total-outage abort. Full project suite: 421 passed,
2 skipped (the same sandbox-only DuckDB extension-download skip as every previous step), zero
third-party mentions on a final scan.

**Real, live run results.** Henry ran `python -m scripts.build_data_dictionary` against the live
bucket:

```
maricopa-az: 1,593 row(s)
northern-ca: 591 row(s)
eastern-ok: 1,192 row(s)
south-central-tx: 6,010 row(s)
combined (4/4 region(s)): {'n_rows': 9386, 'n_null': 0, 'pct_null': 0.0, 'n_distinct': 1, 'min': 1.0, 'max': 1.0, 'mean': 1.0}
```

All four regions loaded cleanly (4/4, zero failures — the per-region isolation fix from the earlier
review pass was never actually exercised on this run, since nothing failed). Row counts match
`REGION_TRACT_COUNTS` exactly for all four regions, the same total-tract-membership figure Step 7
already established as the correct cardinality for a region's own strata table. `docs/schema_
catalog.csv` (233 rows) and `docs/DATA_DICTIONARY.md` were both generated and independently
re-verified (pulled from Henry's machine and inspected directly): row count, column count, no
duplicate column names, the integer-formatting regression test's guarantee held on the real file
(`national_position` never round-trips as `"1.0"`), and the two documented-absent sections
(`## Columns absent from every region's own joined table`, listing exactly the same 6 columns as
Step 7) and (`## Region-only addition`, `frac_inside_aoi`) both rendered correctly, with the 232
national columns' domain-table row counts summing to exactly 232.

**A real, substantive finding, not just a clean run: `frac_inside_aoi` is constant at 1.0 across
every single one of the 9,386 tracts in all four regions (n_distinct=1, zero nulls).** This means
every tract in this project's four pre-packaged study regions is entirely inside its own region's
area-of-interest boundary — none of the four regions contains a single tract that straddles the AOI
edge. Concretely, this project's four study regions carry no partial-tract-containment edge cases at
all in this data.

**This directly triggered a real bug in this step's own original hand-classification**, caught only
because the live read actually happened rather than being assumed: `frac_inside_aoi` had been
hand-classified `allowed_for_bias=True` on the (reasonable-sounding, but unverified) theory that a
low value would signal a boundary-straddling tract. A constant column carries zero discriminative
signal for any bias analysis, however plausible its role-based reasoning sounds — this is exactly
the same hard, data-driven override Step 5 already established for every one of the 232 national
columns (`scripts/classify_columns.py`'s `compute_allowed_for_bias`: any column with `n_distinct <=
1` is forced to `allowed_for_bias=False` regardless of role), and this step's original static
`allowed_for_bias=True`/`candidate_hypotheses="Tribal Sub-type + Edge Effect"` for `frac_inside_aoi`
never actually applied that same rule to itself. Fixed: `build_frac_inside_aoi_row` no longer
hand-sets `allowed_for_bias`/`candidate_hypotheses` as static constants — it computes them from the
real `n_distinct` in the live profile, applying the identical override. Confirmed against the real
committed catalog: `frac_inside_aoi` now correctly shows `allowed_for_bias=False`,
`candidate_hypotheses=""`, and a `bias_reason` stating the constant-value finding explicitly
(`"constant across all 9,386 tracts profiled live (n_distinct=1, value=1.0) — carries no
discriminative signal for any bias analysis, regardless of role"`). The non-constant, geometry-
measure-based classification is preserved as a fallback should this project ever extend to a
region/vintage where `frac_inside_aoi` genuinely does vary, and an explicit `PROVISIONAL` label is
attached whenever the classification runs with no live data at all (`--skip-live-read`, or every
region failing), so an incomplete run can never present an unconfirmed classification as settled.
Nine new tests added (`tests/test_build_data_dictionary.py`, now 36) covering the constant-value
override firing exactly as it did on the real data, the non-constant fallback, and the
no-live-data provisional label — plus an end-to-end simulation of Henry's exact live result
(4-region reads returning constant 1.0, run through the real `main()`) confirming the fix produces
`allowed_for_bias=False` byte-for-byte the way the real re-run will. Full project suite: 424 passed,
2 skipped, zero third-party mentions on a final scan.

**Status: closed.** The re-run produced the identical live values as before (`n_rows=9386`,
`n_null=0`, `n_distinct=1`, `min=max=mean=1.0`, 4/4 regions loaded), confirming the constant-value
finding is real and reproducible, not a fluke of one run. `docs/schema_catalog.csv` (233 rows,
zero duplicate column names) and `docs/DATA_DICTIONARY.md` were both independently re-pulled from
Henry's machine and inspected directly against the corrected script, not just re-read from the
console log:

- `frac_inside_aoi`'s row now shows exactly what the fix was supposed to produce:
  `allowed_for_scoring=False`, `allowed_for_bias=False`, `candidate_hypotheses` blank, and
  `bias_reason` stating the constant-value finding in full ("constant across all 9,386 tracts
  profiled live (n_distinct=1, value=1.0) — carries no discriminative signal for any bias analysis,
  regardless of role... fires here too").
- Every one of `assert_catalog_completeness`'s required fields is populated for all 232 national
  columns (checked directly, not just inferred from the run not crashing); `vintage_status` never
  shows the `MISSING_VINTAGE_ENTRY`/`not_profiled` sentinels.
- The integer-formatting regression is clean on the real file: `national_position` never
  round-trips as a `"1.0"`-style float anywhere in the 233 rows.
- `DATA_DICTIONARY.md` renders both the "Columns absent from every region's own joined table"
  section (the same 6 columns Step 7 found) and the "Region-only addition" section for
  `frac_inside_aoi`, now correctly showing `allowed_for_bias=False, candidate_hypotheses=''` and the
  constant-value reasoning in the human-readable form; the nine domain tables' row counts sum to
  exactly 232.

Stage 3 Step 8 is complete. `docs/schema_catalog.csv` and `docs/DATA_DICTIONARY.md` are both
real, live-verified, and correctly reflect the one genuinely new fact this step surfaced: none of
this project's four study regions contains a tract that straddles its own area-of-interest
boundary, and that finding — not a guessed edge-effect signal — is what `frac_inside_aoi`'s
dictionary entry now says.

## 4.19 Stage 3 Step 9 — enforcement test for the exit criterion itself

Step 8 built the data dictionary once and verified that single build by hand, twice, against real
live output. That is not the same thing as a standing guarantee that the dictionary stays correct
as the project moves forward — a later edit to any upstream Step 1-7 artifact, or a hand-edit to
`docs/schema_catalog.csv`/`docs/DATA_DICTIONARY.md` themselves, could silently break one of the
facts already verified without anyone noticing. Step 9 closes that gap: it is a permanent pytest
file, `tests/test_data_dictionary.py`, that checks the real, already-committed dictionary files
directly — not synthetic fixtures — every time the suite runs, including in CI on every future
commit. This is Gate A ("Data Trusted") closing enforcement test: as long as this file passes, the
data dictionary can be trusted as an input to every later stage.

This is a different kind of test file from `tests/test_build_data_dictionary.py` (Step 8's own
suite). That file exercises the *build logic* — pure functions fed synthetic inputs, checking they
transform correctly in isolation. `tests/test_data_dictionary.py` instead exercises the *real
committed output* — it reads `docs/schema_catalog.csv` and `docs/DATA_DICTIONARY.md` off disk as
they exist right now, on this run, and checks 19 concrete facts about them directly. The two files
are complementary and neither substitutes for the other: the build-logic suite would still pass if
someone hand-edited the committed CSV to inject a scoring-eligible column; this suite would catch
that immediately.

The whole file is protected by a `pytest.mark.skipif` guard: if any of the eight required
artifacts (the two dictionary outputs plus the six upstream Step 1-7 CSVs) is missing from the
checkout, every test in the file skips with a clear reason rather than failing with a confusing
file-not-found error — the same pattern already used elsewhere in this project for tests that
depend on real committed data rather than synthetic fixtures.

What the 19 tests check, grouped by what they protect:

- **The scoring-safety invariant** (1 test): every single row in `schema_catalog.csv` has
  `allowed_for_scoring=False`, with zero exceptions. This is the single most consequential fact in
  the entire dictionary — if it were ever violated, a column from `strata/` could leak into the
  scored coverage-gap computation. Checked directly against the real file's raw values, not
  inferred from anything in code.
- **Shape and identity** (3 tests): the catalog has exactly 233 rows with no duplicate
  `column_name` values; exactly one row is `region_only=True` and it is `frac_inside_aoi`; every
  real national schema column (re-derived live from `national_schema.csv`, not hard-coded) appears
  somewhere in the catalog.
- **Traceability to every upstream step** (1 parametrized test, 3 cases): every national-schema row
  in the catalog has a matching row in `column_domain_map.csv` (Step 2), `column_classification.csv`
  (Step 5), and `column_candidate_hypotheses.csv` (Step 6), and vice versa — no column silently
  dropped or invented anywhere along the five-step merge chain.
- **Internal consistency of the bias-tagging rules** (3 tests): no column with
  `allowed_for_bias=False` carries a candidate hypothesis (Step 6's own rule, re-checked here
  against the real file); no `candidate_hypotheses` value anywhere is one of the two explicitly
  dropped candidates (Wildfire-Rebuilt Areas, Heat-Island x SVI); every `candidate_hypotheses` value
  anywhere is a member of the canonical ten-candidate pool — both of the last two reuse
  `scripts/tag_candidate_hypotheses.py`'s own `parse_tags`/`ALL_CANDIDATES`/`DROPPED_CANDIDATES`
  rather than re-implementing tag parsing.
- **Vintage completeness** (1 test): no row shows the `MISSING_VINTAGE_ENTRY` or `not_profiled`
  sentinel — every column has a real, resolved vintage status.
- **The Step 7 region-presence finding stays locked** (1 test): the exact set of six columns
  confirmed absent from all four regions' own joined tables (`state_usps`, `state_name`, `AWATER`,
  `INTPTLAT`, `INTPTLON`, `tract_vintage`) is re-derived from the real committed
  `present_in_all_four_regions` column and compared against the frozen expected set — this is a
  direct regression lock, not just a smoke test.
- **A direct regression lock on the bug this step's own history surfaced** (1 test): the real
  `frac_inside_aoi` row is checked against its confirmed live finding — `n_distinct=1`,
  `allowed_for_bias=False`, blank `candidate_hypotheses`, `allowed_for_scoring=False`, and a
  `bias_reason` that actually mentions the constant-value finding. If a future refactor ever
  reintroduced the exact classification bug Step 8's live run caught, this test fails immediately.
- **The CSV integer-formatting regression, checked the correct way** (1 test): reads
  `schema_catalog.csv` as raw text and regexes for any `national_position` value ending in `.0`,
  rather than re-parsing it with pandas — re-parsing would itself upcast and silently mask exactly
  the bug being checked for, a mistake this project has made and fixed more than once already.
- **Full reproducibility from real committed inputs** (1 test, the most rigorous in the file):
  rebuilds `schema_catalog.csv` from scratch using only the six real, committed upstream CSVs and
  `scripts/build_data_dictionary.py`'s own `build_catalog`, without touching the live bucket. The
  one row that structurally depends on a live read — `frac_inside_aoi` — is handled by recovering
  its exact live-read profile (row count, null count, distinct count, min/max/mean, and which
  regions were included) directly out of the committed row's own `profile_scope` text and numeric
  columns, then feeding that recovered profile back into `build_frac_inside_aoi_row`. The rebuilt
  catalog is written to a temporary CSV and re-read (so both sides go through the same round-trip
  and harmless dtype artifacts cancel out), then compared field-for-field against the real
  committed file with `pandas.testing.assert_frame_equal`. Any drift between the committed file and
  what its own declared inputs actually produce — a stale commit, a hand-edit, a silent upstream
  change — fails this test.
- **`DATA_DICTIONARY.md` content checks** (4 tests): the nine `### <domain> (N columns)` headings
  sum to exactly 232; the "Columns absent from every region's own joined table" section lists
  exactly the same six columns as the CSV-level check above; the "Region-only addition" section for
  `frac_inside_aoi` reflects the corrected classification (`allowed_for_bias=False`,
  `candidate_hypotheses=''`); the document states plainly that `allowed_for_scoring` is `False` for
  every row.

**Verification performed before delivery**: every one of the 19 tests passed cleanly on the first
run against the real committed files. A clean first pass is not itself trusted here — Step 8's own
history showed that a script can run without error and still be wrong — so each of the eight most
consequential tests was independently stress-tested by deliberately corrupting a temporary copy of
the real committed files (backed up first) and confirming the exact targeted test, and only that
test, failed with a clear, correct message:

- Flipped one row's `allowed_for_scoring` to `True` → the scoring-safety test failed, naming the
  exact corrupted column.
- Flipped `GEOID`'s `present_in_all_four_regions` to `False` → the six-column regression-lock test
  failed, showing the drifted set.
- Appended `.0` to one `national_position` value at the raw-text level → the CSV integer-formatting
  test failed, naming the exact corrupted row.
- Inflated one domain heading's count in `DATA_DICTIONARY.md` by 5 → the domain-sum test failed
  with the correct wrong total.
- Deleted one bullet from the "absent from every region" section → the section-content test failed,
  naming the missing column.
- Changed the `frac_inside_aoi` region-only section text to the pre-fix (buggy) classification →
  the region-only section test failed.
- Changed `GEOID`'s `domain` value in the committed CSV to a nonsense value → the full
  reproducibility test failed, pinpointing the exact column and row where the committed file
  diverged from what its own real inputs produce.

After each sabotage check, the corrupted file was restored from its backup and a `diff` against the
original confirmed byte-for-byte restoration before moving to the next check. After all seven
checks, the full project test suite was run once more from the clean, restored files: **443
passed, 2 skipped** (the 2 skips are the pre-existing, environment-only DuckDB spatial-extension
skips noted throughout this project — unrelated to this step). `tests/test_data_dictionary.py`
itself was scanned for any third-party or AI-tool attribution language — zero matches.

Step 9 needs no live-bucket access and required no new script — it is pure enforcement logic
against artifacts Step 8 already produced, matching this project's standing rule not to build
tooling beyond what a step actually requires.

#### Follow-up review pass: two real latent bugs found and fixed, one real test-coverage gap closed

Given how consequential Gate A is to the rest of this project, a second, independent review pass
was run over everything Step 9 touched — `scripts/build_data_dictionary.py`,
`tests/test_data_dictionary.py`, and `tests/test_build_data_dictionary.py` — specifically hunting
for anything the first pass had missed, rather than re-confirming what it had already checked. That
pass found three real issues, none of which affected the actual shipped `docs/DATA_DICTIONARY.md`
(confirmed below), but all three worth fixing before trusting this code for anything downstream:

1. **A real coverage gap**: every existing test checked `docs/schema_catalog.csv` and
   `docs/DATA_DICTIONARY.md` separately, against fixed expectations — none of them confirmed the
   two files actually agree with each other. Two individually-plausible files can still silently
   drift apart (a hand-edit to one but not the other, or a future rendering-logic change applied to
   one path but not the other) without any single-file check ever catching it. Closed by a new
   test, `test_committed_dictionary_markdown_matches_the_committed_schema_catalog`, which re-renders
   `DATA_DICTIONARY.md` directly from the real, committed `schema_catalog.csv` (via
   `render_data_dictionary_markdown`, the same function `main()` calls) and asserts byte-for-byte
   equality with the real, committed file.
2. **A real bug this new test immediately surfaced**: `render_data_dictionary_markdown`'s
   region-only section formatted `candidate_hypotheses` with no null guard, unlike the domain-table
   code path a few lines below it, which already had one. A blank `candidate_hypotheses` — exactly
   what `frac_inside_aoi`'s own real row carries, once its constant-value override fires — round-
   trips through a plain `pd.read_csv()` as float `NaN`, not an empty string, so re-rendering from a
   re-read CSV printed the literal text `candidate_hypotheses=nan` instead of `candidate_hypotheses=
   ''`. Fixed with the same `pd.notna(...)` guard already used one section below. Confirmed this
   never affected the real, shipped file: `render_data_dictionary_markdown` called on the true
   in-memory catalog `main()` actually builds (never a re-read CSV) was independently verified
   byte-identical to the real committed `DATA_DICTIONARY.md` before this fix was even written — the
   bug was a real robustness hole for any future caller re-rendering from a saved CSV (which is
   exactly what the new cross-file test above does), not a defect in what shipped.
3. **A second real bug the same new test then surfaced once the first was fixed**: the domain
   tables' `sort_values("national_position")` call trusted whatever dtype the caller's DataFrame
   happened to carry for that column. `main()`'s real call path always sees a numeric
   `national_position`, but reading `schema_catalog.csv` back with `keep_default_na=False` — the
   correct way to preserve a blank `candidate_hypotheses` cell, and exactly what the new cross-file
   test does — turns `national_position` into a STRING column, because `frac_inside_aoi`'s own
   blank `national_position` cell prevents the whole column from being inferred as numeric. Sorted
   as strings, `"10"` sorts before `"9"`, silently scrambling every domain table with ten or more
   columns rather than raising any error. Fixed by sorting with an explicit
   `key=lambda s: pd.to_numeric(s, errors="coerce")`, which is a no-op on the real numeric path and
   correct on the string path.

Both fixes were locked in with dedicated regression tests in `tests/test_build_data_dictionary.py`
(`test_render_data_dictionary_markdown_region_only_section_is_nan_safe_for_blank_candidate_
hypotheses`, covering both `float('nan')` and `pd.NA`; `test_render_data_dictionary_markdown_sorts_
domain_tables_numerically_even_when_national_position_is_string_typed`), and each was verified the
same "break it to prove it" way as every other fix in this project: the fix was temporarily reverted,
the corresponding test was confirmed to fail with the expected message, then the fix was restored
and the test re-confirmed passing. The new cross-file consistency test itself was also sabotage-
verified: a one-word corruption to the real committed `DATA_DICTIONARY.md` (`confirmed` →
`unresolved` in one table cell) was confirmed to fail the test, then the file was restored and
`diff`-confirmed byte-for-byte clean.

Suite counts after this review pass: `tests/test_data_dictionary.py` 19 → 20 tests, `tests/
test_build_data_dictionary.py` 36 → 38 tests, full project suite 443 → **446 passed, 2 skipped**
(same pre-existing, environment-only DuckDB skips). All files re-scanned for third-party or
AI-tool attribution language after these edits — zero matches.

Stage 3 Step 9 is complete, and with it, Gate A ("Data Trusted") is closed: every fact this project
depends on about the joined schema — its shape, its scoring eligibility, its bias-tagging rules, its
vintage status, and its region-presence gaps — is now both documented and permanently enforced by a
test that reads the real files, not just a script that produced them once, and the two files that
carry those facts (`docs/schema_catalog.csv` and `docs/DATA_DICTIONARY.md`) are now also verified
to agree with each other, not just individually plausible.

## 4.20 Pre-Stage-4 full Stage 3 review pass

Before starting Stage 4 (Repository Restructure), every Stage 3 file — every script, every module
under `src/`, every test, and the one notebook — was reviewed a second time end to end, specifically
hunting for bugs, incorrect implementations, silent failure modes, and test-coverage gaps, rather
than re-confirming what Steps 1-9 already established. Each finding below was independently
reproduced against the real, already-committed code before being treated as confirmed (this
project's standing "break it to prove it" discipline) — not accepted on a first read. Two real,
previously-undetected bugs were found and fixed; two smaller latent/cosmetic defects were found and
fixed; one defensive hardening fix was applied preemptively; and one already-self-documented data
staleness item (Section "Correction found while building Stage 3 Step 5" in `docs/data_vintage_
confirmation.md`) remains open pending a live re-run on the machine with bucket access.

**1. `src/io.py`'s `_assert_geoid_is_string` — false positive on a null-containing, otherwise valid
string GEOID column.** This guard, run on every strata/national-strata/sample-submission load in the
pipeline, used `pd.api.types.is_string_dtype(...)`. Under this project's pinned pandas (2.3.3), that
function falls through to `is_all_strings` for an object-dtype column, which inspects every element
— including nulls — and returns `False` the moment any element is `None`/`NaN`, even when every
non-null value is a real string. Reproduced directly:
```python
df = pd.DataFrame({"GEOID": ["04013010101", None, "04013010102"]})
_assert_geoid_is_string(df, context="repro")
# ValueError: ...expected a string dtype... (misdiagnosed as an integer-coercion bug)
```
This would have hard-failed, with a misleading "integer GEOID" diagnosis, on any otherwise-correct
strata table that legitimately has a missing GEOID in one row — a real risk given several strata
tables' documented null-rate profiles (Section 4.14). **Fixed** by switching to `pd.api.types.
infer_dtype(df[STRATA_KEY_COLUMN], skipna=True)`, which correctly ignores nulls when classifying the
non-null values, accepting `"string"` and `"empty"` (all-null column — a presence question for the
caller, not this guard) and rejecting everything else (confirmed `"floating"`/`"integer"` are still
correctly rejected). Three new regression tests added to `tests/test_io.py` (null-containing valid
string column accepted; null-containing integer column still rejected; all-null column accepted as
a no-op); the fix was confirmed load-bearing by reverting it and confirming the new tests fail
against the pre-fix code, then restoring it and re-confirming they pass.

**2. `scripts/build_data_dictionary.py`'s `summarize_region_presence` — silently wrong
`missing_from_regions` for a column absent from a region's schema entirely.** Step 7's per-region
detail CSV (`docs/region_national_schema_consistency.csv`) only ever emits a row for a
(column, region) pair when that region's own schema block actually carries the column at all —
every region's national columns, plus that region's own extra-in-region-only columns. A column
present in only some of the four regions therefore never gets a row at all for the regions that
lack it outright (as opposed to a row with `in_region=False`). The function computed `missing_from_
regions` as `group.loc[~group["in_region"], "region"]` — which is empty whenever every row that
*does* exist for a column happens to have `in_region=True`, silently reporting `missing_from_
regions=""` for a column genuinely absent from half the regions, even though `present_in_all_four_
regions` itself was still computed correctly as `False`. This field is published verbatim into
`docs/DATA_DICTIONARY.md`. Not yet live-wrong today — the one real extra-in-region-only column
(`frac_inside_aoi`) happens to be present in all four regions — but a landmine for the next
region-only column. Reproduced with a synthetic 2-of-4-region fixture (rows only for the two present
regions): before the fix, `missing_from_regions=""`; correct answer is the two genuinely-absent
region names. **Fixed** by computing `missing` as the set difference between a fixed, complete
region list and the regions actually present for that column (added an `all_regions` parameter,
defaulting to `src.config.REGIONS`, so the pure function stays testable with synthetic labels while
production always uses the real four regions) — this now catches both "row exists with
`in_region=False`" and "no row at all for this region" as equally missing. Three new tests added to
`tests/test_build_data_dictionary.py`, the pre-existing three updated to pass `all_regions`
explicitly (they test pure logic with synthetic `a/b/c/d` labels, not real region names); fix
confirmed load-bearing the same revert-and-restore way as above.

**3. `scripts/tag_candidate_hypotheses.py`'s `identity_metadata` branch of `tag_column` — list
aliasing bug.** Returned `IDENTITY_METADATA_TAGS[column_name]` directly — the live list object
stored in the module-level dict — rather than a copy, unlike every other branch (the `measurement`
branch explicitly does `list(MEASUREMENT_DOMAIN_TAGS[domain])`, with its own dedicated
anti-aliasing regression test). Currently harmless (`build_tagging` never mutates a returned tags
list), but a real defect: any future caller mutating the returned list in place would silently
corrupt `IDENTITY_METADATA_TAGS`'s entry for every subsequent call for that column name. **Fixed**
by wrapping in `list(...)`, matching the measurement branch's pattern exactly. New regression test
added to `tests/test_tag_candidate_hypotheses.py`, mirroring the existing measurement-branch
anti-aliasing test; confirmed load-bearing the same way.

**4. `scripts/classify_columns.py` module docstring — stale column count.** Said vintage metadata
was found "for 36 of them"; the live `all_vintage_columns()` returns 37 (the `epht_metric` addition
documented in `docs/data_vintage_confirmation.md`'s Step 5 correction note — see item 5 below,
already reconciled in the code, just not in this one docstring sentence). No code path used the
hardcoded number; purely documentation drift. **Fixed** — updated to 37.

**5. `scripts/check_nchs_reclassification.py`'s CDC crosswalk fetch — no custom User-Agent header
(defensive hardening, not a confirmed live failure).** `load_nchs_crosswalk` called `pd.read_csv(
source)` with no header override, unlike the established, already-*confirmed*-necessary fix pattern
this exact project already uses in `src/io.py`'s `load_sample_submission` (a real, previously-hit
`HTTP 403: Forbidden` from a different bucket's front end rejecting pandas' default plain-urllib
User-Agent — Section 4.13/`_SAMPLE_SUBMISSION_USER_AGENT`). This could not be independently
confirmed as live-broken from this environment (network access to cdc.gov was unavailable, exactly
as `load_nchs_crosswalk`'s own docstring already flags as an unverified assumption), so it is
reported and fixed as a preemptive, low-cost defensive measure — not a confirmed bug — given this
project's own demonstrated history of hitting this precise failure mode once already. **Fixed** by
adding `_NCHS_CROSSWALK_USER_AGENT` and applying it via `storage_options` only when `source` is an
actual http(s) URL (mirroring `load_sample_submission`'s exact guard, since `storage_options` for a
local path raises `ValueError` under this project's pinned pandas — confirmed directly, and why the
guard is conditional). Two new tests added to `tests/test_check_nchs_reclassification.py`: one
confirms the header is sent for a URL source (via a monkeypatched `pd.read_csv`), one confirms no
`storage_options` is passed for a local fixture path (so every existing local-path test in that file
keeps working).

**6. `docs/domain_vintage_raw_values.csv` staleness — not fixed here at review time, tracked as
open, subsequently closed on 2026-09-07.** This CSV had 36 rows at review time; the current
`VINTAGE_COLUMNS_BY_SOURCE_TABLE` in `scripts/confirm_domain_vintages.py` lists 37 columns for
`national-epht-heat-tract-table` (including `epht_metric`, added after this CSV was last generated
— see item 4 above and `docs/data_vintage_confirmation.md`'s own correction note, which already
documented this exact gap and stated a re-run would include it automatically). Closing this required
a live re-run of `scripts/confirm_domain_vintages.py` against the real bucket, which needed to
happen on the machine with bucket access, not from this review. **Closed**: Henry ran
`python -m scripts.confirm_domain_vintages` on 2026-09-07, ahead of Stage 5. Execution was clean —
85,396 rows / 232 columns loaded (matching Step 1 exactly), 37 rows written as expected, zero
errors or unexpected warnings. All 36 previously-confirmed values reproduced bit-for-bit
identically to the 2026-09-05 run (a real, independent two-day consistency check on the live
bucket, with zero drift found), and the one new value, `epht_metric='daily maximum heat index'`
(constant, 0% null), was folded into `docs/data_vintage_confirmation.md`'s EPHT row — combined with
the already-confirmed `epht_threshold='95th percentile'`, it exactly matches CDC's own documented
Extreme Heat Days measure definition. Full re-run details and the updated status:
`docs/data_vintage_confirmation.md`'s "Live run results (2026-09-07 re-run)" section. See Section 7
below — this item is removed from the open-items list accordingly.

Suite counts after this review pass: `tests/test_io.py` gained 3 tests, `tests/test_build_data_
dictionary.py` gained 3, `tests/test_tag_candidate_hypotheses.py` gained 1,
`tests/test_check_nchs_reclassification.py` gained 2 — full project suite went from
**461 passed, 2 skipped** to **469 passed, 2 skipped** (same two pre-existing, environment-only
DuckDB skips; zero regressions). Every one of the six findings above was reproduced against the real
code before being called confirmed; every fix's regression test was confirmed load-bearing by
reverting the fix, confirming the new test fails, then restoring the fix and re-confirming the full
suite passes. All touched files re-scanned for third-party/AI-tool attribution language after these
edits — zero matches.

Everything else reviewed across every Stage 3 script, `src/` module, test file, and the audit
notebook — Steps 1-4, most of 5-6, all of 7, the CBP/foundational loaders, and the notebook's own
markdown-vs-CSV cross-checks — held up under the same reproduce-before-trusting scrutiny: no further
confirmed defects found.

## 4.21 Stage 5 Step 3 — real-data verification of TIGER `MTFCC` and Overture road `class` filters (R-006 close-out)

`notebooks/01_eda.ipynb` Section 7, executed live end-to-end against all four regions, closes
`docs/risk_register.md` R-006 ("Unfiltered road classes") with direct evidence rather than
assumption.

**TIGER side.** The real `census-tiger-roads` package contains only 4 distinct `MTFCC` codes across
all four regions — `S1400` (Local Neighborhood Road/Rural Road/City Street, 96.91%-98.87% of every
region's rows), `S1200` (Secondary Road), `S1630` (Ramp), `S1100` (Primary Road) — not the full
~14-code national TIGER/Line road catalog. None of the other ten documented MTFCC road codes (e.g.
`S1710` Walkway, `S1730` Alley, `S1820` Bike Path) appear anywhere in this data. Zero lexical
near-misses against `MTFCC in (S1100, S1200)` in any region. The documented filter's real coverage:
`maricopa-az` 0.35%, `northern-ca` 0.63%, `south-central-tx` 1.16%, `eastern-ok` 1.62% of each
region's real TIGER road rows.

**Overture side.** `subtype` is confirmed 100% `"road"` in every region (494,492 / 191,836 / 520,550
/ 1,937,009 rows for `maricopa-az` / `northern-ca` / `eastern-ok` / `south-central-tx` — zero
non-road rows anywhere), so the documented filter's `subtype == "road"` scoping, while kept
defensively, filters nothing away in practice today. `overture-roads`, as this project actually
receives it, is itself already a curated 7-class subset — `residential`, `tertiary`, `unclassified`,
`secondary`, `primary`, `trunk`, `motorway` — of Overture's real, wider class taxonomy; no other real
column beyond these three (of the layer's 22 real columns total — `id`, `names`, `subclass`,
`subclass_rules`, `connectors`, `road_surface`, `road_flags`, `rail_flags`, `width_rules`,
`level_rules`, `access_restrictions`, `speed_limits`, `prohibited_transitions`, `routes`,
`destinations`, `sources`, `version`, `theme`, `type`, plus `subtype`/`class`/`geometry` — has ever
been inspected by this project) has been used here. Zero lexical near-misses against `class in
(motorway, trunk, primary, secondary)` within this 7-class package. The documented filter's real
coverage: `eastern-ok` 11.42%, `maricopa-az` 11.63%, `northern-ca` 13.59%, `south-central-tx` 18.27%
of each region's `subtype == "road"` rows.

**The `overture-roads-unfiltered` comparison — the specific near-miss hypothesis, resolved.**
`LAYER_OVERTURE_ROADS_UNFILTERED` (`overture-roads-unfiltered`) had existed in `src/config.py` since
Stage 2 but was never discussed in this manifest or schema-inspected until now. It carries 17
distinct real `class` values per region (raw row counts before any filtering: `maricopa-az`
1,170,165; `northern-ca` 479,596; `eastern-ok` 1,037,555; `south-central-tx` 4,122,701 — roughly
40-50% more rows than the already-filtered `overture-roads` keeps in every region). The 10 classes
present in the unfiltered layer but absent from `overture-roads` are **identical across all four
regions**: `bridleway`, `cycleway`, `footway`, `living_street`, `path`, `pedestrian`, `service`,
`steps`, `track`, `unknown` — every one non-vehicular, informal/unpaved, a catch-all, or
driveway/parking-lot-scale access, and none of them a `*_link` ramp/connector variant. The specific
hypothesis this check was built to test — that `motorway_link`/`trunk_link`/`primary_link`/
`secondary_link` values might be present and require a deliberate include/exclude decision for
`transport_gap` — is answered directly: those values do not exist anywhere in this project's real
Overture road data, in any region. `only_in_filtered` is empty in every region too, confirming
`overture-roads` is a clean, well-formed subset of the unfiltered layer rather than a separately
relabeled product.

**Conclusion: both documented filters are correct exactly as written. No change to `src/gaps.py` is
needed.**

**Two findings beyond R-006's original scope, carried forward rather than acted on here:**
1. Both reference layers this challenge ships are already curated subsets of their full raw products
   (TIGER: 4 of ~14 possible MTFCC road codes; Overture: 7 of 17 real class values), applied
   identically across all four regions — not raw, unfiltered exports, and never stated as such
   anywhere in this project's documentation before now.
2. The two filters' real coverage percentages are asymmetric and region-varying — TIGER 0.35%-1.62%
   vs. Overture 11.42%-18.27%, a ratio of roughly 7x (`eastern-ok`) to 33x (`maricopa-az`) depending
   on region, not a fixed conversion factor. This is a second, independent piece of real evidence for
   the classification-scheme-driven cross-region incomparability Section 4.6 already documents from
   the challenge's own materials (the 0.71-1.59 `transport_gap` ratio range) — worth Stage 7
   accounting for deliberately (e.g. normalizing each side by its own network total) rather than
   treating a raw filtered-count ratio as a direct physical-coverage comparison. A smaller,
   non-blocking note for a Stage 9 reachability-style candidate: `service` roads (excluded from
   `overture-roads`) can include short facility-access roads, not only driveways/parking lots.

This section's build also surfaced and fixed a genuine bug during the same real run: an
`overture-roads-unfiltered` load originally implemented as a full geometry-bearing read (mirroring
Section 3's ACS-housing loader) froze Henry's machine partway through `south-central-tx` — the
largest region by tract count (6,003, 3.6x the next-largest) — requiring a hard reboot. Root cause:
this check never needs road geometry, only the `class` column, and geometry (WKB) payloads are
normally the majority of a road-network parquet's bytes. Fixed by column-projecting to `class` only
via a schema-checked `pyarrow.parquet` read and processing one region at a time, discarding each
region's table before loading the next — confirmed working on the real re-run (`south-central-tx`
scanned cleanly at 4,122,701 rows). A second, independent bug was found the same way immediately
after: the comparison cell's result (`class_set_comparison`) was a bare expression nested inside an
`if` block, which Jupyter/IPython does not auto-display (only a cell's top-level trailing statement
is auto-displayed) — the dict was computed correctly but silently never shown or saved. Fixed with an
explicit `print()` call. Both fixes are a real, worked example of this project's
build-then-run-then-interpret-then-close discipline catching genuine defects that a "looks like it
ran fine" pass would have missed.

## 4.22 Stage 5 Steps 4-5 — transport-only-undefined self-check and transport-gap ratio sanity bound

`notebooks/01_eda.ipynb` Sections 8-9, executed live end-to-end against all four regions, close
both of `PROJECT_BLUEPRINT.md`'s named Stage 5 exit criteria.

**Step 4 result, with a genuine root-cause correction along the way.** The first implementation
used `gpd.sjoin(..., predicate="intersects")` as a bare per-tract existence test against TIGER
named-highway segments (`MTFCC in (S1100, S1200)`) and computed 251/218/869/1,704
transport-only-undefined tracts — an exact 2-tract undercount against the published `eastern-ok`
figure (253) only; the other three regions matched immediately. Diagnosis (clipping the matched
roads to each "defined" tract via `gpd.overlay` and measuring real geodesic length with
`geodesic_length_m`) found the precise cause: two `eastern-ok` tracts have a named-highway segment
that touches the tract boundary at a single vertex only — topologically `True` under
`intersects()`, but zero real road length once clipped (`gpd.overlay`'s `keep_geom_type=True`
correctly drops the resulting Point geometry, which is expected behavior here, not a bug to
suppress). Switching the definedness test from bare topological intersection to **clipped length
> 0** reproduces all four published counts **exactly**:

| region | computed (clipped-length) | published | computed % |
|---|---|---|---|
| maricopa-az | 869 | 869 | 54.55% |
| northern-ca | 218 | 218 | 36.89% |
| eastern-ok | 253 | 253 | 21.22% |
| south-central-tx | 1,704 | 1,704 | 28.39% |

**This is a load-bearing requirement for Stage 7's `gaps.py`, not merely an EDA-stage curiosity.**
The real `transport_defined` flag in the pipeline must use clipped road length inside the tract
boundary, exactly as this section now does — a bare spatial-join existence predicate silently
disagrees with the challenge's own published ground truth on this specific boundary-touching edge
case, and Section 4.24 (Step 8) confirms the same phenomenon recurs in every region, not only
`eastern-ok` (undercounts of 4, 4, 2, and 17 tracts across `maricopa-az`/`northern-ca`/
`eastern-ok`/`south-central-tx` respectively, under a non-clipped raw-length method).

**Step 5 result**: the `overture_over_tiger` named-highway length ratio falls inside the documented
`[0.71, 1.59]` band in all four regions — `maricopa-az` 1.296, `northern-ca` 1.173, `eastern-ok`
0.719, `south-central-tx` 1.542. See Section 4.6 for the full interpretation of `eastern-ok`'s
near-floor result and its cross-corroboration with two other, independent findings in this
document.

**Both named Stage 5 exit criteria are met, in writing, as of this section.**

## 4.23 Stage 5 Step 6 — tract-count and cross-region GEOID-uniqueness regression tests

`notebooks/01_eda.ipynb` Section 10 reproduces `reconcile_scored_tracts()` (defined in
`notebooks/00_data_audit.ipynb` cell 12) verbatim against its own 3-fixture self-test (passes),
then re-runs it against the real per-region tract packages:

| region | strata tracts | scored tracts | extra in strata | missing from strata |
|---|---|---|---|---|
| maricopa-az | 1,593 | 1,593 | 0 | 0 |
| northern-ca | 591 | 591 | 0 | 0 |
| eastern-ok | 1,192 | 1,192 | 0 | 0 |
| south-central-tx | 6,010 | 6,003 | 7 | 0 |

Three regions reconcile exactly; `south-central-tx`'s 7-tract gap is exactly the documented `99xx`
water-tract exclusion (Section 4.8), confirmed again independently here, and zero tracts are
missing from any region's strata package (no silent data loss anywhere).

Cross-region GEOID uniqueness was checked twice: once against the scored lists (9,379 GEOIDs
across all four regions, zero collisions — the guideline's minimum spec), and once, as an added
check beyond that minimum, against the full raw tract-package lists (9,386 GEOIDs — 9,379 plus the
same 7 `south-central-tx` water tracts — zero collisions). No tract is double-counted across
regions at any boundary, including the Maricopa/New Mexico state line.

## 4.24 Stage 5 Steps 7-8 — CBP column equality and local distribution sanity checks

**Step 7** (`notebooks/01_eda.ipynb` Section 11): `cbp_estab == cbp_estab_bus` holds in every one
of the 9,386 real CBP rows across all four regions, using a null-safe equality check (both
columns are declared `nullable=True` in `src/schemas.py`'s `CENSUS_CBP_SCHEMA`) that also
confirmed zero rows where both columns are simultaneously null in any region. `cbp_estab` is
confirmed a pure restatement of `cbp_estab_bus` project-wide, with real data behind the confirmation
rather than the schema's declared intent alone. `CBP_ESTAB_COLUMN_DEFAULT = "cbp_estab_bus"`
remains the documented default weighting for Stage 7's POI/establishments component; `src/gaps.py`
can read either column interchangeably.

**Step 8** (`notebooks/01_eda.ipynb` Section 12): per-tract TIGER and Overture named-highway length
distributions are heavily right-skewed in every region (a large mode near 0 km, a long tail to
several hundred — over 1,000 in `eastern-ok`/`south-central-tx` — km per tract for the largest
rural tracts), the expected shape given each region's urban-to-rural span, with no all-zero or
single-spike degenerate pathology in either source in any region.

This section's raw (unclipped, full-segment-length) touching-road count also independently
corroborates Section 4.22's Step 4 root-cause finding, across all four regions, not just
`eastern-ok`:

| region | zero-length tracts (raw, unclipped) | Step 4 clipped-length count |
|---|---|---|
| maricopa-az | 865 | 869 |
| northern-ca | 214 | 218 |
| eastern-ok | 251 | 253 |
| south-central-tx | 1,687 | 1,704 |

Every region undercounts under the raw method by exactly the number of boundary-vertex-touching
slivers present there (4, 4, 2, 17 respectively) — strong, independent confirmation that the
point-touch edge case is a systematic, project-wide phenomenon (worst, both in absolute and
proportional terms, in `south-central-tx`), not an `eastern-ok`-specific anomaly.

## 4.25 Stage 5 Step 9 — face-validity spot map (Maricopa)

`notebooks/01_eda.ipynb` Section 13 computes Maricopa's named-highway road density
(km/km² per tract, percentile-clipped at 2nd/98th to avoid outlier tracts dominating the color
scale, with an explicit zero-area guard). Distribution: mean 2.93, median 1.94, 98th percentile
12.05 km/km², max 126.07 km/km² (1,593 tracts). The resulting choropleth shows a clean, spatially
coherent bright cluster over the Phoenix metro core against a uniformly dark rural/desert
periphery — the expected urban/rural contrast, no isolated single-tract outlier dominating the
map, qualitative confirmation that the per-tract length aggregation shared across Sections 4.22
and 4.24 is spatially sound.

## 4.26 Stage 5 Step 10 — water-dominated and boundary-edge tract identification; `national-census-tracts` schema resolved

This closes the open item Section 4.17/6 flagged: whether `AWATER`/`INTPTLAT`/`INTPTLON` are
sourceable from `<region>-census-tracts` (they are not, per Section 6's real-run finding) or from
`national-census-tracts` instead. `notebooks/01_eda.ipynb` Section 14 directly inspects
`national-census-tracts` (85,396 rows, nationwide) for the first time: it carries `AWATER` but
**not** `INTPTLAT`/`INTPTLON`. The section's branch-detection logic (checking the real column set
rather than assuming a branch) correctly selected the real `AWATER`-based national join for water
fraction, and fell back to a geometric-centroid computation (via `to_equal_area`/`EQUAL_AREA_CRS`
reprojection, per this project's standing CRS discipline, then reprojected back to `OGC:CRS84`) for
point resolution — explicitly flagged in the notebook as lower-fidelity, not silently presented as
authoritative.

**Water-dominated tracts (`water_fraction > 0.5`), by region:**

| region | water-dominated tracts |
|---|---|
| maricopa-az | 0 |
| northern-ca | 2 |
| eastern-ok | 1 |
| south-central-tx | 47 |

The `south-central-tx` known-water-tract list was derived from the data itself
(`sctx_all_tract_geoids - sctx_scored_geoids`, not hardcoded) and matched the documented 7 tracts
exactly; every one shows `water_fraction = 1.0`, `is_water_dominated = True` under this section's
independent `AWATER`-based method — a clean 7-for-7 agreement between the challenge's own exclusion
list and this project's from-scratch computation, real evidence the `AWATER` join and
water-fraction logic are correct.

**A finding to carry into Stage 7/8, not just a check that passed.** Unlike `south-central-tx`,
`eastern-ok`'s 1 and `northern-ca`'s 2 water-dominated tracts remain in the official *scored* set.
A tract that is more than half water by area has structurally little land for buildings, POIs, or
roads to occupy, which can produce unusually extreme or unstable building/POI coverage-gap ratios
for reasons that are about tract geography, not mapping effort or equity. The named GEOID lists are
available in `water_dominated["eastern-ok"]`/`water_dominated["northern-ca"]` (in-notebook, not yet
persisted to a standalone file) and should be carried forward as a named, controllable confound:
Stage 7's pipeline should be able to flag these tracts, and Stage 8/9's Bias Discovery analysis
should check any SVI- or tribal-land-correlated coverage-gap finding against water-dominance status
before treating it as a pure equity signal.

## 4.27 Stage 5 Step 11 — component correlation structure: deferred to Stage 7

`notebooks/01_eda.ipynb` Section 15 ran the cheap Parquet-metadata row-count check this step is
explicitly permitted to gate on (`CHEAP_ROW_THRESHOLD = 2,000,000`, checked via
`pq.ParquetFile(path, filesystem=...).metadata.num_rows`, no data downloaded) before attempting any
real join. Maricopa's `overture-buildings` layer alone is 2,908,224 rows — above threshold — so
this step correctly deferred to Stage 7 rather than forcing a throwaway building/POI correlation
computation through an EDA notebook. No correlation figure was produced, and per the Step 0
resolution documented in `claude/stage5-eda-implementation-guideline.md`, none should have been —
this is a deliberate, explicit deferral, not a skipped step.

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

- ~~Exact schema of `<region>-census-acs-housing.parquet`~~ — **closed 2026-09-07, see
  `notebooks/01_eda.ipynb` Section 3 (Stage 5 Step 2), executed live end-to-end.** Real, confirmed
  schema: `GEOID` (string), `STATEFP`, `COUNTYFP`, `TRACTCE`, `housing_units` (`int64`), `geometry`
  — identical across all four regions, no `bbox` column. Geometry-bearing (not one of the flat
  tables), CRS confirmed `OGC:CRS84`. Row counts match `census-tracts`/`REGION_TRACT_COUNTS`
  exactly in every region (1,593 / 591 / 1,192 / 6,010) — exactly one row per tract, no coverage
  gap, no extra or missing tracts. Null profile is 0.0% on every column in every region — the
  cleanest layer this project has loaded to date, well below TIGER's 36-49% `FULLNAME`/`RTTYP`
  nulls and Overture buildings' 62-94% `subtype`/`class` nulls. All four regions loaded without
  error on the real run — the per-region failure-tolerance this section's loader was built with
  (since this layer, unlike every other layer this project reads, was never part of the Stage 2
  44-combination audit) never had to activate. Carried forward to Stage 7's R-003
  (`03_building_vs_housing_analysis.ipynb`): the housing count lives in one plain `int64` column,
  `housing_units`, not a multi-column occupied/vacant/owner/renter breakdown.
- ~~Whether `cbp_estab` is exactly equal to `cbp_estab_bus` in every row, or differs in edge
  cases~~ — **closed 2026-09-07, see Section 4.24 and `notebooks/01_eda.ipynb` Section 11.**
  Confirmed equal in all 9,386 real CBP rows across all four regions, null-safely, with zero
  both-null rows found anywhere. `cbp_estab_bus` remains the documented default.
- ~~`docs/risk_register.md` R-006 (unfiltered/near-miss road classes) and `overture-roads-unfiltered`
  never discussed or schema-inspected~~ — **closed 2026-09-07, see Section 4.21 and
  `notebooks/01_eda.ipynb` Section 7, executed live end-to-end across all four regions.** Both
  documented filters (`MTFCC in (S1100, S1200)` for TIGER, `subtype == "road"` and `class in
  (motorway, trunk, primary, secondary)` for Overture) confirmed correct with zero lexical
  near-misses; the specific `*_link` ramp/connector hypothesis does not apply — those values do not
  exist in this project's real Overture road data. No change to `src/gaps.py` needed.
- **New, 2026-09-07 — Section 4.17's `AWATER`/`INTPTLAT`/`INTPTLON` sourcing plan does not hold.**
  Section 4.17 states these three columns can be sourced from `<region>-census-tracts` for Stage
  6+'s Tribal Sub-type + Edge Effect and Dispatch-Blind Reachability candidates, "confirmed present
  in `NATIONAL_STRATA_SOURCE_TABLES`'s regional counterpart" — that was an inference by analogy
  from the national table, never a direct check of the regional file. `notebooks/01_eda.ipynb`
  Section 1 (Stage 5 Step 2) now directly inspects `<region>-census-tracts`'s real schema for the
  first time: `GEOID`, `STATEFP`, `COUNTYFP`, `TRACTCE`, `NAMELSAD`, `ALAND`, `pop_total`,
  `pop_urban`, `pop_rural`, `pct_urban`, `ur_class`, `frac_inside_aoi`, `geometry` — identical
  across all four regions, confirmed on a real, executed run. None of `AWATER`, `INTPTLAT`,
  `INTPTLON` are present. **Before Stage 5 Step 10 (water-dominated tract identification) begins,
  `national-census-tracts.parquet`'s own real columns need to be directly inspected** (Section
  4.16 only asserts it is "geometry-only," never lists its columns) — either it carries these three
  columns and can be joined onto each region's tract list by `GEOID`, or a different approach
  (e.g. deriving a water estimate from the tract polygon geometry itself, if this package's
  boundaries are full TIGER/Line rather than a land-only cartographic simplification — Section 1.1
  of the same notebook found zero `MultiPolygon` tracts across all four regions, one small piece of
  evidence worth weighing when that's decided) is needed instead. Not resolved here — flagged for
  Step 10 to resolve with direct evidence, not assumed forward a second time.
  A smaller, non-blocking finding from the same inspection: `pop_total`/`pop_urban`/`pop_rural`/
  `pct_urban`/`ur_class` (a direct rurality signal, already classified `role=population` in the
  232-column national schema) and `NAMELSAD` (human-readable tract names) are both confirmed
  present on this table too — useful for Step 9's face-validity map, not acted on further here.
  **Resolved 2026-09-07, see Section 4.26 and `notebooks/01_eda.ipynb` Section 14.**
  `national-census-tracts` carries `AWATER` but not `INTPTLAT`/`INTPTLON` — confirming this
  flag's prediction exactly. Water dominance now computed from the real national `AWATER` join
  (Branch A); point resolution falls back to a geometric centroid via equal-area reprojection
  (Branch B), explicitly flagged in the notebook as lower-fidelity rather than presented as
  authoritative.
- ~~`docs/domain_vintage_raw_values.csv` was stale by one column~~ — **closed 2026-09-07, see
  Section 4.20 item 6 and `docs/data_vintage_confirmation.md`'s "Live run results (2026-09-07
  re-run)" section.** Henry re-ran `scripts/confirm_domain_vintages.py` against the live bucket:
  37 rows now written (was 36), `epht_metric='daily maximum heat index'` confirmed and folded in,
  every other previously-confirmed value reproduced identically two days apart with zero drift.
- ~~The exact structure of Overture's `sources` field~~ — **closed, see Section 4.5.** Confirmed
  directly against the live bucket for all four regions × `overture-buildings`/`overture-roads`:
  identical 10-field struct signature everywhere, zero null rows, real per-region/layer dataset
  value distributions recorded.
- ~~Full schema/null/geometry-validity inspection across all four regions' `reference/` and
  `strata/` folders~~ — **closed, see Section 4.8.** `scripts/audit/audit_bucket.py` ran against all
  44 region/layer combinations; 44/44 loaded and validated cleanly on the final run, three real
  schema mismatches were found and fixed, and the full findings (row-count reconciliation, geometry
  integrity, null-rate gradients) are recorded in Section 4.8. Note: `<region>-census-acs-housing`
  is not one of the four reference layers this project scores against, so it was not part of this
  audit and remains open per the bullet above.
