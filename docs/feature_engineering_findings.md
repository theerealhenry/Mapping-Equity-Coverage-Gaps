# Feature Engineering Findings — Stage 6

A durable, human-readable record of everything Steps 0-9 of Stage 6 did and found, executed live
against all four challenge regions. This document mirrors the pattern `docs/eda_findings.md`
established for Stage 5: `src/geometry.py`, `src/features.py`, and the assembled
`data/processed/<region>-tract-features.parquet` files are the reproducible, executable record;
this is the readable one. Every finding below cross-references its full evidence in
`docs/risk_register.md` and `docs/decision_log.md`, where the underlying numbers and methodology
live in permanent detail — this document's job is to be the one a reviewer, a future me, or a
Best-Documentation judge opens first, not to duplicate that detail.

Dated 2026-09-17. Stage owner: Henry Otsyula.

## 1. What Stage 6 set out to do, and its scope boundary

Stage 6's job (`claude/stage6-feature-engineering-guideline.md`) is to build every spatial-
assignment primitive and every derived feature column the project needs, and assemble them into
one schema-validated, tract-indexed feature table per region. It does **not** compute a real
`coverage_gap_score` — that composite, and the calibration that picks a winning variant per
component, is Stage 7's job in full. Three genuine ambiguities in `PROJECT_BLUEPRINT.md` itself
were resolved in writing before any code was touched (Step 0): the spatial-assignment primitives
belong in `src/geometry.py` and are built now, not at Stage 7; Stage 6 computes a capped-ratio gap
value **per candidate spatial-assignment variant**, not one authoritative value, since the winning
variant isn't chosen until Stage 7's calibration; and the hospital-exclusion filter (R-004) is
implemented here, at the point the facility counts are built, not later in `gaps.py`.

## 2. Finding — spatial-assignment primitives built once, shared everywhere (Step 2)

**Checked**: whether point-in-polygon, dual building-assignment (centroid vs. intersection), and
line-clip-and-sum could all be built as tested, reusable primitives in `src/geometry.py`, rather
than re-implemented ad hoc in `src/features.py` and later in Stage 7's `src/gaps.py`.

**Result**: all three families were built — `assign_points_to_tracts` (point-in-polygon, via
`predicate="within"`), `assign_buildings_by_centroid` and `assign_buildings_by_intersection` (both
built, not one chosen, so Stage 7's calibration has real RMSE evidence to compare rather than a
coin flip), and `assign_and_clip_lines` (Stage 5's own already-validated clipped-length fix,
promoted from notebook-local code into this shared module rather than re-derived). Every centroid
computation goes through equal-area reprojection, never raw CRS84 — the exact bug Stage 5 caught
and fixed once for tract centroids, now enforced structurally for building centroids too.

**Full evidence**: `docs/decision_log.md`'s Stage 6 Steps 6-7 entry; `src/geometry.py` itself.

## 3. Finding — raw ingredients and candidate gap values, all four regions (Step 3)

**Checked**: whether the per-component raw counts/lengths (transport, buildings — both assignment
variants, POI facilities with hospitals excluded, POI establishments) and their candidate
capped-ratio gap values could be built region by region, starting with the smallest
(`eastern-ok`), without silently re-deriving decisions Stage 5 had already settled.

**Result**: built for all four regions, reusing Stage 5's clipped-length transport logic and the
Stage 1-confirmed real `categories.primary` string list directly (never a substring/fuzzy match —
the `security_systems`-contains-"ems" near-miss stays a live, proven risk this filter avoids). The
hospital-exclusion filter (R-004) was implemented at this exact point, resolving Step 0's Ambiguity
3.

**A real, previously-undetected bug was found here, but only surfaced at Step 9** (see Finding 8
below): `build_transport()` never applied its own documented named-highway class filters before
clipping, so every raw transport length in this step's first pass was silently wrong (the entire
road network, not just named highways). The bug was root-caused and fixed at Step 9, and Step 3
was re-run for all four regions with the fix in place — this finding is recorded here, at its true
point of origin, rather than only at Step 9 where it was caught.

**Full evidence**: `docs/risk_register.md` R-004 (hospital exclusion), R-011 (the transport-filter
bug).

## 4. Finding — strata join features attached without touching the scoring boundary (Step 4)

