# Decision Log

Populated continuously from Stage 6 onward, per `PROJECT_BLUEPRINT.md`. Distinct from
`docs/scoring_assumptions.md`: this log records *why* an implementation choice was made over its
alternatives (a different audience/purpose than "what the scorer does"). Example entry shape:
`Decision D014 — Date: [date] — Question: how should boundary-crossing buildings be assigned? —
Options: A. centroid, B. intersection, C. area-weighted split — Decision: B — Evidence: [link to
the relevant calibration experiment] — Consequences: [what this implies downstream]`.

Empty of Stage 6+ implementation decisions as of this writing — the first genuine "why X over Y"
implementation choice belongs to Stage 6 onward, and none has been made yet. Stage 4 itself (the
repository restructure this file was created during) gets one entry below despite predating this
log's normal scope, since it is the one Stage 4 fact worth a permanent, easy-to-find record rather
than tribal knowledge from one session.

## Stage 4 — Repository restructure: complete

**Date**: 2026-09-06

**What was done**: The repository was brought into the exact shape `PROJECT_BLUEPRINT.md` Section 4
names, per the 16-step implementation guideline (`stage4_implementation_guideline.md`). Steps 1-2
(branch/baseline checkpoint, re-verifying the inventory findings) were explicitly skipped at
Henry's direction, since every step from Step 3 onward only creates new paths and touches nothing
already committed — there was nothing for a safety branch to protect against. Steps 3-14 ran in
full:

- `configs/` created, scoped by its own README to environment-only settings, never region/formula
  constants (those stay in `src/config.py` by design).
- Seven docstring-only placeholder modules added to `src/` (`features.py`, `gaps.py`,
  `statistics.py`, `diagnostics.py`, `bias_api_replica.py`, `viz.py`, `validate.py`), each naming
  its owning stage and responsibilities, no function signatures or stubs.
- `app/` skeleton created (`explorer.py` placeholder, `data/`, `requirements.txt`).
- Four placeholder notebooks added (`01_eda`, `02_pipeline_dev`,
  `03_building_vs_housing_analysis`, `04_bias_discovery`), each a single valid markdown-title cell.
- `scripts/download/download_data.ps1` and `scripts/submission/build_submission.py` /
  `build_submission_notebook.py` placeholders added.
- Top-level `submission/` created (README only, explicitly marking the eventual generated notebook
  as never hand-edited).
- `scoring/v1/` created (README explaining the versioning scheme; empty of the actual frozen
  artifact, which is Stage 7's job).
- Two placeholder test files added to `tests/` (`test_gap_arithmetic.py`,
  `test_geometry_assignment.py`), zero test functions yet — `pytest` collects and passes with no
  new failures from an empty test file.
- `docs/` extended: `model_card.md`, `scoring_assumptions.md` as true empty placeholders;
  `docs/risk_register.md` seeded with all six risks already identified in Stages 1-3's own real
  findings (GEOID-as-integer truncation, CRS axis order, ACS-in-denominator, hospital inclusion,
  zeroing-vs-excluding undefined components, unfiltered road classes) — two of the six
  (GEOID-as-integer, CRS axis order) already marked Mitigated, since their fixes exist in
  `src/io.py` and `src/geometry.py` today; `docs/validation/`, `docs/experiments/`, `docs/figures/`
  created empty.
- `.gitignore` gained `mlruns/` and `models/`.
- `.github/workflows/tests.yml` deliberately **not** created (Step 13) — an empty CI workflow would
  give a misleading false-green badge before there's anything real to check; this file is Stage
  10's responsibility in full.
- One real documentation gap surfaced during this pass and fixed: `PROJECT_BLUEPRINT.md`'s Section
  4 tree never explained that Stage 1-3's flat one-off scripts stay at `scripts/` root, or that
  `scripts/verify_bucket.py` is deliberately never moved despite looking superseded by `scripts/
  audit/audit_bucket.py` — that reasoning existed only in `docs/data_manifest.md` and this session's
  own working notes. Added a permanent note directly under the Section 4 tree recording it.

**Verification performed (Step 14)**: `pytest -q` returned 469 passed, 2 skipped both before and
after the restructure (the 2 skips are the pre-existing, environment-only DuckDB spatial-extension
download failures) — zero new failures from any placeholder file. All seven new `src/` placeholder
modules were confirmed to import cleanly. The full repository tree was diffed against Section 4
file-by-file — every named path exists, nothing extra was created. The `scripts/verify_bucket.py`
cross-reference grep was re-run and confirmed unbroken.

**Consequences**: Stages 5 onward now have every path they'll write into already in place, with an
honest placeholder or the real already-scaffolded file — no future stage needs to stop and build
structure instead of pipeline logic. Nothing in this stage constitutes functional progress on any
later stage's actual work; every new file is either a directory-shape placeholder or a
docstring-only module naming its future owner.

## Stage 0.5 — Smoke-test submission: accepted

**Date**: 2026-09-07

**What was done**: Submitted a trivial, format-only file (`submissions/smoke_test_2026-09-07.csv`,
gitignored — not a candidate solution) built directly from `SampleSubmission 3.csv`: all 9,379
GEOIDs across the four regions, every gap-value column (`coverage_gap_score`, `transport_gap`,
`building_gap`, `poi_gap`, `poi_gap_fire`, `poi_gap_ems`, `poi_gap_schools`, `poi_gap_cbp`) set to a
constant `0.5`, every `*_defined` column set to `TRUE`, GEOID preserved as text (Maricopa's leading
zero intact). Sole purpose: confirm the platform accepts the 17-column combined-region shape before
any real pipeline exists, per Step 0.5 of the project plan — no scoring information was expected or
sought from this submission. Cost: 1 of 300 submissions.

**Outcome**: Accepted, not rejected — processed cleanly with no column-name, row-count, or blank-cell
error. Public score: RMSE = 0.440549264. Public leaderboard rank at time of submission: 67th (of the
participants who have submitted so far).

**What this smoke test actually confirmed**:
- The submission format is a full match to the platform's expectations (column names, row count,
  GEOID-as-text) — the concrete goal of this step, achieved on the first try.
