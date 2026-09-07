# Data vintage confirmation

Stage 3 Step 4 of the data-audit plan (see `docs/data_manifest.md` Section 4). Steps 1-3 established
what columns exist, what domain each belongs to, and how often each is null. This step asks a
different question: is the specific vintage of every underlying public dataset actually the current,
authoritative one, and are the several datasets joined into one table internally consistent with
each other? That can only be answered by comparing this project's real data against each source
agency's own current documentation.

This document exists for two reasons at once: it is due diligence the Bias Score's own equity claims
depend on (a coverage-gap finding is only as credible as the data vintage it is measured against),
and it satisfies the challenge's own rule that any data or fact used in the Best Bias Discovery
writeup beyond the four provided packages be "documented there with URL and retrieval date."

**Method.** For every column across the 19 source tables that carries genuine vintage, edition,
version, or coverage-window metadata, two independent things were checked side by side: (1) the
column's actual value(s) in the live bucket (`scripts/confirm_domain_vintages.py`, run against real
data — see the run instructions and results below), and (2) what the source agency's own site
currently documents as that dataset's authoritative vintage, retrieved on 2026-09-05. A column is
"confirmed" only when both sides were checked and agree; "ambiguous" means external research found
more than one plausible match and the live value is needed to pick between them; "unresolved" means
external research alone could not pin down a single authoritative coverage window from a top-level
agency page, and would need a narrower, dataset-specific technical page to close.

## Findings, by domain