**Checked**: whether every relevant SVI/tribal/rurality/hazard/CVI column, plus `census-tracts`'
own rurality signal (`pop_total`/`pop_urban`/`pop_rural`/`pct_urban`/`ur_class`, carried forward by
name from Stage 5 Finding 2/6), could be attached to each scored tract via a single GEOID merge
against the already-joined 232-column `national-strata-tract-table`, with correct `feature_role`
tagging throughout.

**Result**: `STRATA_FEATURE_COLUMNS` (`src/features.py`) curates ~63 columns from that table —
SVI, tribal status/sub-type, RUCA/RUCC/NCHS rurality, heat/wildfire/drought exposure, CVI pillars,
and the population/rurality columns — every one tagged `research` (a vulnerability/context signal)
or `diagnostic` (a `*_covered` trustworthiness flag, never a signal itself), never `competition`.
`join_strata_features()` is a single merge, not 25 per-domain joins, because every curated column
was confirmed present in the pre-joined table directly against `docs/schema_catalog.csv` before
being listed — no fallback logic needed today.

**Full evidence**: `src/features.py`'s `STRATA_FEATURE_COLUMNS` and `join_strata_features()`.

## 5. Finding — derived Bias Discovery features, three left un-populated for a named reason (Step 5)

**Checked**: whether every named blueprint derived feature — four dispatch-blind-reachability
candidates, source-provenance vector, confidence-reporting features (kept as two distinct
columns), component-dominance/definedness, distance-to-tract-boundary, population-weighted gap
stats, and region as an explicit control column — could be designed, unit-tested, and traced to a
specific prior finding.

