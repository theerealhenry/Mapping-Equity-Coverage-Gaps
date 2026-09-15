# EDA Findings — Stage 5 (Exploratory Data Analysis, EDA-B)

A durable, human-readable record of everything Steps 2-11 of Stage 5 found, executed live against
all four challenge regions in `notebooks/01_eda.ipynb`. This document mirrors the pattern
`docs/data_manifest.md` established for Stages 1-2 and `docs/DATA_DICTIONARY.md` for Stage 3: the
notebook is the reproducible, executable record; this is the readable one. Every finding below
cross-references its full evidence in `docs/data_manifest.md`, where the underlying numbers and
methodology live in permanent detail — this document's job is to be the one a reviewer opens first,
not to duplicate that detail.

Dated 2026-09-07. Stage owner: Henry Otsyula.

## 1. What Stage 5 set out to do, and its scope boundary

Stage 5's job (`claude/stage5-eda-implementation-guideline.md` Step 0) is **EDA-B, phenomenology**
— what the data actually looks like and how its pieces relate — deliberately scoped to the
self-checks answerable with only road and tract data, so nothing here is blocked on a pipeline that
doesn't exist yet. EDA-A (data integrity) was already Stage 2's job (`notebooks/00_data_audit.ipynb`)
and is not repeated here. This stage does **not** touch `src/gaps.py`, does not compute a real
`coverage_gap_score`, and does not build the Reference Reconstruction Engine — that is Stage 7's job
in full.

## 2. Finding — data loading and schema confirmation (Step 2)

**Checked**: whether `census-tracts`, `census-tiger-roads`, and `census-acs-housing` load cleanly in
all four regions, with the project's two standing guards (CRS `OGC:CRS84`, GEOID-as-string) holding
throughout, and row counts matching `src/config.py`'s published constants exactly.