- The Bias Scorecard mechanism behaves exactly as documented: with an identical constant across
  every tract, every disparity ratio it returned came back at exactly `1.00x`, and every stratum row
  — Rural vs Urban, Tribal vs Non-Tribal, High Social Vulnerability, High Climate Vulnerability,
  Summer Drought, Winter Drought, Wildfire Hazard, Summer Heat, High Hazard + High Vulnerability —
  read "Similar". This is a clean sanity check that the disparity-ratio math is
  disadvantaged-group-mean / reference-group-mean, not something else, and it independently
  reconfirms — this time from Henry's own account, not inferred from someone else's screenshot —
  the finer real stratification grid the 2026-09-03 leaderboard observation in
  `verification-findings.md` first flagged as unconfirmed (drought split Summer/Winter, heat as
  Summer Heat only, plus an intersectional "High Hazard + High Vulnerability" row). Carry this exact
  9-row grid into `src/bias_api_replica.py`'s design at Stage 9.

**A quantitative hypothesis this RMSE supports (evidence, not proof)**: for a constant guess `c`,
RMSE² = mean(y²) − mean(y) + c² for c=0.5 reduces to RMSE² = 0.25 − mean(y·(1−y)). The observed
RMSE² (0.19408) implies mean(y·(1−y)) ≈ 0.0559 across the scored public tracts — only about 22% of
the maximum (0.25) that quantity would take if the true `coverage_gap_score` were 0.5 everywhere.
That means the true reference scores are, on average, concentrated well away from the midpoint —
consistent with a distribution clustered toward the extremes (many well-covered tracts near 0, a
real tail of poorly-covered tracts near 1) rather than uniform or centered near 0.5. This is a
cheap, zero-risk-to-derive prior worth carrying into Stage 7 calibration expectations, but it comes
from one aggregate scalar over an unknown ~30% sample — a sanity-check expectation, not a target to
fit to, and not a substitute for the golden-case/self-validation work already planned.

**Leaderboard context, read with the same caution `verification-findings.md` already applied to the
2026-09-03 snapshot**: 67 participants have submitted at least once as of this submission. Several
exact-duplicate scores appear across unrelated accounts — e.g. `0.00000301` shared by three users,
`0.070956181` shared by five users at ranks 58-62 — far more consistent with many participants
running the same public tutorial/starter-kit output than with independent pipelines converging
bit-for-bit. This reinforces the project's existing position: early leaderboard rank (including this
submission's own 67th place) signals nothing about solution quality yet, only who has or hasn't
submitted something — real or a placeholder.

**Consequences**: Zero change to the Stage 5-13 plan. Format risk is retired before any real
computation exists; the Bias Scorecard's actual stratum grid is now directly confirmed rather than
inferred; and one legitimate, if soft, prior about the true target distribution's shape is available
for Stage 7. Submission budget spent: 1. Reserve remaining: 299.

## Stage 5, Step 1 — Preflight: complete, one real gap found and fixed

**Date**: 2026-09-07

**What was done**: Before starting Stage 5's real work, four checks were run directly on Henry's
own machine (`claude/stage5-eda-implementation-guideline.md` Step 1): `git status`, `pytest -q`,
a DuckDB `spatial`/`httpfs` extension load check, and a real bucket-read check using the project's
own loader (`src.io.load_strata_table("eastern-ok", "census-tracts")`) rather than a hand-rolled
query, so the check exercises the exact code path Stage 5 depends on.

**Results**:
- `pytest -q`: **471 passed, 0 skipped, 1 warning** (a `pandera` deprecation notice about importing
  from the top-level `pandera` module rather than `pandera.pandas` — harmless today, worth a small
  cleanup at some point, not urgent). This is a real, informative deviation from the 469 passed / 2
  skipped figure `docs/decision_log.md`'s Stage 4 entry recorded: the 2 skips there were already
  documented as "a pre-existing, environment-only DuckDB spatial-extension download limitation...
  not present on Henry's own machine's normal setup" — this run confirms that explanation directly
  rather than leaving it as an untested claim. **471 passed, 0 skipped is now the real baseline**
  Stage 5's own Step 14 verification pass (and every later stage's) should compare against on
  Henry's machine, not the 469/2-skip figure from the constrained environment Stage 4 was partly
  produced in.
- DuckDB `spatial`/`httpfs` extensions load cleanly; `duckdb.__version__` confirmed `1.5.4`,
  matching `requirements.txt`'s pin exactly.
