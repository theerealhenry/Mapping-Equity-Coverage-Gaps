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

### 4.7 Confirmed region tract counts

| Region | Scored tracts | Total tract membership |
|---|---|---|
| Maricopa County, AZ | 1,593 (1,592 AZ + 1 NM tract, `35023970000`, Hidalgo County Tract 9700) | 1,593 |
| Northern California | 591 | 591 |
| Eastern Oklahoma | 1,192 | 1,192 |
| South-Central Texas | 6,003 | 6,010 |
| **Total scored** | **9,379** | — |

Published per-region **transport-only-undefined** counts and percentages (self-checked in Stage 5,
before building/POI definedness logic exists), recomputed here directly from the raw counts rather
than trusting the rounded figures alone: eastern-ok 253/1,192 = 21.2%, maricopa-az 869/1,593 =
54.6%, northern-ca 218/591 = 36.9%, south-central-tx 1,704/6,003 = 28.4%. (Maricopa's precise value
is 54.55%, which rounds to 54.6%, not 54.5% — a rounding slip caught and corrected during this
stage's review; the corresponding figure in `PROJECT_BLUEPRINT.md` was fixed to match.)

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