**Result**: everything proved true on live data. All three layers load cleanly; both guards hold
everywhere checked; row counts match with zero tolerance needed; every tract polygon is a valid,
single-part `Polygon`; the South-Central Texas 7-tract water gap reproduces exactly.
`census-acs-housing`'s previously-open schema gap is now closed for real: `GEOID, STATEFP, COUNTYFP,
TRACTCE, housing_units, geometry`, identical across all four regions, zero nulls, one row per tract.

**A real planning gap was found, not created, here**: an earlier assumption that
`AWATER`/`INTPTLAT`/`INTPTLON` could be sourced from `<region>-census-tracts` for Step 10 does not
hold — direct inspection confirms none of the three columns exist on that table. Flagged explicitly
as a blocker for Step 10 to resolve with direct evidence instead of a second assumption (see Finding
9 below, where it was resolved exactly as flagged).

**Two smaller findings, carried forward without blocking anything**: `census-tracts` also ships
`pop_total`/`pop_urban`/`pop_rural`/`pct_urban`/`ur_class` (a ready-made rurality signal for Stage 8)
and `NAMELSAD` (human-readable tract names, used in Step 9's map); TIGER's `FULLNAME`/`RTTYP` null
rates move together almost exactly in every region, consistent with one shared cause (unnamed/local
roads).

**Full evidence**: `docs/data_manifest.md` Section 6 (in-notebook interpretation) and Section 7
("Still open" — the ACS-housing and AWATER bullets).

## 3. Finding — MTFCC/`class` filter verification, R-006 closed (Step 3)

**Checked**: whether the documented TIGER (`MTFCC in (S1100, S1200)`) and Overture (`subtype ==
"road"`, `class in (motorway, trunk, primary, secondary)`) named-highway filters are exact against
real data in all four regions, or whether a lexical near-miss (the same risk class already proven
real for POI categories in Stage 1) exists.

**Result**: R-006 is closed with real evidence. TIGER's real package contains only 4 MTFCC codes at
all (`S1100`, `S1200`, `S1400`, `S1630`) — a curated subset of the ~14-code national product — with
zero near-misses; the filter keeps 0.35%-1.62% of each region's real TIGER network. Overture's
`subtype` is confirmed 100% `"road"` in every region; `overture-roads` is itself a curated 7-class
subset of the real 17-class taxonomy, zero near-misses, and the diff against
`overture-roads-unfiltered` (identical excluded-class set across all four regions) confirms the
specific `*_link` ramp/connector hypothesis this check was built to test does not apply — no such
values exist anywhere in this project's real data. The filter keeps 11.42%-18.27% of each region's
Overture network. **No change needed to `gaps.py`'s filter logic.**

**Beyond R-006's original scope**: both reference layers are already curated subsets of their full
raw products, consistently across regions — never stated as such before now. The two filters' real
retention rates are asymmetric and region-varying (TIGER 0.35%-1.62% vs. Overture 11.42%-18.27%, a
~7x-33x spread by region) — a methodological caveat for Stage 7's gap formula: a raw count ratio
partly reflects this classification-scheme mismatch, not physical coverage difference alone.

**Full evidence**: `docs/data_manifest.md` Section 4.21; `docs/risk_register.md` R-006.

## 4. Finding — transport-only-undefined self-check, with a genuine root-cause fix (Step 4)

**Checked**: whether this project's own tract-level "does this tract have a named-highway" logic
reproduces the challenge's published transport-only-undefined counts exactly, in all four regions.

**Result**: reproduced **exactly** — 869/218/253/1,704 out of 1,593/591/1,192/6,003 scored tracts —
but only after a real methodological correction, not a rounding-tolerance pass. The original bare
`predicate="intersects"` existence test undercounted `eastern-ok` by exactly 2 tracts; diagnosis
traced this to TIGER named-highway segments that touch a tract boundary at a single vertex —
topologically true under `intersects()`, zero real length once clipped. Switching to a clipped-length
definedness test (`gpd.overlay` + `geodesic_length_m`) closed the gap exactly, and Step 8's
independent raw-length cross-check confirmed the same phenomenon recurs in all four regions (not just
`eastern-ok`).

**Carry forward to Stage 7 (hard requirement)**: `gaps.py`'s real `transport_defined` flag must use
clipped road length inside the tract boundary, not a bare spatial-join existence predicate.

**Full evidence**: `docs/data_manifest.md` Section 4.22; `docs/risk_register.md` R-008.

## 5. Finding — transport-gap ratio sanity bound (Step 5)

**Checked**: whether each region's `overture_over_tiger` named-highway length ratio falls inside the
documented `[0.71, 1.59]` band.

**Result**: yes, in all four regions — `maricopa-az` 1.296, `northern-ca` 1.173, `eastern-ok` 0.719,
`south-central-tx` 1.542. `eastern-ok` sits only 0.009 above the band floor, the tightest margin of
the four and the only region where TIGER's network substantially exceeds Overture's — corroborated by
two other, independent findings in this notebook (Section 4.9's building `subtype`/`class` null-rate
gradient, highest in `eastern-ok`; Step 3's filter-retention-rate asymmetry), together forming a
consistent, three-way-confirmed picture of `eastern-ok`'s mapping-completeness gap.

**Both of Stage 5's named exit criteria (Steps 4 and 5) are now met, in writing.**

**Full evidence**: `docs/data_manifest.md` Sections 4.6 and 4.22.

## 6. Finding — tract-count and cross-region GEOID-uniqueness regression tests (Step 6)

**Checked**: whether the raw strata tract packages, the scored tract lists, and cross-region GEOID
uniqueness all reconcile as expected.

**Result**: three regions reconcile exactly; `south-central-tx`'s 6,010-vs-6,003 gap is exactly the
documented 7-tract water exclusion, confirmed again independently. Zero tracts are missing from any
strata package. Cross-region GEOID uniqueness holds for both the scored lists (9,379 GEOIDs, zero
collisions) and, as an added check, the full raw tract packages (9,386 GEOIDs, zero collisions) — no
tract double-counted anywhere, including at the Maricopa/New Mexico state line.

**Full evidence**: `docs/data_manifest.md` Section 4.23.

## 7. Finding — `cbp_estab == cbp_estab_bus` equality check (Step 7)

**Checked**: whether `cbp_estab` is exactly equal to `cbp_estab_bus` in every real row, in every
region, including a null-safe check for rows where both are simultaneously null.

**Result**: confirmed equal in all 9,386 real CBP rows across all four regions; zero both-null rows
found anywhere. `cbp_estab_bus` remains the documented default weighting for Stage 7, now backed by a
real equality proof.

**Full evidence**: `docs/data_manifest.md` Section 4.24.

## 8. Finding — local distribution sanity checks (Step 8)

**Checked**: whether the raw per-tract road-length distributions feeding the transport component are
plausibly shaped (not degenerate) before any gap ratio is computed, in either source, in any region.

**Result**: both TIGER and Overture per-tract named-highway length distributions are right-skewed and
well-behaved in every region, with no all-zero or single-spike pathology. This section's raw
(unclipped) touching-road count also independently corroborated Finding 4's root-cause fix
project-wide: every region undercounts under a non-clipped method by exactly the number of
boundary-vertex-touching slivers present there (4, 4, 2, 17 across `maricopa-az`/`northern-ca`/
`eastern-ok`/`south-central-tx`).

**`src/viz.py` note**: `plot_distribution_grid` was kept notebook-local for this stage rather than
moved into `src/viz.py` (the guideline's original plan), an explicit, flagged deviation — `src/viz.py`
remains a placeholder for a future stage to populate for real, not silently left undone.

**Full evidence**: `docs/data_manifest.md` Section 4.24.

## 9. Finding — face-validity spot map (Step 9)

**Checked**: whether Maricopa's early per-tract road-density computation correlates sensibly with
known geography — dense urban tracts should show denser coverage, remote rural tracts sparser.

**Result**: passes cleanly. The percentile-clipped (2nd/98th) choropleth shows a spatially coherent
bright cluster over the Phoenix metro core against a uniformly dark rural/desert periphery, with no
isolated outlier tract dominating the color scale — qualitative confirmation the shared per-tract
length aggregation (Findings 4, 8) is spatially sound.

**Full evidence**: `docs/data_manifest.md` Section 4.25.

## 10. Finding — water-dominated and boundary-edge tract identification; `national-census-tracts` schema resolved (Step 10)

**Checked**: resolves the Finding 2 blocker (where do `AWATER`/`INTPTLAT`/`INTPTLON` actually live)
and identifies water-dominated tracts and per-tract representative points for all four regions.

**Result**: `national-census-tracts` (85,396 rows) carries `AWATER` but not `INTPTLAT`/`INTPTLON` —
confirming Finding 2's flagged prediction exactly. Water dominance is computed from the real national
`AWATER` join; point resolution falls back to a geometric centroid via equal-area reprojection,
explicitly flagged as lower-fidelity rather than presented as authoritative. Water-dominated tract
counts (`water_fraction > 0.5`): `maricopa-az` 0, `northern-ca` 2, `eastern-ok` 1, `south-central-tx`
47. The `south-central-tx` known-water-tract list, derived from the data itself, matched the
documented 7 tracts exactly, all at `water_fraction = 1.0`.

**Carry forward to Stage 7/8**: 3 water-dominated tracts (1 `eastern-ok`, 2 `northern-ca`) remain in
the official *scored* set despite being more than half water by area — a named, quantified confound
(GEOID lists in `water_dominated["eastern-ok"]`/`water_dominated["northern-ca"]`) that Stage 7's
pipeline should be able to flag and Stage 8/9's Bias Discovery analysis should control for.

**Full evidence**: `docs/data_manifest.md` Section 4.26; `docs/risk_register.md` R-009.

## 11. Finding — component correlation structure: deferred to Stage 7 (Step 11)

**Checked**: whether a cheap, single-region (Maricopa) correlation between raw transport/building/POI
proxy counts could be computed without real spatial-join engineering.

**Result**: no — Maricopa's `overture-buildings` layer alone (2,908,224 rows) exceeds the
2,000,000-row cheap-check threshold this step is explicitly permitted to gate on. Deferred to Stage 7
deliberately, per the Step 0 resolution, rather than forced through an EDA notebook.

**Full evidence**: `docs/data_manifest.md` Section 4.27.

## 12. Carry-forward list — seeding Stage 7's `docs/scoring_assumptions.md`

1. **Hard requirement**: transport-component definedness must use clipped road length inside the
   tract boundary (`gpd.overlay` + `geodesic_length_m`), not a bare spatial-join existence predicate
   — proven necessary in every region (Finding 4).
2. The documented MTFCC/`class` filters need no changes (Finding 3), but the transport-gap ratio's
   interpretation should account for the two sources' asymmetric filter-retention rates as a known
   classification-scheme artifact, not pure coverage signal (Findings 3, 5).
3. `cbp_estab_bus` can be used as the CBP establishment count with full confidence it equals
   `cbp_estab` everywhere (Finding 7).
4. The 3 non-`south-central-tx` water-dominated tracts (Finding 10) are a named, controllable
   confound for the building/POI components and a candidate covariate for Bias Discovery.
5. `eastern-ok`'s mapping-completeness gap is corroborated by three independent measurements
   (Overture building metadata null rate, transport-gap ratio proximity to the band floor,
   filter-retention-rate asymmetry) — worth citing together, not separately, in later write-ups.
6. `census-tracts`' `pop_total`/`pop_urban`/`pop_rural`/`pct_urban`/`ur_class` columns are a
   ready-made rurality signal for Stage 8, already classified `role=population` in the national
   schema (Finding 2).
7. `src/viz.py` remains unpopulated by this stage (Finding 8) — a real task for whichever stage next
   needs shared, reusable plotting functions, not an oversight to silently carry forward unlabeled.

## 13. What Stage 5 did not attempt (by design)

No real `coverage_gap_score`, `building_gap`, or POI-component computation exists anywhere in this
notebook. The Reference Reconstruction Engine, its two-tier fixture test suite, and the real
`transport_defined`/`building_defined`/`poi_defined` pipeline logic are Stage 7's job in full — this
stage's findings (especially Finding 4's clipped-length requirement) inform that build, they do not
substitute for it.