**Result**: all seven families were designed and unit-tested (`src/features.py`'s `__main__`
self-checks, all PASS): `dispatch_blind_reachability` (`dispatch_blind_threshold_and`,
`dispatch_blind_normalized_euclidean`, `dispatch_blind_product`, `dispatch_blind_dari` — all four
kept, none chosen, pending Stage 9's interpretability/stability/sensitivity selection);
`confidence_features` (`confidence_reporting_rate` and `mean_reported_confidence`, deliberately
never conflated — hand-verified with a fixture proving a missing value is excluded from both the
numerator and denominator of the mean, not silently treated as zero); `source_provenance_vector`
(`osm_share`, `microsoft_share`, `google_share`, `other_share`, `n_sources`, `dominant_source`,
`source_entropy`); `component_dominance_and_definedness` (`dominant_component`,
`n_components_defined`, `undefined_components`); `distance_to_tract_boundary_m`;
`population_weighted_gap_stats`; and `attach_region`.

**A real gap, flagged rather than silently absorbed**: three of these seven families —
`confidence_features`, `source_provenance_vector`, `distance_to_tract_boundary_m` — are NOT called
by Step 6's assembly script and are absent from the assembled
`data/processed/<region>-tract-features.parquet`, because their raw per-record inputs were never
gathered. Step 3's ingredients script aggregates Overture buildings/roads/POIs straight down to
per-tract counts/lengths; it never retains per-tract LISTS of individual records' `confidence`
values or `sources[].dataset` strings, and no facility-point geometry (reprojected to `EPSG:5070`)
was gathered for the boundary-distance calculation. This does not affect the leaderboard score —
`COMPETITION_ALLOWED_COLUMNS` is empty regardless, and none of these three were ever going to be
`feature_role=competition` — but it is a real gap for the Best Bias Discovery submission specifically,
since source-provenance and confidence-reporting patterns are original, non-obvious equity signals,
and `distance_to_tract_boundary_m` is the specific mechanism for eastern-OK's tribal-tract
edge-effect story.

**Carry forward, named explicitly, before Stage 8 begins**: this gap (`docs/risk_register.md`
R-010) must be closed before Stage 9's Bias Discovery analysis needs these columns, and closing it
cleanly is scoped as work to land **before Stage 8**, not folded silently into Stage 8/9 later.
Concretely: extend Step 3's raw-ingredient gathering (or add a Step 6b) to aggregate, per tract,
LISTS (not just counts) of `confidence` off `overture-pois`/`overture-buildings`/`overture-roads`,
LISTS of `sources[].dataset` off the same three layers, and facility-point geometry reprojected to
`EPSG:5070` for the boundary-distance calculation — then re-run the three already-written,
already-tested functions (`confidence_features`, `source_provenance_vector`,
`distance_to_tract_boundary_m`) against those real inputs. No redesign is needed; only new
raw-data gathering, since all three functions are already built and unit-tested against hand-built
fixtures.

**Full evidence**: `docs/risk_register.md` R-010; `docs/decision_log.md`'s Stage 6 Steps 6-7 entry.

## 6. Finding — schema-validated assembly, competition-column enumeration enforced structurally (Step 6)

**Checked**: whether Steps 3-5's outputs could be assembled into one tidy, `GEOID`-indexed table
per region, with `feature_role` as real, schema-enforced metadata rather than a side-document
claim.

**Result**: `TRACT_FEATURES_SCHEMA` (`src/schemas.py`, registered in `LAYER_SCHEMAS` under
`TRACT_FEATURES_LAYER`) validates GEOID-as-string, non-negative raw counts/lengths, `[0,1]` range
on every gap/ratio and dispatch-blind column, non-null `*_defined` booleans, and — critically — a
frozen `COMPETITION_ALLOWED_COLUMNS` constant that is empty today by design (Step 0 Ambiguity 2:
no gap-value variant is frozen into the score until Stage 7's calibration chooses one). Confirmed
against real data in all four regions: 100 columns per table, all four
`data/processed/<region>-tract-features.parquet` files validate `PASS`, row counts match exactly
(maricopa-az 1593, northern-ca 591, eastern-ok 1192; south-central-tx wrote 6010 — the region's
full `census-tracts` membership, not the 6003 scored subset, the same known split Step 3 already
established, not a defect).

**Full evidence**: `docs/decision_log.md`'s Stage 6 Steps 6-7 entry.

## 7. Finding — competition-only enforcement gate built and proven fail-closed (Step 7)

**Checked**: whether a standalone, testable allowlist function could physically enforce the
challenge's own rule — "the scored coverage gap computation must use only the datasets provided
for this challenge" — ahead of Stage 7 needing to reconstruct that boundary from documentation
alone.

**Result**: `assert_competition_only(columns_used)` (`src/features.py`) checks any column set
against `COMPETITION_ALLOWED_COLUMNS`, fail-closed: since that set is empty today, the function
currently rejects ANY non-empty input, correctly, by design, until Stage 7's calibration freezes a
winning variant into it as a deliberate, reviewed change. Proven with a fixture: a call with a
research-tagged column (`svi_overall`) is confirmed REJECTED, naming the disallowed column in the
raised error rather than returning a silently-ignorable bool.

**Full evidence**: `docs/decision_log.md`'s Stage 6 Steps 6-7 entry; `src/features.py`'s Check 4.

## 8. Finding — Step 9 cross-checks caught a real, previously-undetected pipeline bug (Step 9)

**Checked**: row counts against `SCORED_TRACT_COUNTS`; whether the transport-component raw
lengths reproduce Stage 5 Section 4.22's published transport-only-undefined counts exactly;
whether the 3 water-dominated tracts Stage 5 identified show visibly extreme or `*_defined=False`
values in this stage's own output; and whether the hospital-exclusion filter's delta matches the
documented Overture-overcount magnitude.

**Result**: the first run of the transport-length check failed badly (0/0/0/2 computed
transport-only-undefined tracts against a published 869/218/253/1704) — traced, by a targeted
diagnostic script and then direct code review (not guessed), to `build_transport()`
(`scripts/build_stage6_step3_ingredients.py`) never applying its own documented named-highway
class filters before clipping: it summed the entire road network, not just named highways, despite
its own docstring. Fixed by adding the two missing filter lines, then re-running Step 3 → Step 6
for all four regions. All four checks then passed cleanly: row counts (3 exact, south-central-tx's
7-row gap re-confirmed as the documented water exclusion), transport-undefined counts (exact match
to Section 4.22 in every region: 869/218/253/1704), water-dominated tracts (exact match in both
regions, with the specific GEOIDs visible for the first time — `eastern-ok` `40109108508`;
`northern-ca` `06033000502`, `06033000704`), and hospital exclusion (every region overcounts
5.43x-8.54x, confirming R-004's exclusion decision holds everywhere, though the previously
documented "~12x everywhere" figure — quoted from the challenge's own data README rather than
measured directly — did not hold as an exact multiplier; `docs/data_manifest.md` Section 4.4 was
corrected to the real measured spread).

**Full evidence**: `docs/risk_register.md` R-011; `docs/decision_log.md`'s Stage 6 Step 9 entry;
`scripts/verify_stage6_step9.py`.

## 9. What Stage 6 did not attempt (by design)

No real `coverage_gap_score` or calibration between candidate spatial-assignment variants exists
anywhere in this stage's output. Choosing the winning building-assignment rule (centroid vs.
intersection) and freezing exactly one gap-value variant per component into
`COMPETITION_ALLOWED_COLUMNS` is Stage 7's job in full — this stage deliberately built and kept
every reasonable candidate rather than picking one early, so Stage 7's calibration has real,
already-computed evidence to compare rather than having to re-run any spatial join itself.

## 10. Carry-forward list — seeding Stage 7's calibration and Stage 8/9's Bias Discovery work

1. **Both building-assignment variants exist and are both legitimate** —
   `overture_building_count_centroid`/`_intersection` and
   `microsoft_building_count_centroid`/`_intersection`, with matching `building_gap_centroid`/
   `_intersection` values — kept deliberately (Step 0 Ambiguity 2) so Stage 7's Tier-A calibration
   can compare them on real RMSE evidence rather than a guess.
2. **The hospital-exclusion filter (R-004) lives in Stage 6 now**, at the point the per-facility
   POI counts are built (Step 3), not in Stage 7's `gaps.py` — `gaps.py` simply reads the
   already-correct `poi_gap_fire`/`poi_gap_ems`/`poi_gap_schools` columns. The exclusion is
   confirmed warranted in every region (5.43x-8.54x overcount), not just the one region originally
   checked.
3. **Four dispatch-blind-reachability candidates await Stage 9's selection**:
   `dispatch_blind_threshold_and`, `dispatch_blind_normalized_euclidean`, `dispatch_blind_product`,
   `dispatch_blind_dari` — all four computed and schema-valid; none chosen yet. Stage 9 selects by
   interpretability, stability, and sensitivity, not here.
4. **Hard requirement carried from Stage 5, re-confirmed here**: `transport_defined` must use
   clipped road length inside the tract boundary through the documented named-highway class
   filters (`OVERTURE_NAMED_HIGHWAY_CLASSES`, `TIGER_NAMED_HIGHWAY_MTFCC`) applied BEFORE clipping
   — Step 9's own cross-check is what caught the one place this stage's first implementation
   missed that requirement (Finding 8); the fix is confirmed, but the requirement itself is now a
   two-time-proven hazard worth stating explicitly for Stage 7's `gaps.py`, which will re-implement
   an equivalent computation.
5. **Must land before Stage 8 begins, not deferred into it silently**: close R-010 by extending
   Step 3's raw-ingredient gathering to retain per-tract LISTS (not just counts) of `confidence`
   and `sources[].dataset` off `overture-buildings`/`overture-roads`/`overture-pois`, plus
   facility-point geometry in `EPSG:5070`, then re-run the three already-tested functions against
   real inputs:
   - `confidence_features` → `confidence_reporting_rate`, `mean_reported_confidence`
   - `source_provenance_vector` → `osm_share`, `microsoft_share`, `google_share`, `other_share`,
     `n_sources`, `dominant_source`, `source_entropy`
   - `distance_to_tract_boundary_m`

   No redesign is needed — all three functions are already built and unit-tested against
   hand-built fixtures; only the raw per-record inputs remain to be gathered. Skipping this would
   mean Stage 8/9 falls back on the same rural/urban and SVI-decile cuts every other submission is
   likely to run, losing the project's most original Bias Discovery signal.
6. **`eastern-ok`'s mapping-completeness gap** (Stage 5's three-way-confirmed finding) is a live
   example of exactly the cross-region-comparability artifact `region` as a control feature exists
   to let Stage 8 account for — cite it there, not as a fresh discovery.
7. **The `docs/data_manifest.md` Section 4.4 hospital-overcount figure was corrected** from an
   unverified "~12x everywhere" (quoted from the challenge's own data README) to the real measured
   5.43x-8.54x spread — Stage 8/9 write-ups should cite the corrected figure, not the original one.

## 11. Where this stage's work is recorded

`docs/risk_register.md` gains R-010 (open, must close before Stage 9) and R-011 (mitigated, closed
with real-data verification). `docs/decision_log.md` carries the full Steps 6-7 entry and the Step
9 entry, including the transport-filter bug's discovery, fix, and confirmation. This document is
the single place Stage 7 and Stage 8/9 should open first to know what candidate columns exist,
what each means, and which decisions are still open versus already settled and not to be silently
redone.