- Real anonymous S3 bucket read via `load_strata_table("eastern-ok", "census-tracts")`: 1,192 rows
  (matching the published eastern-ok scored-tract count exactly), CRS confirmed `OGC:CRS84`, GEOID
  confirmed `object` dtype (string, not integer-coerced) with a real sample value
  (`40141070300`). Confirms the CRS-normalization and GEOID-string guards (R-002, R-001) are both
  working correctly against live data on Henry's own machine, not just in fixture tests.

**A real, previously-undetected gap found and fixed**: `git status` showed the entire `scoring/`
directory (`scoring/README.md` and `scoring/v1/`) as **untracked** — meaning it was never actually
committed during Stage 4, despite that stage's own decision-log entry listing
`scoring/v1/ created (README explaining the versioning scheme...)` among its completed deliverables
and stating Steps 3-14 "ran in full." The directory existed correctly on disk; it simply never
reached git. Fixed by committing it now, during Stage 5 preflight, rather than letting the gap
between "documented as done" and "actually in git history" persist further. No functional
consequence — nothing depended on `scoring/` being tracked yet — but it's exactly the kind of
drift this project's own "clean, meaningful commit history" discipline exists to catch.

**Verification performed**: All four checks above were run directly by Henry on his own machine and
their real output reviewed, not assumed from the guideline's expected values. The `scoring/`
tracking gap was caught from that real `git status` output, not from re-deriving Stage 4's steps.

**Consequences**: Step 1 of the Stage 5 guideline is closed. The real, machine-verified baseline
going forward is 471 passed / 0 skipped, not 469/2. `git status` is now expected fully clean after
the `scoring/` commit below. Stage 5 Step 2 (notebook scaffold) can proceed on a confirmed
foundation.

## Stage 5, Steps 2-13 — EDA-B: complete, both named exit criteria met

**Date**: 2026-09-07

**What was done**: `notebooks/01_eda.ipynb` was built and executed live, end-to-end, against all
four regions, across Steps 2-11 of `claude/stage5-eda-implementation-guideline.md`. Full findings
are recorded in `docs/eda_findings.md` (new, Step 12) and cross-referenced in `docs/data_manifest.md`
Sections 4.21-4.27. Summary of what each step produced:

- **Step 2** — all three layers (`census-tracts`, `census-tiger-roads`, `census-acs-housing`) load
  cleanly in all four regions; ACS-housing's schema gap closed for real; a real planning gap found
  (Section 4.17's `AWATER`/`INTPTLAT`/`INTPTLON`-from-`census-tracts` assumption does not hold) and
  flagged for Step 10 to resolve properly, rather than papered over.
- **Step 3** — `docs/risk_register.md` R-006 closed with real, live evidence from all four regions;
  both documented road-class filters confirmed exact, zero lexical near-misses, no change needed to
  `gaps.py`.
- **Step 4** — the transport-only-undefined self-check reproduces all four published counts exactly,
  but only after a genuine root-cause correction: the first implementation's bare spatial-join
  existence test undercounted `eastern-ok` by 2 tracts (boundary-vertex-touching road segments with
  zero real length once clipped); fixed by switching to a clipped-length definedness test, and
  independently confirmed as a project-wide (not region-specific) phenomenon by Step 8's raw-length
  cross-check. **Named a hard requirement for Stage 7's `gaps.py`.**
- **Step 5** — every region's transport-gap ratio falls inside the documented `[0.71, 1.59]` band;
  `eastern-ok`'s 0.719 is the tightest margin of the four, corroborated by two other independent
  findings elsewhere in this notebook and in prior stages.
- **Steps 6-9** — tract-count/GEOID reconciliation, `cbp_estab`/`cbp_estab_bus` equality, local
  distribution sanity, and the Maricopa face-validity map all pass cleanly with real data, closing
  three more previously-open items (`docs/data_manifest.md` Section 7).
- **Step 10** — resolves Step 2's flagged `AWATER`/`INTPTLAT`/`INTPTLON` gap exactly as predicted
  (present on `national-census-tracts`, not on the per-region tract table); reproduces
  `south-central-tx`'s 7 known water-exclusion tracts exactly (7-for-7); surfaces 3 additional
  water-dominated tracts (`eastern-ok` 1, `northern-ca` 2) that remain in the scored set — a new,
  named confound carried into `docs/risk_register.md` as R-009.
- **Step 11** — correctly deferred to Stage 7 (Maricopa's `overture-buildings` layer exceeds the
  cheap-check row threshold), per the Step 0 resolution.

**Both of `PROJECT_BLUEPRINT.md`'s named Stage 5 exit criteria are confirmed met**: the
transport-only-undefined percentages match the published ones exactly (not merely within rounding
tolerance) in all four regions, and the transport-gap ratio falls within the `[0.71, 1.59]` band in
all four regions. See `PROJECT_BLUEPRINT.md`'s Stage 5 section for the sign-off note itself.

**Verification performed**: every notebook cell was run top to bottom on a real, restarted kernel
(not resumed from stale state); every in-notebook `assert` passed; each section's real output was
reviewed and interpreted before being folded into this record, not assumed from the guideline's
expected values. Two genuine bugs were found and fixed along the way through this same
run-then-interpret discipline: the clipped-length root-cause fix (Step 4, above) and, earlier in the
same notebook, an `overture-roads-unfiltered` full-geometry load that froze Henry's machine on
`south-central-tx` (fixed by column-projecting to `class` only) and a silently-undisplayed
`class_set_comparison` result (fixed with an explicit `print()`) — both recorded in
`docs/data_manifest.md` Section 4.21.

**Consequences**: Stage 5 is functionally complete. Four concrete, load-bearing requirements carry
into Stage 7's `src/geometry.py`/`src/gaps.py` build (full list in `docs/eda_findings.md` Section
12): the clipped-length transport-definedness fix; the classification-scheme-asymmetry caveat for
the ratio formula; confirmed `cbp_estab`/`cbp_estab_bus` interchangeability; and the 3-tract
water-dominance confound. `docs/risk_register.md` gains R-008 (mitigated) and R-009 (open, Stage
7/8). Step 14's verification pass is the only remaining item before Stage 6 begins.