### Wildfire

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-carbonplan-tract-table` | `carbonplan_version='v1.1.0'` (confirmed live value, 2026-09-05 run) | CarbonPlan Open Climate Risk wildfire data | Current public release is tagged v1.1.0 on CarbonPlan's own release history | **Confirmed match** | [CarbonPlan OCR docs](https://docs.carbonplan.org/ocr/en/latest/how-to/work-with-data.html), [releases](https://github.com/carbonplan/ocr/releases) |
| `national-fpa-fod-tract-table` | `fod_edition`, `fod_year_min=1992`, `fod_year_max=2020` | USDA/USFS Fire Program Analysis Fire-Occurrence Database (FPA-FOD) | 6th Edition (`RDS-2013-0009.6`, file `FPA_FOD_20221014`) is documented as covering exactly 1992-2020 | **Confirmed match** | [USFS RDS-2013-0009.6](https://www.fs.usda.gov/rds/archive/catalog/RDS-2013-0009.6) |
| `national-mtbs-tract-table` | `mtbs_year_min=1984`, `mtbs_year_max=2023`, `mtbs_size_threshold='about 1000 acres in the West, 500 in the East'` (confirmed live value, 2026-09-05 run) | Monitoring Trends in Burn Severity (MTBS) | Program coverage 1984-present, continuously updated; current public release is version 12.0 (April 2025), newer than the file's 2023 upper bound. The live threshold string matches MTBS's own long-documented size-threshold convention exactly | **Confirmed coverage window and threshold definition; file is one release behind current** — expected for any snapshot, not an error, but worth stating explicitly rather than implying the file is current | [USGS MTBS ver. 12.0](https://www.usgs.gov/data/monitoring-trends-burn-severity-ver-120-april-2025), [mtbs.gov](https://www.mtbs.gov/) |
| `national-nifc-tract-table` | `nifc_year_min=1984`, `nifc_year_max=2025` | NIFC Interagency Fire Perimeter History — All Years View | Continuously-updated ArcGIS feature layer with historical coverage from 1984 onward; no fixed "edition," so a 2025 upper bound is consistent with a recent pull | **Confirmed match** | [NIFC feature layer](https://data-nifc.opendata.arcgis.com/datasets/nifc::interagencyfireperimeterhistory-all-years-view/about) |
| `national-usfs-wildfire-tract-table` | `usfs_edition='WRC v2 (RDS-2020-0016-2 / RDS-2020-0060-2 / RDS-2024-0030)'`, `usfs_extent='CONUS'` (confirmed live values, 2026-09-05 run) | USFS Wildfire Risk to Communities | The live value confirms this is the **2nd edition** (`RDS-2020-0060-2`), not the 1st (`RDS-2020-0060`) | **Confirmed match — 2nd edition, CONUS extent** | [2nd edition metadata](https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/_metadata_RDS-2020-0060-2.html), [Ag Data Commons listing](https://agdatacommons.nal.usda.gov/articles/dataset/Wildfire_Risk_to_Communities_Spatial_datasets_of_wildfire_risk_for_populated_areas_in_the_United_States/27009298) |
| `national-usgs-combined-tract-table` | `usgs_record_start=1835`, `usgs_record_end=2020` | USGS "Combined wildland fire datasets for the United States and certain territories, 1800s-Present" | Published 2022-02-07 (DOI `10.5066/P9ZXGFY3`), distributed as versioned fiscal-year packages; an FY21-vintage pull would show records through roughly 2020 | **Confirmed match** | [USGS combined wildland fire dataset](https://www.usgs.gov/data/combined-wildland-fire-datasets-united-states-and-certain-territories-1800s-present), [ScienceBase item](https://www.sciencebase.gov/catalog/item/61aa537dd34eb622f699df81) |

### Heat

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-cdc-wonder-tract-table` | `cdcw_grain='county'` (confirmed live value, 2026-09-05 run), `cdcw_window_start=1981`, `cdcw_window_end=2010` | Referenced via CDC WONDER, but the 1981-2010 window itself matches NOAA NCEI's "U.S. Climate Normals (1981-2010)" product suite | **Confirmed the window's origin, with a caveat**: this is a NOAA NCEI baseline (dataset family `C00820`/`C00822`), not a CDC-native vintage — CDC WONDER's heat tooling appears to reference these NOAA Normals as its baseline period rather than publishing its own. **New finding from the live `cdcw_grain` value**: this table's real spatial resolution is **county**, not tract — every tract in the same county carries the identical `hwd_*` heat-trend values, disaggregated down from one county-wide figure. See the new section below ("Resolution mismatch...") for why this is worth checking as a possible rurality-correlated bias, not just a vintage note | [NOAA NCEI 1981-2010 Normals metadata](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC00822) |
| `national-epht-heat-tract-table` | `epht_threshold='95th percentile'` (confirmed live value, 2026-09-05 run), `epht_metric='daily maximum heat index'` (confirmed live value, 2026-09-07 re-run), `epht_year_min=2015`, `epht_year_max=2023` | CDC/EPHT (Environmental Public Health Tracking) heat measures | The two live values together exactly match CDC's own published definition of its "Extreme Heat Days" tracking measure — a day on which the **daily maximum heat index** exceeds a location's own **95th-percentile** threshold — rather than a fixed absolute temperature or a different heat metric (e.g. mean temperature, wet-bulb globe temperature). This is a real, specific methodological match, not just "a percentile-based threshold exists somewhere." Top-level EPHT/Heat & Health Tracker pages still do not state one single fixed 2015-2023 coverage range | **Threshold and metric definitions both confirmed and mutually consistent with CDC's documented Extreme Heat Days measure; exact coverage-window provenance still unresolved** — needs the EPHT Data Explorer's own per-measure metadata, not just agency landing pages | [CDC Tracking Heat Events](https://www.cdc.gov/environmental-health-tracking/php/data-research/tracking-heat-events.html), [EPHT Data Explorer](https://ephtracking.cdc.gov/DataExplorer/) |

**Correction found while building Stage 3 Step 5**: `epht_metric` — a genuine constant string
methodology-metadata column in `national-epht-heat-tract-table`, structurally identical to
`epht_threshold` — was missed by this step's original column list and by its keyword-based
completeness test (the regex never included "metric"). It was caught by Step 5's own cross-check,
which compares every column's real distinct-value count (from `docs/coverage_null_profile.csv`)
against the vintage list directly, rather than guessing keywords. Fixed: `epht_metric` has been
added to `VINTAGE_COLUMNS_BY_SOURCE_TABLE`, and a second, stronger completeness test
(`test_every_nationally_constant_column_is_either_vintage_or_a_documented_exception`) has been added
to `tests/test_confirm_domain_vintages.py` — it checks every column that takes only one distinct
value across all 85,396 tracts nationally, which cannot be fooled by an incomplete keyword list the
way the first test could. **`epht_metric`'s actual live value was pulled in the 2026-09-07 re-run
(see "Live run results" below): `'daily maximum heat index'`, constant across all 85,396 tracts,
0% null.** Combined with `epht_threshold='95th percentile'`, this confirms the two columns together
describe CDC's documented Extreme Heat Days measure exactly (see the table row above) — this gap is
now fully closed. `tests/test_confirm_domain_vintages.py` now has 18 tests (was 17); full project
suite: 278 passed, 2 skipped, zero third-party mentions (figures as of the original Stage 3 Step 5
pass — see the live-run sections below for the subsequent re-runs' own suite figures).
| `national-nasa-heat-tract-table` (`gehe_*`) | `gehe_record_start=1983`, `gehe_record_end=2016` | NASA SEDAC/CIESIN "Annual Global High-Resolution Extreme Heat Estimates (GEHE), 1983-2016" | Exact title and year-range match; this exact quote was independently re-fetched and re-confirmed word-for-word during this step's own review pass | **Confirmed match** | [NASA Earthdata GEHE](https://www.earthdata.nasa.gov/data/catalog/sedac-ciesin-sedac-sdei-gehe-1.00), [data.gov GEHE listing](https://data.nasa.gov/dataset/annual-global-high-resolution-extreme-heat-estimates-gehe-1983-2016) |
| `national-nasa-heat-tract-table` (`uhe_*`) | `uhe_city_country` (confirmed live values, 2026-09-05 run): `'United States' (44,028)`, `'Puerto Rico' (409)`, `'Mexico' (205)`, `'Canada' (23)`; `uhe_city_name` top values include New York, Los Angeles, Chicago, Miami, Dallas, Houston, Phoenix, Seattle — and **Tijuana, Mexico** (690 tracts) | Most likely NASA SEDAC/CIESIN "Global High Resolution Daily Extreme Urban Heat Exposure (UHE-Daily), 1983-2016" — the natural city-level sibling product to GEHE from the same source | **Strengthened toward the SEDAC/CIESIN match, though still not fully proven.** The live values include Mexican and Canadian cities (Tijuana, plus 23 Canadian-tract matches) even though every tract being joined is a US Census tract — this is only explainable by a nearest-city assignment from a genuinely global city list (consistent with SEDAC's worldwide UHE-Daily product), since a US-only academic dataset would have no non-US cities to assign at all. This also surfaces a real, separate methodological note worth stating in the writeup: US border tracts near Tijuana/other Mexican or Canadian cities are apparently matched to the nearest urban center regardless of country, not restricted to a US-city list | [data.gov UHE-Daily listing](https://catalog.data.gov/dataset/global-high-resolution-daily-extreme-urban-heat-exposure-uhe-daily-1983-2016) |
| `national-noaa-ghcn-tract-table` | `ghcn_year_min=2015`, `ghcn_year_max=2023` | NOAA GHCN-Daily (Global Historical Climatology Network) | GHCN-Daily itself spans the 1750s-present at the station level; no NOAA-native "2015-2023" derived product was found | **Unresolved as a NOAA-native vintage** — the 2015-2023 window is most likely this project's own upstream pipeline choice (e.g. matching EPHT's window, which uses the identical 2015-2023 range), not a GHCN limitation; needs the upstream pipeline's own documentation, not NOAA's | [NOAA GHCN-Daily](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily) |

### Drought

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-drought-gov-tract-table` | `drought_gov_window_start=2015`, `drought_gov_window_end=2023`, `spi_calibration` (100% null) | drought.gov / NIDIS PMDI and SPI | No single documented "2015-2023" PMDI/SPI coverage window found at the top level; SPI is conventionally computed against a fitted calibration period (often ~30 years), which is consistent with `spi_calibration` simply not being populated in this extract rather than SPI lacking one | **Unresolved** — needs the specific NIDIS/CPC SPI product page | [drought.gov data download](https://www.drought.gov/data-download), [drought.gov SPI](https://www.drought.gov/drought/data/category/spi-standardized-precipitation-index) |
| `national-usdm-drought-tract-table` | `usdm_year_min=2015`, `usdm_year_max=2023` | U.S. Drought Monitor (USDM) | USDM's full historical record begins January 2000; 2015-2023 is a deliberate sub-window of a much longer record, not a USDM data limitation | **Confirmed as an intentional analysis-window subset** | [drought.gov USDM](https://www.drought.gov/data-maps-tools/us-drought-monitor), [historical info](https://www.drought.gov/historical-information) |

### Rurality

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-nchs-tract-table` | `nchs_year=2013` | NCHS Urban-Rural Classification Scheme for Counties | CDC has since published an updated **2023** scheme (2023 OMB metro delineations + 2022 Census population estimates); the 2013 scheme is not current. **Independently re-verified during this step's review** directly against CDC's own page: CDC itself states "there were minimal differences in county assignments between the 2023 and 2013 schemes" — no changed-county count or percentage is given. CDC also publishes a single combined crosswalk file with all four vintages (1990/2006/2013/2023) side by side per county, at `https://www.cdc.gov/nchs/data/data-analysis/NCHSurb-rural-codes.csv` | **Mismatch confirmed, but tempered — see the revised Best Bias Discovery section below; do not present this as "significant bias" without first checking the crosswalk against this project's own four study regions** | [CDC NCHS urban-rural](https://www.cdc.gov/nchs/data-analysis-tools/urban-rural.html), [2023 scheme documentation](https://www.cdc.gov/nchs/data/data-analysis/2023-File-Documentation-final.pdf), [all-vintage county crosswalk CSV](https://www.cdc.gov/nchs/data/data-analysis/NCHSurb-rural-codes.csv) |
| `national-ruca-tract-table` | `ruca_year=2020` | USDA ERS Rural-Urban Commuting Area (RUCA) codes | ERS explicitly documents a 2020-vintage RUCA release built on 2020 Census tract geography | **Confirmed match** | [USDA ERS RUCA](https://www.ers.usda.gov/data-products/rural-urban-commuting-area-codes) |
| `national-rucc-tract-table` | `rucc_year=2023` | USDA ERS Rural-Urban Continuum Codes (RUCC) | "2023 Rural-Urban Continuum Codes" is ERS's current published release | **Confirmed match** | [USDA ERS RUCC chart](https://www.ers.usda.gov/data-products/chart-gallery/chart-detail?chartId=108333), [direct file](https://www.ers.usda.gov/media/5767/2023-rural-urban-continuum-codes.xlsx) |

### Climate Vulnerability Index (CVI)

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-cvi-tract-table` | `cvi_source_vintage=2010` | U.S. Climate Vulnerability Index (Environmental Defense Fund / Texas A&M) | Peer-reviewed and published 2023 (*Environment International*, v.172); the CVI deliberately uses **2010** Census TIGER/Line tract boundaries rather than 2020, because most of its underlying input data (largely 2017-2019) predates the 2020 Census geography update | **Confirmed, with an important clarification** — "2010" is the Census geography vintage the CVI's own methodology deliberately chose, not the CVI's publication year (2023) or its underlying data's collection years (~2017-2019). This is a real point worth stating explicitly in the methodology writeup so it is not misread as "this project used decade-old vulnerability data." | [CVI methodology](https://climatevulnerabilityindex.org/methodology/) |

### Social Vulnerability Index (SVI)

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-svi-tract-table` | `svi_year=2022` | CDC/ATSDR Social Vulnerability Index | "CDC/ATSDR SVI 2022 USA" is the current full release, built on 2018-2022 5-year ACS estimates | **Confirmed match — the most current SVI available** | [SVI 2022 dataset](https://www.arcgis.com/home/item.html?id=f2af3fd35858443293b75d5f73c7d4d3), [SVI fact sheet](https://www.atsdr.cdc.gov/place-health/media/pdfs/2024/07/SVI-Fact-Sheet-H.pdf) |

### Tribal

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-tribal-tract-table` | (no vintage column exists in this table) | Census Bureau AIANNH (American Indian/Alaska Native/Native Hawaiian) area boundaries | TIGER/Line AIANNH shapefiles are published annually; several vintages exist. Since this project's tracts are `tract_vintage=2020`, the AIANNH layer should also be the 2020 vintage for internal consistency | **Ambiguous by design (no in-file vintage marker) — assumed 2020 by consistency with `tract_vintage`, not independently confirmed from the file itself** | [2020 TIGER/Line AIANNH](https://catalog.data.gov/dataset/tiger-line-shapefile-2020-nation-u-s-american-indian-alaska-native-native-hawaiian-aiannh-areas) |

### Geography / population

| Source table | Column(s) | Agency / dataset | Externally confirmed vintage | Status | Source |
|---|---|---|---|---|---|
| `national-census-tract-table` | `tract_vintage=2020` | Census Bureau TIGER/Line Census tract boundaries and population | 2020 TIGER/Line Shapefiles are built on the 2020 Census Redistricting Data (P.L. 94-171) tract boundaries and population base | **Confirmed match** | [2020 TIGER/Line tracts](https://www.census.gov/cgi-bin/geo/shapefiles/index.php?year=2020&layergroup=Census+Tracts), [technical documentation](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2020pl/TGRSHP2020PL_TechDoc.pdf) |

## Best Bias Discovery candidate surfaced by this step (revised after independent re-verification)

**Vintage lag in the rurality classification: `nchs_year=2013` while CDC's current scheme is 2023 —
real, but not yet a demonstrated bias, and CDC's own page pre-empts the naive version of this claim.**

The first draft of this document presented "the NCHS scheme is a decade out of date" on its own as a
strong, self-evidently significant finding. A closer, independent re-read of CDC's own NCHS
urban-rural page during this review's fact-checking pass found a sentence that directly undercuts
that framing: CDC itself states "there were minimal differences in county assignments between the
2023 and 2013 schemes." Presenting the raw vintage gap as a bias finding without acknowledging that
CDC has already characterized the practical difference as minimal would be exactly the kind of
overclaim a Best Bias Discovery judge — who can trivially find the same CDC sentence — would flag
against us, not for us.

The vintage gap is still real and still worth carrying forward, but only as a **testable hypothesis
with a concrete, already-identified path to verify or debunk it**, not as a finding stated outright:
CDC publishes a single combined crosswalk file with all four scheme vintages (1990, 2006, 2013, 2023)
side by side per county (`https://www.cdc.gov/nchs/data/data-analysis/NCHSurb-rural-codes.csv`).
Stage 8/9's hypothesis mining should download that file and check, specifically, whether ANY county
within this project's four study regions (Maricopa AZ; the Northern California fire corridor; Eastern
Oklahoma's tribal statistical areas; South-Central Texas along I-35/I-37) is classified differently
under the 2013 scheme (the one `nchs_year=2013` says this project actually uses) than under the
current 2023 scheme. If zero study-region counties changed, this is not a Best Bias Discovery finding
at all — it should be dropped, not stretched. If one or more DID change, that is a genuine,
quantifiable, county-specific vintage-bias finding worth pursuing, with the exact county and both its
old and new classifications as concrete evidence, which is a far stronger submission than an
unqualified "the scheme is outdated" claim.

**This check is not built yet — it is Stage 8/9 work, deliberately not pulled forward into Step 4.**
Recorded here in full so it does not get lost or forgotten by the time Stage 8/9's hypothesis mining
actually starts:

- **Data needed**: CDC's combined crosswalk CSV,
  `https://www.cdc.gov/nchs/data/data-analysis/NCHSurb-rural-codes.csv`. Its documented column
  layout (per CDC's `2023-File-Documentation-final.pdf`, not independently verified against the raw
  file yet — no network access to cdc.gov was available while researching this) is `STFIPS`,
  `CTYFIPS`, `ST_ABBREV`, `CTYNAME`, `CODE1990`, `CODE2006`, `CODE2013`, `CODE2023`, where codes 1-4
  are metro tiers (1 = large central metro down to 4 = small metro), 5 = micropolitan, 6 =
  noncore/nonmetro.
- **Method**: for each of the four study regions, load its real scored-tract GEOID list the same
  way every other step in this project does (`src.io.load_sample_submission` — never a hardcoded
  county list, per the Section 4.8/4.9 discipline), derive each tract's county FIPS from its own
  GEOID (first 5 digits: 2-digit state + 3-digit county), take the region's distinct county set, and
  join it against the crosswalk on that 5-digit FIPS to compare `CODE2013` against `CODE2023`.
- **The rule that matters most**: if zero counties across all four regions show a different code
  between 2013 and 2023, the NCHS vintage-lag claim above must be **dropped from the Best Bias
  Discovery writeup entirely** — not kept in a softened or hedged form. A null result here is itself
  the answer to the question this check exists to ask; stretching it into "a finding anyway" would
  repeat the exact overclaim this review pass already caught once. If one or more counties DID
  change, that specific county, its old code, and its new code become the actual evidence — a far
  stronger submission than the unqualified "the scheme is outdated" framing this section originally
  had.
- **Where this belongs**: Stage 8/9 (bias-discovery hypothesis mining), not Stage 3. When that stage
  starts, build this as a small script following this project's established testable-core pattern
  (pure county-matching logic tested against fixtures; only the crosswalk download and the real
  sample-submission loads touch the network), run it, and update this section with the actual result.

## New finding from the live run: CDC WONDER heat-trend data is county-level, not tract-level

`cdcw_grain`'s confirmed live value is `'county'`. This table's 15 real heat-trend measurement
columns (`hwd_maxtemp_*`, `hwd_heatindex_*`, `hwd_heatstress_*` — the actual measurements
`cdcw_covered` describes, per Step 3's naming-trap finding) are therefore county-level figures,
disaggregated down so that every tract within the same county carries an identical value. This was
not previously documented anywhere in Steps 1-3, which profiled null rates and distinct-value counts
per column but had no reason to compare values ACROSS tracts within the same county.

This is worth flagging as a possible additional bias angle, with the same discipline just applied to
the NCHS claim above: state it as a hypothesis with a concrete, cheap verification path, not as a
finding. County-level data spread uniformly across tracts means a county with many tracts (typically
a larger, often more urban or more populous county) gets exactly the same effective heat-trend
"resolution" as a county with only one or two tracts (often smaller, more rural) — the per-tract
figure is equally uninformative about within-county variation in both cases, but a large rural county
covering many tracts could still end up systematically smoothing over more real spatial heterogeneity
than a small urban county simply because it has more tracts sharing one number. Before this becomes
anything more than a plausible mechanism, Stage 8/9 should check it directly and cheaply: group the
real tract-level `hwd_*` values by county (a one-line `groupby(["STATEFP","COUNTYFP"])` on the already
-loaded national table) to (a) confirm the within-county-constant pattern actually holds as described,
and (b) check whether tract-count-per-county (a direct rurality proxy already available from
`pop_total`/`ur_class`) correlates with anything meaningful once this resolution artifact is
accounted for, rather than assuming it does.

## Review pass #1, before running against the live bucket

A dedicated review of this document, the external research behind it, `scripts/
confirm_domain_vintages.py`, and `tests/test_confirm_domain_vintages.py` — done independently, not
just re-reading what was already written — checked three things: whether the research citations
actually say what they were reported to say, whether every vintage-relevant column in the real
232-column table was actually captured, and whether the script/tests have any real bugs. Findings:

1. **Three of the highest-stakes citations were independently re-fetched and re-checked word for
   word** (NCHS urban-rural, the CVI methodology's 2010-boundary claim, USDA ERS's RUCA 2020
   availability, and NASA's exact GEHE title/date range) — all matched, except for one important
   omission, item 2 below.
2. **The NCHS "vintage lag" claim was incomplete and, as originally written, overclaimed.** CDC's own
   page states the 2013-to-2023 scheme change produced "minimal differences in county assignments" —
   a sentence the first draft of this document did not surface. Presenting the raw vintage gap alone
   as a Best Bias Discovery finding risked a judge finding that same CDC sentence and discounting the
   whole submission. Fixed: the finding above is now framed as a testable hypothesis with a specific,
   already-identified verification path (CDC's own all-vintage county crosswalk CSV, checked against
   this project's four actual study regions), not an unqualified claim.
3. **A completeness sweep of the real domain map, done as an independent check rather than trusting
   the original by-hand review, found zero missing columns — but this had not been locked in as a
   test.** A keyword sweep (year/vintage/edition/version/window/threshold/calibration/grain/extent/
   record/date/period/epoch/baseline/release) against all 232 real column names found every match was
   already accounted for: either already listed in `VINTAGE_COLUMNS_BY_SOURCE_TABLE`, or one of five
   `cvi_baseline*` columns confirmed (by checking their actual values) to be continuous per-tract CVI
   sub-scores, not vintage metadata. This was true, but only true because someone happened to check
   it by hand — nothing would have caught a future column silently falling through this step. Fixed:
   added `test_no_vintage_relevant_column_is_missing_from_the_module_level_mapping` and
   `test_every_real_source_table_is_either_listed_or_a_documented_exclusion` as permanent regression
   tests, plus `test_all_vintage_columns_has_no_duplicates_in_the_real_module_level_mapping` to lock
   in a previously-unverified docstring claim.
4. **`uhe_city_country` alone cannot actually discriminate between the two candidate "uhe" source
   datasets the way the original research write-up implied.** Since `national-nasa-heat-tract-table`
   is already joined to only US census tracts, both candidate datasets (NASA SEDAC's global UHE-Daily
   product and the alternative academic Global Urban Heat Island dataset) would show a US-dominated
   country list after that join regardless of which one it actually is — the country column mainly
   rules out a non-US-only mismatch, it does not settle the question. Fixed: added `uhe_city_name` to
   the columns the script extracts, so the actual city list (not just country) is available for a
   direct, qualitative comparison against each candidate dataset's own published city list once the
   script is run.

`tests/test_confirm_domain_vintages.py` grew from 14 to 17 tests, all passing, including the three
new completeness/regression tests above (two of them running against the real, committed
`docs/column_domain_map.csv`). Full project suite: 277 passed, 2 skipped (the same sandbox-only
DuckDB extension-download skip as every previous step), zero third-party mentions on a final scan.

## Live run results (2026-09-05)

Henry ran `scripts/confirm_domain_vintages.py` against the live bucket: 85,396 rows, 232 columns
loaded (matching Step 1 exactly), 36 vintage-column rows written to
`docs/domain_vintage_raw_values.csv` (35 originally planned plus `uhe_city_name`, added during review
pass #1). Execution was clean — no warnings, no errors, no unexpected row count. Every value has been
folded into the domain tables above; the six previously ambiguous/unresolved items now stand as:
**resolved and confirmed** — `carbonplan_version` (v1.1.0), `usfs_edition`/`usfs_extent` (2nd
edition, CONUS), `mtbs_size_threshold`, `epht_threshold`; **strengthened but not fully proven** —
the `uhe_*` dataset identity (the Mexico/Canada city evidence favors SEDAC's global UHE-Daily product
over a US-only academic alternative, but this is inference from indirect evidence, not a title match
like GEHE's); **still unresolved, unaffected by this run** — EPHT's exact 2015-2023 coverage-window
provenance and the drought.gov SPI calibration period, both of which need a narrower per-dataset page
neither this run nor the original research pass could reach; **new finding entirely** — `cdcw_grain`
revealed the CDC WONDER table's county-level (not tract-level) resolution, written up as its own
section above.

**Note on scope**: the NCHS reclassification check described above is intentionally NOT built or run
as part of Step 4 — it is recorded as a fully-specified Stage 8/9 action item (data source, exact
column layout, method, and the drop-if-zero rule are all written out above) so it does not get lost,
but the script itself, and confirming or debunking the claim, is deliberately deferred to when Stage
8/9's hypothesis mining actually begins.

## Live run results (2026-09-07 re-run — closes the `epht_metric` gap)

Henry re-ran `python -m scripts.confirm_domain_vintages` against the live bucket, ahead of Stage 5,
to close the one open item flagged during the pre-Stage-4 review pass (`docs/data_manifest.md`
Section 7): `docs/domain_vintage_raw_values.csv` was stale by one column, missing `epht_metric`
(added to `VINTAGE_COLUMNS_BY_SOURCE_TABLE` during the Stage 3 Step 5 correction described above,
but never actually re-pulled live until now).

Execution was clean: 85,396 rows, 232 columns loaded — matching Step 1's expected figure exactly,
identical to the 2026-09-05 run — with no warnings or errors beyond the standard, already-documented
harmless `pandera` `FutureWarning`. **37 vintage-column rows written** (36 from the prior run plus
`epht_metric`), confirming the row count moved from 36 to 37 exactly as the correction note
predicted, with no other row added or dropped.

**Every one of the 36 previously-confirmed values reproduced bit-for-bit identically** to the
2026-09-05 run — same dtype, same 0% (or, for `spi_calibration`, the same already-documented 100%)
null rate, same distinct-value count, same actual value(s) for every column, including the
higher-cardinality `uhe_city_country`/`uhe_city_name` distributions (`'United States'` 44,028,
`'Puerto Rico'` 409, `'Mexico'` 205, `'Canada'` 23; New York/Los Angeles/Chicago/Miami/Dallas/
Houston/... topping `uhe_city_name`, Tijuana still present at 690). This is a meaningful,
independent consistency check in its own right — two live pulls of the same 85,396-row table, two
days apart, agree exactly on every previously-confirmed fact, with zero drift in the underlying
bucket data.

**The one new fact**: `epht_metric='daily maximum heat index'` — constant across all 85,396 tracts
nationally, 0% null, `n_distinct=1`. Folded into the table above: combined with the already-confirmed
`epht_threshold='95th percentile'`, this exactly matches CDC's own documented definition of its
Extreme Heat Days tracking measure (a day whose daily maximum heat index exceeds a location's own
95th-percentile threshold) — a specific, positive methodological confirmation, not just "some
percentile-based threshold exists." This closes the `epht_metric` item in full; the two genuinely
separate items EPHT's coverage-window provenance and the drought.gov SPI calibration period remain
open exactly as before (see below) — this run did not touch either.

## Status and what's still needed

Step 4 itself is complete: every vintage-relevant column across all 19 source tables has been
checked against external documentation and, where ambiguous, against its live value —
**`docs/domain_vintage_raw_values.csv` is now current at 37 rows, with zero known staleness.** What
remains open is genuinely out of this step's scope — `uhe_*`'s exact dataset identity (strengthened,
not proven), EPHT's coverage-window provenance (distinct from `epht_metric`/`epht_threshold`, both
now confirmed), and the drought.gov SPI calibration period would each need a narrower per-dataset
page to fully close, and none of the three blocks anything downstream. The one true open action
item with a required build is the NCHS reclassification check specified above, which belongs to and
will be executed in Stage 8/9, not here.

**Personal follow-up noted 2026-09-07 (no stage assignment, no build required).** Henry intends to
later try to pin down the two still-unresolved provenance items directly against their own
dataset-specific technical pages, rather than the general agency landing pages already checked
here:

- **EPHT coverage-window provenance** — check the EPHT Data Explorer's own per-measure metadata for
  the Extreme Heat Days measure, not just the general Tracking Heat Events / Data Explorer landing
  pages already cited above: [EPHT Data Explorer](https://ephtracking.cdc.gov/DataExplorer/).
- **drought.gov SPI calibration period** — check the specific NIDIS/CPC SPI product page for its
  stated calibration baseline, not just the general drought.gov data-download page already cited
  above: [drought.gov SPI](https://www.drought.gov/drought/data/category/spi-standardized-precipitation-index).

This is a documentation-quality improvement, not a correctness fix — neither item blocks any
downstream stage, and both columns' actual live values are already confirmed and in use. If either
is pinned down, update this file's corresponding table row (Heat section for EPHT, Drought section
for SPI) from its current status to a confirmed match, and update `docs/data_manifest.md`'s vintage-
status table entry for that source table (`confirmed_with_clarification` → `confirmed` for EPHT;
`unresolved` → `confirmed` or `confirmed_with_clarification` for drought.gov) accordingly.

## How to run this (Henry's local environment)

Nothing further to run for Step 4 itself — `scripts/confirm_domain_vintages.py` has already been run
and its results are folded into the tables above. The NCHS reclassification check is Stage 8/9 work
and will get its own run instructions when that stage starts.