## Stage 5, Step 14 — Verification pass: complete, Stage 5 formally closed

**Date**: 2026-09-07

**What was done**: Per the guideline's own Step 14, three checks were run to confirm "the plan
produced the stated outcome" rather than assuming it from having followed the steps in order:
`pytest -q` re-run on Henry's own machine, `notebooks/01_eda.ipynb` re-run top to bottom on a
clean, restarted kernel, and a diff of Steps 2-13's actual output against this guideline's stated
deliverables.

**Results**:
- `pytest -q`: **471 passed, 1 warning, 0 skipped**, in 43.58s — exactly matching Step 1's
  preflight baseline (`docs/decision_log.md`'s "Stage 5, Step 1" entry), confirming Stage 5 added
  notebook content and documentation only, no new `src/` logic requiring new tests. The single
  warning is the same pre-existing, harmless `pandera` top-level-import deprecation notice Step 1
  already recorded — not a new warning introduced by this stage.
- `notebooks/01_eda.ipynb` was confirmed by Henry to run clean, top to bottom, on a fresh kernel —
  every cell executes without error, every in-notebook `assert` passes, matching the discipline
  Section 4.9 already established for the audit notebook.
- Diff against `claude/stage5-eda-implementation-guideline.md` Steps 2-13: every named deliverable
  is present and real (notebook sections, `docs/eda_findings.md`, the risk register/decision
  log/README/blueprint updates), with one deliberate, explicitly-flagged deviation carried forward
  rather than silently accepted: Step 8's guideline plan to move `plot_distribution_grid` into
  `src/viz.py` was not done this stage — it was kept notebook-local instead, at Henry's direction,
  and recorded as an open item in `docs/eda_findings.md` Section 8/Section 12 for whichever future
  stage next needs shared, reusable plotting functions. No other deviation found.

**Verification performed**: this entry itself is that verification note — the real `pytest` output,
the real notebook confirmation, and the real diff outcome, not restated from the plan.

**Consequences**: Stage 5 (EDA-B) is formally closed. `docs/README.md`'s badge and checklist were
also corrected during this pass to the confirmed 471-passing/0-skipped baseline (previously stale
at 469/2, a figure that predated Step 1's own re-verification and had not been carried forward into
the README until now). Stage 6 (Feature Engineering) may begin on a confirmed foundation.

## Stage 6, Steps 6-7 — Tract-features assembly, schema, competition-only gate — one deferral flagged

**Date**: 2026-09-16

**What was done**: `src/schemas.py` gained `TRACT_FEATURES_SCHEMA` (Step 6) — GEOID-as-string,
`[0, 1]` range on every gap/ratio column, non-negative on every count/length column, and a new
frozen constant `COMPETITION_ALLOWED_COLUMNS: frozenset[str] = frozenset()` — plus
`scripts/build_stage6_step6_features.py`, which assembles each region's
`data/processed/<region>-step3-ingredients.parquet` with Step 4's strata join
(`join_strata_features`) and the Step 5 derived columns that are actually computable from Step 3 +
Step 4 alone (`dispatch_blind_reachability`, `component_dominance_and_definedness`,
`attach_region`), then validates and writes `data/processed/<region>-tract-features.parquet`.
`src/features.py` gained `assert_competition_only(columns_used)` (Step 7) — an allowlist check
against `COMPETITION_ALLOWED_COLUMNS`, fail-closed by construction (the set is empty today, so it
currently rejects any non-empty input, correctly, until Stage 7's calibration freezes a winning
gap-value variant into that constant as a deliberate, reviewed change).

**Deviation flagged, not silently absorbed**: three Step 5 feature functions that were designed and
unit-tested in the prior Steps 4/5 pass — `confidence_features`, `source_provenance_vector`,
`distance_to_tract_boundary_m` — are NOT called by the Step 6 assembly script and are therefore
absent from the assembled `tract-features.parquet`. Root cause: their raw per-record inputs were
never gathered. Step 3's ingredients script aggregates Overture buildings/roads/POIs straight down
to per-tract counts/lengths; it never retains per-tract LISTS of individual records' `confidence`
values or `sources[].dataset` strings, and no facility-point geometry (reprojected to `EPSG:5070`)
was gathered for the boundary-distance calculation. Recorded in full as `docs/risk_register.md`
R-010.

**Why this is not urgent enough to block Step 6/7's close-out**: `COMPETITION_ALLOWED_COLUMNS` is
empty regardless of whether these three column families exist — none of them were ever going to be
`feature_role=competition`, so the leaderboard score is completely unaffected by the omission.

**Why it is still worth tracking deliberately (not silently dropping it)**: these three families
are exactly the kind of original, non-obvious equity signal the Best Bias Discovery prize rewards —
source-provenance and confidence-reporting rate as a second-order bias (does data quality itself
degrade in low-SVI/tribal tracts, independent of raw coverage-gap magnitude?), and
`distance_to_tract_boundary_m` specifically as the mechanism for eastern-OK's tribal-tract
edge-effect story (a facility just across a small, irregularly-shaped tribal statistical area's
boundary can make a tract look covered when it functionally isn't). Losing these permanently would
mean falling back on the same rural/urban and SVI-decile cuts every other submission is likely to
run.

**Verification performed**: `TRACT_FEATURES_SCHEMA` and `assert_competition_only` were both proven
against real, hand-built TDD fixtures, not just imported and assumed correct — a valid fixture row
passes; a fixture row with `transport_gap=1.5` (an out-of-range capped-ratio value) is confirmed
REJECTED by the schema; a fixture call to `assert_competition_only({"svi_overall"})` (a
research-tagged column) is confirmed REJECTED. All three ran and printed PASS in a sandboxed copy
of the package. `build_stage6_step6_features.py` was then run for real, by Henry, against all four
regions: `data/processed/<region>-tract-features.parquet` now exists for all four, every one
validates `PASS` against `TRACT_FEATURES_SCHEMA` (100 columns), and row counts match exactly —
maricopa-az 1593/1593, northern-ca 591/591, eastern-ok 1192/1192. south-central-tx wrote 6010 rows
against a printed "(expected 6003)": not a bug — Step 3's `full_index` is built from the region's
full `census-tracts` membership (`REGION_TRACT_COUNTS["south-central-tx"]` = 6010), not the scored
subset (`SCORED_TRACT_COUNTS["south-central-tx"]` = 6003), the same known split confirmed back in
Step 3 Phase 2; the script's verification print just compares against the wrong constant for this
one region — cosmetic, not a data defect. Population-weighted gap stats printed for all seven gap
columns in all four regions land in sane ranges with `n_tracts_used` shrinking exactly where
expected (e.g. `poi_gap_ems` far sparser than `poi_gap_fire`/`poi_gap_schools` in every region,
consistent with EMS stations being genuinely sparser than fire/school facilities).

**Consequences**: Step 6/7 are code-complete, unit-verified, AND now confirmed against real data in
all four regions — `data/processed/<region>-tract-features.parquet` exists and is schema-valid for
maricopa-az, northern-ca, eastern-ok, south-central-tx. `docs/risk_register.md` gains R-010 (open,
planned before Stage 9 — must land before Bias Discovery analysis begins, does not block Stage 6/7
close-out or Stage 7's scoring build). No other stage's timeline changes. Step 6/7 are formally
closeable pending Henry's go-ahead to proceed to Step 8.

## Stage 6, Step 9 — Cross-checks against Stage 5 findings: complete, one real bug found and fixed

**Date**: 2026-09-17

**What was done**: Per the guideline's own Step 9, four checks were run against the assembled
`data/processed/<region>-tract-features.parquet`, each written as if it were expected to fail, then
run to confirm it doesn't: (1) row counts vs. `SCORED_TRACT_COUNTS`; (2) transport-component raw
lengths reproducing Stage 5 Section 4.22's published transport-only-undefined counts exactly; (3)
the 3 water-dominated tracts Section 4.26 identified, confirmed present with extreme/`*_defined`
values; (4) the hospital-exclusion filter's delta against the documented Overture-overcount
magnitude. `scripts/verify_stage6_step9.py` was built to run all four.

**A real, previously-undetected bug found and fixed**: the first run of Check 2 failed badly — 0/0/0/2
computed transport-only-undefined tracts against a published 869/218/253/1704. Rather than guess,
`scripts/diagnose_transport_defined.py` was written first and confirmed `tiger_transport_length_m`
was never zero and implausibly large (max 6.5M meters for one tract). Direct code review of
`build_transport()` in `scripts/build_stage6_step3_ingredients.py` then found the actual cause: the
documented named-highway class filters (`OVERTURE_NAMED_HIGHWAY_CLASSES`, `TIGER_NAMED_HIGHWAY_MTFCC`)
were never applied before clipping — the function summed the entire road network, not just named
highways, despite its own docstring. This had been silently present since Step 3 was first built and
confirmed weeks earlier; Step 9's own "verify, don't assume" discipline is what caught it. Fixed by
adding the two missing filter lines, then re-running the full pipeline (Step 3 → Step 6) for all four
regions. Recorded in full as `docs/risk_register.md` R-011.

**A documentation-accuracy finding, not a pipeline bug**: Check 4 (hospital exclusion) initially
failed for `eastern-ok` alone (5.43x against an 8x-16x band built around `README.md`'s "~12x ...
everywhere" claim). Rather than either loosen the band arbitrarily or assume a pipeline bug, all four
regions were checked with the same query (`README.md`'s own wording — "everywhere" — justified this).
Real measured spread: maricopa-az 7.58x, northern-ca 8.54x, eastern-ok 5.43x, south-central-tx 7.19x
— every region unambiguously and materially overcounts (all comfortably above a loose `ratio > 3.0`
qualitative bar), confirming R-004's exclusion decision is warranted everywhere, but the documented
"~12x" figure does not hold as an exact multiplier in any single region. This is a wording issue in
`README.md`/`docs/data_manifest.md` Section 4.4, not a defect in the exclusion logic itself.

**Verification performed**: after the transport-filter fix, all four checks pass cleanly in every
region: row counts (3 exact matches; south-central-tx's 7-row gap re-confirmed as the documented
Section 4.23 water exclusion), transport-undefined counts (exact match to Section 4.22 in all four
regions: 869/218/253/1704), water-dominated tracts (exact count match in both regions, with the
specific GEOIDs now visible for the first time — `eastern-ok` `40109108508`; `northern-ca`
`06033000502`, `06033000704` — each showing the extreme/`*_defined` values R-009 predicted), and
hospital exclusion (all four regions pass the loosened, defensible bar, spread recorded above).

**Consequences**: Step 9 is formally closed — a clean pass on all four checks, with one real bug
found, root-caused, fixed, and confirmed resolved by an exact match across all four regions (not a
silently-ignored mismatch, per the guideline's own deliverable clause). `docs/risk_register.md` gains
R-011 (mitigated, closed with real-data verification). The "~12x everywhere" figure in
`docs/data_manifest.md` Section 4.4 — originally quoted from the challenge's own data README, never
independently measured against this project's own pipeline — is corrected in place, per Henry's
direction, to the real measured 5.43x-8.54x spread, with the change and its reason (this project's
own numbers should be the citation, not someone else's unverified figure) recorded directly in
Section 4.4 rather than silently overwritten. Step 10 (`docs/feature_engineering_findings.md`) can proceed on
a confirmed foundation once Henry gives the go-ahead.

## Stage 6, Step 10 — Feature engineering findings summary: complete

**Date**: 2026-09-17

**What was done**: `docs/feature_engineering_findings.md` was written, mirroring
`docs/eda_findings.md`'s exact structure — one numbered finding per step (Steps 2-9), what wasn't
attempted, and an explicit carry-forward list seeding Stage 7's calibration and Stage 8/9's Bias
Discovery work. The carry-forward list names precisely what Stage 7 inherits (both building-
assignment variants kept and why; where the hospital filter actually lives; the four dispatch-
blind-reachability candidates awaiting Stage 9's selection) and, at Henry's explicit direction,
calls out R-010's closure — gathering the raw per-record inputs `confidence_features`,
`source_provenance_vector`, and `distance_to_tract_boundary_m` need — as work that must land before
Stage 8 begins, not something silently deferred into it.

**Verification performed**: cross-checked against `src/features.py`'s real, current column names
and docstrings (not recalled from memory) before writing the findings document, so every column
name and function behavior quoted in it matches the actual code.

**Consequences**: Stage 7 and Stage 8/9 now have a single findings document to open first, matching
the precedent `docs/eda_findings.md` set for Stage 5. Step 11 (close-out) can proceed.

## Stage 6, Step 11 — Close-out: risk register, decision log, README, blueprint corrections

**Date**: 2026-09-17

**What was done**:
- `docs/risk_register.md`: R-004 corrected on two counts — its "roughly 12x" language is replaced
  with the real measured 5.43x-8.54x spread (matching the Section 4.4/Step 9 correction), and its
  status is corrected from "implementation lands with `src/gaps.py` in Stage 7" to reflect reality:
  the hospital exclusion is already implemented in Stage 6, in `build_poi()`
  (`scripts/build_stage6_step3_ingredients.py`), via `POI_FACILITY_CATEGORY_MAP`
  (`src/config.py`) simply omitting `hospital`, guarded by an inline `assert`. No new risk was
  added for the dual building-assignment variants — Step 9's cross-checks never compared
  `building_gap_centroid` against `building_gap_intersection` for a material tract-count asymmetry,
  so, per the register's own evidence-first pattern (R-006/R-008/R-009), nothing is recorded that
  wasn't actually measured; if Stage 7's calibration finds a material difference between the two
  variants, that is exactly the kind of finding this register should capture then, with real
  numbers, not now on spec.
- `docs/decision_log.md` (this file): the two Step 0 boundary-resolution choices are recorded below
  as named Decisions (D001, D002), not left as prose buried in the Steps 6-7 entry above — matching
  this file's own stated example format and its stated purpose (capturing "why X over Y," not just
  "what was done").
- `README.md`: stage badge (`stage-5%20of%2013%20complete` → `stage-6%20of%2013%20complete`) and
  the Project Status checklist updated — Stage 6 checked off, its real deliverables named
  (`src/features.py`, `src/geometry.py`'s spatial-assignment primitives, four
  `data/processed/<region>-tract-features.parquet` tables, `docs/feature_engineering_findings.md`),
  Stage 7 named as next.
- `PROJECT_BLUEPRINT.md`: Stage 7's "Activities — spatial-assignment logic and geometry ownership"
  heading and text corrected to describe testing and freezing an already-built module, per Step 0's
  Ambiguity 1 resolution, rather than implying `src/geometry.py`'s primitives are authored in Stage
  7 — the same "the blueprint should always describe what the project actually does, not an
  aspirational plan that's drifted from reality" standard Stage 4's own decision-log entry already
  established. Stage 6's own exit criteria (one schema-validated feature table per region, every
  column traceable to a definition and a `feature_role`, the competition/research boundary
  physically enforced) are confirmed met, in writing, in the corrected blueprint text.

**Decision D001 — Question: which stage builds `src/geometry.py`'s spatial-assignment primitives
(point-in-polygon, centroid-vs-intersection, line-clip-and-sum)? — Options: A. Stage 6 (this
stage cannot compute a single feature-table column without them); B. Stage 7 (per
`PROJECT_BLUEPRINT.md`'s Stage 7 "Activities" section, which originally listed this work there) —
Decision: A — Evidence: `src/geometry.py`'s own Stage-2-era docstring already settled this
directly ("that logic is Stage 6 work and is added to this same file then, not now"), and Stage 6
structurally cannot build a per-tract building or facility count without an assignment rule already
in hand — Consequences: `PROJECT_BLUEPRINT.md`'s Stage 7 text is corrected (this step) to describe
testing and freezing the already-built primitives via `tests/test_geometry_assignment.py` and the
calibration protocol, not authoring them.**

**Decision D002 — Question: does Stage 6 compute one authoritative capped-ratio gap value per
component, or one value per candidate spatial-assignment variant? — Options: A. One authoritative
value per component, matching the blueprint's literal "the capped-ratio gap value" wording; B. One
value per candidate variant (e.g. `building_gap_centroid`, `building_gap_intersection`), deferring
which one is authoritative to Stage 7 — Decision: B — Evidence: Stage 7's own activities include a
designed-experiment calibration that decides which spatial-assignment rule wins before any value
can be called final, so Stage 6 cannot compute "the" gap value before that choice is made; computing
every candidate now, once, is also the only way to avoid re-running an expensive spatial join per
calibration submission in Stage 7 — Consequences: `COMPETITION_ALLOWED_COLUMNS` (`src/schemas.py`)
is deliberately empty through Stage 6's close — every candidate column is tagged `competition`
(each is a legitimate reconstruction from only provided data) but none is yet the frozen choice;
Stage 7 selects exactly one column per component and records it in `scoring/v1/formula.yaml`.**

**Verification performed**: `docs/risk_register.md`'s R-004 row, `README.md`'s badge/checklist, and
`PROJECT_BLUEPRINT.md`'s Stage 7 heading were each re-read after editing to confirm they now
describe what the project actually built, not the original plan. Stage 6's exit criteria were
checked line by line against real evidence already recorded in this log's Steps 6-7 and Step 9
entries — schema-validated tables (Finding/Step 6), competition/research boundary enforced
(Step 7), and the explanatory-model/Bias-Discovery table dependency (Stage 8/9 not yet started, so
this criterion is forward-looking and unverifiable until then, noted as such rather than claimed
met).

**Consequences**: Stage 6 (Feature Engineering) is formally closed. `docs/risk_register.md` has no
open Stage-6-authored risk blocking Stage 7 (R-010 is explicitly scoped to land before Stage 8, not
before Stage 7; R-011 is mitigated). Stage 7 (Reference Reconstruction Engine) can begin on a
confirmed foundation, inheriting: two already-built, already-tested building-assignment variants;
the hospital exclusion already implemented and verified; four dispatch-blind-reachability
candidates awaiting selection; and an empty `COMPETITION_ALLOWED_COLUMNS` ready for its calibration
to fill in with a reviewed, deliberate choice.

## Stage 6, Step 12 — Verification pass: adversarial code review complete, one real fix applied; pytest and clean-state regeneration pending Henry's own run

**Date**: 2026-09-17

**What was done**: per the guideline's own Step 12 (and `agent-skills:doubt-driven-development`'s
guidance that stakes this high — a competition-prize-critical foundation — warrant adversarial
review, not self-review), a fresh-context, five-axis code review (correctness, readability,
architecture, security, performance) was run via an independent subagent with no memory of this
project's prior conversation, against the actual Stage 6 code on disk: `src/geometry.py`,
`src/features.py`, `src/schemas.py`, `scripts/build_stage6_step3_ingredients.py`, and
`scripts/build_stage6_step6_features.py`. The review was explicitly briefed to hunt for siblings of
R-011's transport-filter bug — a documented invariant, filter, or exclusion the code's docstring
claims to apply but the executed code path does not enforce — rather than a generic pass.

**Result, round 1**: the reviewer initially reported a CRITICAL finding — `build_stage6_step6_features.py`
"does not exist on disk" — which was a staging mistake on my part (the file was never copied into
the review sandbox), not a real gap; the file exists and was already confirmed working end-to-end
against real data (this log's Steps 6-7 entry). Corrected by re-staging the file and sending it back
to the same reviewer for a completed pass.

**Result, round 2 (final)**: **APPROVE**, with the missing-file finding reversed once the real file
was reviewed. The reviewer traced `build_stage6_step6_features.py`'s `_GAP_TO_DEFINED_COL` mapping
against Step 3's actual output column names, column by column (all 7 gap columns correctly mapped,
no naming mismatches), confirmed the dispatch-blind-reachability inputs are fire/EMS only (schools
correctly excluded, matching `features.py`'s own docstring), and confirmed `validate_layer()` is
called before the parquet write, in the correct order. No repeat of R-011's failure class was found
in `build_stage6_step3_ingredients.py`: every documented filter (TIGER `MTFCC` allowlist, Overture
`class` allowlist, exact-match POI category matching) is confirmed actually applied in the executed
code, and the hospital exclusion was assessed as structurally more bug-resistant than an explicit
`NOT IN (...)` filter would have been — hospitals are simply never listed in
`POI_FACILITY_CATEGORY_MAP`, so the unfiltered establishments term is unaffected by construction,
by design rather than by a second filter that could drift out of sync.

**One real, previously-unguarded gap found and fixed**: no assertion anywhere confirmed
`GEOID` uniqueness in the tract polygons before they become the join target for every
`ST_Within`/`ST_Intersects` spatial join in `build_stage6_step3_ingredients.py`. A duplicate GEOID
(a future tract-boundary vintage change, or an ingestion artifact) would silently double-count
every building/POI matched against it — inflating raw counts with no crash and no visible symptom
until a gap value came out wrong. This is exactly the same class of failure as R-011 (a documented
assumption the code never actually checked), caught this time before it shipped rather than after.
Fixed by adding `assert tracts_gdf[TRACT_ID_COL].is_unique` immediately after `_register_tracts`,
before `tracts_gdf` is used to build `full_index` or trusted as the DuckDB join's join target.

**Two findings investigated and confirmed non-issues, not waved through on trust**: (1) whether
`assert_competition_only()` could be silently bypassed — confirmed it is correctly fail-closed in
isolation, but its enforcement point doesn't exist until Stage 7 wires it in, so its practical
effectiveness is unverified until then, not a Stage 6 defect; carried forward as a note for Stage 7
to wire it in at the single choke point where the scored dataframe is finalized, not as an
easy-to-forget manual call. (2) whether `source_provenance_vector`'s substring-matched
`osm_share`/`microsoft_share`/`google_share` could sum to more than 1 (the same substring-vs-exact-
match failure class the project already fixed once for POI categories) — confirmed, against the
real, fully-enumerated `sources[].dataset` value set (`docs/data_manifest.md` Section 4.5:
`OpenStreetMap`, `Microsoft ML Buildings`, `USGS Lidar`, `Esri Community Maps`,
`Google Open Buildings`, `TomTom`), that no real value matches two buckets — the `other_share`
clamp is unreachable dead-code safety margin against a hypothetical future dataset name, not a live
bug. A one-line comment was added at that clamp recording this, so a future reader doesn't mistake
it for load-bearing behavior today.

**Not yet done, deliberately left to Henry rather than claimed without evidence**: `pytest -q`
re-run and compared against Step 1's 471-passed/0-skipped baseline (expected to increase now, from
the geometry-primitive, schema-validation, and enforcement-gate self-checks — though these currently
live as `__main__` self-checks, not `pytest` files; whether that gap itself needs closing before
Stage 7 is a question for Henry, not decided unilaterally here), and a clean regeneration of all
four `data/processed/<region>-tract-features.parquet` files from a clean state (re-running Step 3
with the new GEOID-uniqueness assertion in place, then Step 6, for all four regions) followed by
re-validation against `TRACT_FEATURES_SCHEMA`. These require Henry's own machine and are pending his
confirmation before this step — and Stage 6 as a whole — is marked fully closed.

**Verification performed**: the code review was run adversarially, by an agent with no prior context
on this project, specifically briefed on this codebase's one demonstrated failure pattern; its
first-round false-positive was itself verified and corrected rather than accepted at face value; the
one real finding it surfaced was fixed and the fix's own reasoning was written directly into the
code as a comment, not left implicit.

**Consequences**: Stage 6's code is now adversarially reviewed and one real defensive gap is closed
before Stage 7 builds on top of it. Full closure of Step 12 (and therefore Stage 6) awaits Henry's
own `pytest -q` run and a clean four-region regeneration/re-validation with the new assertion in
place — this entry will be updated once that confirmation arrives, per this project's own "verify,
don't assume" discipline applied to itself.

### Step 12 (continued) — final verification confirmed, Stage 6 closed

All four regions regenerated end-to-end after the Step 12 code-review fixes (GEOID-uniqueness
assert, schema_catalog/DATA_DICTIONARY.md scoping) and confirmed clean:

- `pytest -q`: 471 passed, 1 warning, 0 skipped — exact match to pre-Step-8 baseline.
- `build_stage6_step3_ingredients` re-run individually for maricopa-az, northern-ca, and
  south-central-tx (eastern-ok already covered by the full pipeline run). south-central-tx failed
  three times with rotating network/DNS errors (AWS SDK network error, then two separate DuckDB
  DNS-resolution failures) before succeeding on retry — diagnosed as transient local network
  flakiness, not a code defect: the identical code path succeeded immediately for the other two
  regions in the same session, and three different error signatures at unrelated hostnames rules
  out a logic bug. No code change made for this — root cause never localized to the code.
- `build_stage6_step6_features` re-run for all four regions: schema validation PASS (100 columns)
  in every case.
- `verify_stage6_step9.py` run against the freshly regenerated data: all four checks (row counts,
  transport-undefined counts, water-dominated tracts, hospital-exclusion ratio) PASS for every
  region.
  - south-central-tx's row count (6010 vs. 6003 scored) is confirmed, not a defect: matches
    Section 4.23's documented 7-tract water-exclusion finding exactly, verified live against the
    real sample-submission GEOID list rather than assumed from prior documentation.
  - Hospital-exclusion ratio confirmed per-region: 5.43x-8.54x, consistent with the corrected
    figure in `docs/data_manifest.md` Section 4.4 and `docs/risk_register.md` R-004.

Stage 6 Step 12 is closed. All deliverables (src/geometry.py, src/features.py, four
tract-features.parquet tables, schema_catalog.csv/DATA_DICTIONARY.md extension,
feature_engineering_findings.md, risk register/decision log/README/blueprint updates) are
verified against real committed data and real local runs. Stage 6 is complete — 6 of 13 stages.
