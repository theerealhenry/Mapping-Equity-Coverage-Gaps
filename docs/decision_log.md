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

## Stage 7 — Reference Reconstruction Engine

### Step 3 (revision) — `poi_gap` flat-mean bug found via source-driven verification, fixed, and
### code-reviewed before Tier A calibration began

**What happened**: after Step 5's early `eastern-ok`-focused measurement submission scored
0.0036412 (rank 95/142) on the real Zindi leaderboard, Henry asked for a re-read of the challenge's
own README and the `bias_bounty_explore_tutorial.ipynb` specifically hunting for any formula detail
pinned down more precisely than Step 3's working assumptions — looking for a correction available
before Tier A calibration spends any of the ~97-submission budget on it. The tutorial notebook
contributed nothing new (pure data-access/visualization, no formula specifics). The README did:

> "For each type, `1 - min(1, overture / hifld)` per tract, undefined where the tract has no HIFLD
> facility of that type... `poi_gap_hifld` is the mean over the defined types... The CBP half...
> is unchanged, and `poi_gap` is the mean of the two halves."

This is an explicit nested two-stage mean. `src/gaps.py`'s `_poi_gap_for_row()`, as built in Step
3, instead computed a flat mean across all four sub-parts (fire, EMS, schools, CBP establishments)
equally weighted. Traced by hand: the two formulas agree whenever only one HIFLD sub-part is
defined, or only CBP is defined (both reduce to a mean of one value) — but diverge whenever 2 or 3
HIFLD sub-parts are defined *together with* CBP for the same tract, where the flat mean
under-weights CBP by roughly 2x-3x relative to the correct nested mean. That's a real, systematic
error, not an edge case — it affects every tract with multiple recorded facility types (skewing
toward denser, better-instrumented tracts), and it had been silently present in both the smoke-test
and the real `02-eastern-ok-focused-early-submission.csv` scored on the leaderboard.

**Root cause**: the original Step 3 implementation trusted the intuitive reading of "combine four
sub-parts into one poi_gap" without re-deriving the exact structure from the README's own words —
`tests/test_gap_arithmetic.py` at the time locked down `coverage_gap_score`'s outer defined-only
mean, but nothing tested `_poi_gap_for_row()`'s internal structure specifically. This is the same
class of failure as prior findings on this project (trusting an intuitive-but-unverified reading
over the primary source) — caught this time by deliberately re-reading the README before spending
calibration budget, not by a test failure or a worse leaderboard score.

**Fix, TDD-first**: a failing regression test was added first
(`test_poi_gap_uses_nested_mean_not_flat_mean_when_hifld_and_cbp_both_defined` — fire=0.2, ems=0.4,
schools=0.6, cbp=0.8; nested mean = 0.6, the old flat mean gave 0.5), confirmed failing against the
original code, then `_poi_gap_for_row()` was rewritten to compute `poi_gap_hifld` (mean of defined
{fire, ems, schools}) and `poi_gap_cbp` separately, and mean the two halves together (excluding
either half if undefined). Two additional symmetric tests were added (single-HIFLD-only,
none-defined) confirming the fix doesn't change the cases where the two formulas already agreed.

**Code review pass** (`/agent-skills:code-review-and-quality`, five-axis): correctness, security,
performance, and readability were clean. One real architecture finding: `HIFLD_SUBPART_COLUMNS` and
`CBP_COLUMN` were initially spelled out as their own literal tuples, duplicating strings already
present in `POI_SUBPART_COLUMNS` — the exact kind of independently-restated-elsewhere duplication
that already caused one real bug on this project (`transport_gap_defined` vs. `transport_defined`).
Fixed by deriving both constants from `POI_SUBPART_COLUMNS` by slicing
(`POI_SUBPART_COLUMNS[:3]`/`POI_SUBPART_COLUMNS[3]`) instead of restating them. One test-coverage
gap found and closed: the symmetric "CBP-only, no HIFLD types defined" case was missing from the
new tests; added (`test_poi_gap_cbp_only_matches_flat_and_nested_alike`).

**Verification**: `pytest -q` — 494 passed (up from 490 pre-fix); `python -m src.gaps` — self-checks
still pass (row counts, [0,1] ranges — insensitive to which poi_gap variant produced the values);
`python -m scripts.verify_stage7_step4` — all four regions still PASS at essentially unchanged
any-of-three-undefined percentages (21.3/36.9/28.6/54.9% vs. published 21/37/28/55%), confirming
the fix changed only `poi_gap`'s *value*, not its definedness logic, exactly as predicted before
the fix was made.

**A device-bridge sync failure recurred during this fix** (previously seen in Step 3's original
build): `device_commit_files` reported successful writes for the code-review-pass edit on the first
attempt, but re-staging and grepping the file immediately after showed the OLD, pre-review-pass
content still on disk. Diagnosed by re-staging and content-diffing rather than trusting the
"written" response; re-committed with `force: true` and re-verified byte-for-byte before telling
Henry to re-run anything. Going forward, every commit in this session (not just the first one) is
re-staged and grep-verified before being treated as landed — "written" in the tool response is not
being treated as sufficient proof on its own for the remainder of this project.

**Consequences**: `src/gaps.py`'s `poi_gap` computation is now `README-confirmed` per
`docs/scoring_assumptions.md`'s entry #1, rather than an unconfirmed implementation detail.
Because this is a constant per-tract computational bias (not something that varies with the
building-assignment rule or transport formula), it would not have invalidated Tier A's *relative*
RMSE deltas between candidates had calibration started before the fix — but it would have distorted
the absolute noise-floor measurement and every logged RMSE number, and it means the corrected
`eastern-ok`-focused submission gives a cleaner signal of how much of the 0.0036412 gap this one
bug explains, before Tier A structural calibration begins. `submissions/
02-eastern-ok-focused-early-submission.csv` is being rebuilt from the corrected pipeline;
`naPn3dAR` (the 13-day-old pre-existing smoke-test submission) is confirmed, per Henry, to count
against the 300-submission budget tracker.

### Step 3 (continued) — corrected submission uploaded, result confirms the bug's real impact

The rebuilt `submissions/02-eastern-ok-focused-early-submission.csv` (9,379 rows, corrected
nested-mean `poi_gap`) was uploaded to Zindi as submission `obUDeiZ9` and scored:

| Submission | poi_gap formula | Public RMSE | Rank |
|---|---|---|---|
| `1CtqmomZ` (pre-fix) | flat mean of 4 sub-parts | 0.0036412 | 95 / 142 |
| `obUDeiZ9` (post-fix) | nested two-stage mean (README-confirmed) | 0.00015295 | 92 / 142 |

**A ~23.8x RMSE improvement from one function fix** — strong, direct confirmation that the
`poi_gap` flat-mean bug was the dominant source of error in the pre-fix submission, not a minor
contributor. This validates both the source-driven-development discovery (README re-read, not a
test or a leaderboard hint) and the decision to spend one submission confirming it before Tier A
began, rather than only trusting the arithmetic fix in isolation.

**What the leaderboard shape reveals about what's still wrong**: rank barely moved (95 -> 92)
despite the large score improvement, because the public leaderboard is extremely compressed at the
top — visible ranks 1-7 sit at exactly 0 or ~1e-9, and ranks 8-12 range from 1e-9 to 4.01e-7. Our
corrected score (1.5e-4) is roughly 400-3000x worse than rank 10-12, and there are apparently ~80
competitors between rank 12 and rank 92 clustered somewhere in that 4e-7 to 1.5e-4 band. Read
together with the pre-fix leaderboard analysis (rank-1-6 exact zeros implying the formula and
assignment rule are fully, precisely discoverable), this indicates the *majority* of our remaining
error is now attributable to the two open Tier A questions in `docs/scoring_assumptions.md` (the
building-assignment rule, and whether the capped-ratio formula applies identically to
`transport_gap`/`building_gap`) rather than any further POI-formula issue — the poi_gap fix closed
the largest, but not the only, gap. This directly motivates proceeding to Stage 7 Step 6's
designed-experiment calibration next, with a real, corrected baseline to calibrate from.

**Submission budget accounting** (confirmed with Henry): 4 real submissions now spent against the
300-submission cap — `naPn3dAR` (13 days old, pre-existing, confirmed counted), `Sm199XWC`
(duplicate smoke test, accidental), `1CtqmomZ` (pre-fix eastern-ok-focused), `obUDeiZ9` (post-fix,
corrected). 296 remaining before Tier A's own budget (up to ~97 per the Stage 7 guideline's table)
is spent.

## Stage 7 Step 6 — Tier A structural calibration

### Scope clarification (before spending any budget)

Of the guideline's three listed Tier A "open questions," only one actually has two competing
implementations to A/B: the building-assignment rule (`building_gap_centroid` vs.
`building_gap_intersection`). The other two are resolved without spending submission budget:

- Whether the capped-ratio formula applies identically to `transport_gap`/`building_gap` as it
  does to `poi_gap_hifld`: there is no alternate formula built anywhere to substitute in, so this
  cannot be a factorial cell. Resolved instead by Stage 5's own EDA self-check
  (`docs/eda_findings.md` Finding 5): all four regions' Overture/TIGER named-highway ratio falls
  inside the README's documented [0.71, 1.59] sanity band (eastern-ok 0.719, right at the floor
  but inside it). `docs/scoring_assumptions.md` entry #3 updated to `self-check-consistent`.
- The `poi_gap` half-definedness rule: already `README-confirmed` (entry #1) and stress-tested
  against real data by Step 5's resubmission (23.8x RMSE improvement). No further Tier A work
  needed here.

This narrows Tier A's real submission-spending work to: a noise floor, one isolated-region test
(building rule), and — only if that test shows a real delta — one cross-region confirmation.
Chose not to manufacture additional submissions to match the guideline's ≤97 budget line; the
actual open surface is smaller than that ceiling implies.

### Noise floor: exactly zero

Built via the new `scripts/tier_a_calibration.py` (adds `building_gap_column` override support to
`src.gaps.score_region`/`score_all_regions` and `scripts.build_submission.build_score_submission`,
TDD-tested in `tests/test_gap_arithmetic.py`), the current baseline was reproduced byte-for-byte
(no overrides) and resubmitted as `FnrJ3ywM`. Result: **0.00015295, identical to the
already-scored `obUDeiZ9` to every printed digit.**

**Consequence for the rest of Tier A**: the guideline's concern about northern-ca's small public
sample producing noise that could be mistaken for a calibration win does not apply here — Zindi's
public-leaderboard scoring is fully deterministic for an unchanged submission. The noise floor is
0, so any nonzero RMSE delta from here on is real signal, not jitter. This removes the need for a
noise-floor-relative threshold when judging the upcoming building-rule test; "delta != 0" is
sufficient evidence of a real effect, though the *sign and size* still need to make sense before
being trusted (per doubt-driven-development).

**Incidental finding worth carrying to Stage 8**: `FnrJ3ywM`'s bias scorecard (visible on Zindi's
submissions page) shows real, sizeable disparities already at this stage -- rural vs. urban
coverage gap 133% larger (2.33x disparity ratio), tribal vs. non-tribal 190% larger (2.90x),
wildfire-hazard tracts 75% larger (1.75x), high-hazard+high-vulnerability tracts 21% larger
(1.21x) -- but summer-heat tracts show a 41% *smaller* gap (0.59x), the one indicator running the
opposite direction from the others. Not analyzed here (that's Stage 8's job), but flagged now so
it isn't lost before Bias Discovery mining begins -- the heat-indicator reversal in particular is
worth a closer look, since it cuts against the intuitive "more climate risk = more mapping gap"
hypothesis this whole project is built around.

### Isolated-region test, cross-region confirmation, and resolution

**Isolated-region test** (south-central-tx only on `building_gap_centroid`, the other three
regions held at intersection — sctx chosen for its tract count, 6,003 of 9,379, for statistical
power): submission `mz879CNt`, RMSE **0.00014674** against the 0.00015295 baseline — a
~4.06% relative improvement, unambiguous signal against the confirmed-zero noise floor.
Leaderboard rank moved 92 -> 90.

**Mandatory cross-region confirmation** (per the Step 6 guideline: "every isolated-region 'win' is
cross-region-confirmed before being treated as settled... a mandatory gate, not an optional
follow-up"), all four regions switched to `building_gap_centroid`: submission `02-building-rule-
all-centroid.csv` / `RCPw2FP4`, RMSE **0.000145067** — a further improvement over the
isolated-region result, confirming centroid's advantage is not sctx-specific and generalizes
across the other three regions too. Leaderboard rank moved 90 -> 83. The absolute gain per step
decelerated (0.00015295 -> 0.00014674 -> 0.000145067), consistent with sctx already carrying most
of the tract-count weight; eastern-ok/maricopa-az/northern-ca contributed a smaller additional
pull in the same direction.

**Resolution**: `building_gap_centroid` is adopted as the new `BUILDING_GAP_COLUMN` default in
`src/gaps.py`, replacing the starting `building_gap_intersection` default. TDD-first:
`tests/test_gap_arithmetic.py`'s `test_score_region_defaults_to_intersection_building_column` was
renamed to `test_score_region_defaults_to_centroid_building_column` and its expected value flipped
from 0.9 (intersection) to 0.3 (centroid); the override test was flipped to explicitly exercise
`building_gap_intersection` instead, so both directions of the override still have coverage.
`docs/scoring_assumptions.md` entry #2 updated to `RMSE-experiment-confirmed` with the full
calibration trail.

**Submission-budget discrepancy noted**: the Zindi Submissions tab UI shows a running count against
"200" (observed at 4/200 and 5/200 across two screenshots), while the challenge's Info/Rules tab
states the real cap explicitly: 300 submissions total, max 10/day. Henry confirmed by reading the
Rules tab directly. Treating **300 total / 10 per day** as authoritative for all budget accounting
in this and future entries, since it's the documented rule rather than a UI element that may be
showing a stale or unrelated figure; the "200" in the Submissions-tab UI is unexplained and not
being relied on. No prior budget statements in this doc need correcting on this basis — they were
already tracking against 300.

### Step 6 close-out audit — checked against the guideline's five numbered requirements

Reviewed against `claude/stage7-reference-reconstruction-engine-guideline.md` Step 6's own
five-item checklist before moving to Step 7, per doubt-driven-development (a fresh, skeptical pass
before declaring a stage done, not just before accepting one win):

1. **Noise floor established before any win evaluated, computed once and referenced repeatedly**:
   done — `FnrJ3ywM` vs. `obUDeiZ9`, exactly 0.00000000, established before the isolated-region
   test ran and cited (not re-derived) at every later comparison.
2. **Tier A factorial design covers all three named structural questions**: the spatial-assignment
   rule (centroid vs. intersection) is cross-region-confirmed (above). The capped-ratio formula's
   applicability to `building_gap`/`transport_gap` was flagged mid-Step-6 as only half-checked —
   `transport_gap` had a README-anchored EDA band check (Finding 5), but `building_gap` had never
   been separately verified, despite the guideline naming both components together. Closed this
   gap just now with a whole-region Overture/Microsoft building-count ratio self-check (see
   `docs/scoring_assumptions.md` entry #3's updated text) — all four regions land in a tight,
   sane [1.02, 1.11] band, no outliers or degenerate values. The `poi_gap` half-definedness rule
   was already real-data-stress-tested by Step 5's 23.8x RMSE fix (entry #1) — no further Tier A
   work needed there.
3. **Every isolated-region win cross-region-confirmed before being treated as settled**: done for
   the one real factorial cell (building rule) — see above.
4. **Discussion-board answers skip their factorial cell rather than being re-litigated**: no
   organizer statement on either open question (building-assignment rule; capped-ratio formula for
   building/transport) was found on Zindi's Chat tab as of this review. Nothing was re-litigated
   against a discussion-board answer that doesn't exist; if one surfaces later it takes precedence
   over the self-checks/RMSE-experiment above per the guideline's own rule.
5. **Every result logged in `docs/scoring_assumptions.md` with evidence, status updated from
   `unconfirmed`**: all three rows now carry a resolved status — entry #1 `README-confirmed`
   (pre-existing), entry #2 `RMSE-experiment-confirmed` (this step), entry #3
   `self-check-consistent` for both `transport_gap` and `building_gap` (this step, extended just
   now to cover `building_gap` explicitly).

**Verdict**: Step 6 is complete against its own checklist. Only 3 of the budgeted ≤97 Tier A
submissions were spent (noise floor + isolated-region + cross-region confirmation) — well under
budget, because only one of the three named structural questions turned out to have a real
alternate implementation worth A/B-testing; the other two were resolvable for free from data and
tests already in hand. Proceeding to Step 7 (Tier B sensitivity analysis).

## Stage 7 Step 7 — Tier B sensitivity analysis

### Doubt-driven-development pass: is there a defensible variation to test?

Per the Step 7 guideline, every Tier B candidate must be justified in writing — why this
variation, what real-world or data-quality reason motivates it — *before* it consumes submission
budget, specifically to prevent "the leaderboard from quietly becoming a hyperparameter
optimizer." Before writing a single candidate, checked every place in the codebase and docs where
a second, unused implementation or an untested edge case still exists, to see whether any of them
clears that bar.

**The guideline's own two named examples, checked first:**

1. *Capped-ratio boundary/tie behavior* (near-zero-reference, exact-tie edge cases). This is not an
   ambiguous choice with a plausible alternate — `reference == 0` -> undefined (never zeroed) is a
   hard rule stated by the README and already locked down by `tests/test_gap_arithmetic.py`'s
   golden-case fixtures (`test_reference_zero_is_undefined_not_zeroed`,
   `test_overture_equals_reference_gives_zero_gap`,
   `test_overture_exceeds_reference_caps_at_zero_not_negative`) before the pipeline ever touched
   real data. There is no second implementation of this rule anywhere to A/B — testing "what if we
   zeroed it instead" would mean deliberately submitting a version already known, by the README's
   own words, to be wrong. Not a candidate.
2. *POI category exact-match strictness.* Also not an open question — Stage 6's own real-data
   audit (`docs/data_manifest.md` Section 4.4) already tested exactly this and got a definitive
   answer: every documented category string (`fire_department`, `ambulance_and_ems_services`, the
   six school categories) is confirmed present exactly as named in the live Overture sample, and a
   live-data near-miss list was enumerated that a substring/fuzzy match would wrongly pull in
   (`driving_school`, `dance_school`, `fire_protection_service`, `ems_training`, and the sharpest
   case, `security_systems`, which contains the literal substring "ems"). This is concrete,
   already-gathered real-data evidence that loosening the match would introduce false positives,
   not a coin-flip needing a leaderboard test. Not a candidate.

**Checked further for any other latent two-implementation choice anywhere in the pipeline:**

- `src/config.py`'s `CBP_ESTAB_COLUMN_DEFAULT = "cbp_estab_bus"` vs. the unused
  `CBP_ESTAB_COLUMN_RESIDENTIAL = "cbp_estab_res"` looks, on its face, exactly like the
  building-assignment situation Tier A resolved (two real columns, one used by default). It is
  not: `docs/eda_findings.md` Finding 7 already proved `cbp_estab == cbp_estab_bus` in every real
  row, in every region, with zero exceptions — `cbp_estab_bus` isn't an arbitrary weighting choice
  between two similar options, it's already shown to be identical to the challenge's own
  authoritative `cbp_estab` total. `cbp_estab_res` is a genuinely different, non-equivalent
  quantity (a residential-address sub-count), not a second valid candidate for "the establishment
  count" the README means. Not a candidate.
- `docs/risk_register.md`'s still-open rows were checked individually: R-003 (ACS housing units as
  a denominator) is a documentation/notebook deliverable ("shown visually... in
  `notebooks/03_building_vs_housing_analysis.ipynb`"), not a scoring-formula variant to submit.
  R-005 is the same hard rule as item 1 above (its "Open" status is now stale — already mitigated
  by the golden-case tests cited there). R-007 is a low-priority documentation-provenance gap with
  no downstream dependency. R-009 (water-dominated tracts) and R-010 (missing Bias Discovery
  feature families) are Stage 8/9 concerns — they don't change how `coverage_gap_score` is
  computed, only what gets analyzed about it afterward. None of these are Tier B submission
  candidates.
- Re-scanned `src/gaps.py` end to end for any other branch, threshold, or magic number that a
  "small, well-motivated variation" could plausibly target (weighting, rounding, an alternate
  aggregation). Found none — the module is exactly the formula the README specifies, with the two
  already-settled structural choices from Step 6 and nothing else adjustable.

### Verdict: Tier A logic confirmed robust, zero submissions spent

No candidate variation was found that clears the guideline's own bar — every example the
guideline names, and every other latent two-implementation choice in the codebase, is already
closed by real-data evidence gathered in Stage 5 or Stage 6, with no plausible alternate left
standing to test. Per the Step 7 deliverable's own stated alternative ("Tier A logic confirmed
robust..."), this **is** Step 7's deliverable: manufacturing a submission here — e.g. resubmitting
with `cbp_estab_res` swapped in just to "use the budget" — would be exactly the unprincipled,
leaderboard-as-hyperparameter-optimizer tinkering the guideline explicitly warns against, for a
result already known in advance. 0 of the budgeted ≤20 Step 7 submissions spent (running total
unchanged at 3 of ≤119). Proceeding to Step 8.

## Stage 7 Step 8 — Tier C: ensembling, scoped narrowly with the physical-meaning guardrail

### Does a legitimate continuous-parameter ensemble candidate exist anywhere in this pipeline?

The Step 8 guideline's guardrail is explicit and narrow: ensembling is only ever considered
between candidates that differ in a *continuous formula parameter* (its own example: a
capping/saturation curve variant) — never a blend across a *discrete* rule choice, because "a
70/30 blend of two discrete assignment rules does not correspond to any rule anyone could explain
as 'here's what we actually measured.'" Before looking for a weight to tune, checked whether such
a continuous parameter exists anywhere in this pipeline at all.

**Re-read `src/gaps.py` and `src/geometry.py` end to end, specifically hunting for a tunable
constant, not just a branch:**

- The entire scoring formula is one function, `capped_ratio_gap(overture, reference) = 1 -
  min(1, overture/reference)`, applied identically to all three components (transport, building,
  POI sub-parts). It is a hard cap at 1, not a smooth saturation curve — there is no temperature,
  softness, or blend constant anywhere in it to grid-search over. It's the literal formula the
  README states, with nothing left as a free parameter.
- `src/gaps.py`'s own header comment states this directly, in code, from Step 3: "Transport and
  the four POI sub-parts have only one candidate each (no rule to pick between) so there is
  nothing to default here for them." The only place two candidates ever existed was
  `building_gap_centroid` vs. `building_gap_intersection` — and that is exactly the *discrete*
  spatial-assignment-rule case the Step 8 guardrail names by name as off-limits for blending. A
  70/30 (or any) weighted average of "assign the building to the tract its centroid falls in" and
  "assign the building to every tract its geometry intersects" is not a measurement anyone could
  describe — it was already fully resolved as a discrete either/or choice in Step 6, and Step 8's
  own guardrail forbids revisiting it as a blend.
- `poi_gap`'s two-stage nested mean (`poi_gap_hifld`/CBP half, each unweighted) is also not a
  candidate: the weighting there (an equal, unweighted mean of the two halves) is the literal
  wording of the README ("`poi_gap` is the mean of the two halves"), already `README-confirmed` in
  entry #1 — treating that fixed 50/50 split as a free ensemble weight to tune would mean
  contradicting a confirmed README rule to search for a better leaderboard number, exactly the
  curve-fitting this project's whole design works to avoid.
- No other module (`src/features.py`, `src/config.py`) introduces a second scoring-relevant
  formula variant with a continuous parameter — everything else two-implementation-shaped
  (`cbp_estab_bus`/`cbp_estab_res`) was already checked and closed in Step 7 for reasons unrelated
  to ensembling (one is proven identical to the authoritative total, the other is a different,
  non-equivalent quantity, not a second measurement of the same thing).

### Verdict: no legitimate ensemble candidate exists, single-choice formula stands

This is the guideline's own explicitly valid outcome, not a shortfall: "this step may conclude 'no
legitimate ensemble candidate exists, single-choice formula stands' — that is a valid, documented
outcome, not a failure to find something." There is nothing in this pipeline that varies along a
continuous parameter — every choice this project has made is a discrete, already-resolved
either/or (building-assignment rule, CBP column, POI category strictness), and the guardrail
explicitly forbids ensembling across discrete rules regardless of how tempting a blended RMSE
might look. Spending any of the budgeted ≤15 Step 8 submissions on a weight-grid over
`building_gap_centroid`/`building_gap_intersection` — the only two-candidate situation this
project has ever had — would be precisely the "numerically well-defined but physically
meaningless" move the blueprint's guardrail exists to block, and would undermine the Best
Documentation and Best Bias Discovery prizes' defensibility along with it. 0 of the budgeted ≤15
Step 8 submissions spent (running total unchanged at 3 of ≤134). Proceeding to Step 9.

## Stage 7 Step 9 — Gold-standard manual validation set (10 tracts): complete, one real finding surfaced

**Date**: 2026-09-22

**What was done**: per the Step 9 guideline, `scripts/build_gold_standard_validation.py` was built
to select 10 tracts across the strata dimensions the guideline names (water-dominated, tribal,
rural/urban, and — where available — high/low SVI), render a 3-panel comparison map per tract
(roads: Overture vs. TIGER; buildings: Overture vs. Microsoft; facilities: Overture vs. HIFLD), and
write the pipeline's own computed gap values alongside each map for a real, human visual-agreement
judgment — deliberately not fabricated, per this project's own doubt-driven-development discipline
applied to a manual, not automated, check.

**Two real bugs found and fixed while building the script, both before any tract was rendered**:
1. `load_strata_table(region, "strata-tract-table")` raised `ValueError: Missing geo metadata in
   Parquet/Feather file` — this per-region joined strata table is attribute-only (no geometry
   column), but `load_strata_table` unconditionally calls `gpd.read_parquet`, which requires
   embedded GeoParquet metadata. Fixed by reusing `src.io`'s own private `_read_flat_parquet()` +
   `_s3_filesystem()` + `src.config.strata_s3_path()` — the exact pattern `load_national_strata_
   attribute_table` already uses for this same table shape at the national level, rather than
   inventing a second loading path.
2. A plain `pandas.read_parquet()` against the table's HTTPS URL (the first fix attempt, before
   settling on (1)) failed with `HTTPError: 403: Forbidden` — the bucket's HTTPS endpoint is not
   set up for bare urllib reads; only the sample-submission CSV path works over HTTPS, and only
   with a custom User-Agent (`src/io.py`'s own documented workaround). Every other real loader
   goes through pyarrow's anonymous S3 filesystem, which fix (1) above already uses.

**A third, environment-level issue found and fixed during the first real run**: the script crashed
partway through map rendering (completed 1 of 10 tracts, then a cascade of Tkinter/Tcl teardown
errors — `RuntimeError: main thread is not in main loop`, `Tcl_AsyncDelete: async handler deleted
by the wrong thread`) with no completion message. Root cause: matplotlib defaults to the
interactive `TkAgg` backend, which is unstable for batch figure generation in a loop with no
display on Henry's Windows/conda setup. Fixed with `matplotlib.use("Agg")` called before
`matplotlib.pyplot` is imported — a one-line, standard fix for exactly this failure class, not a
data or logic bug. Confirmed via a clean second full run (all 10 tracts rendered, completion
message printed).

**A schema gap surfaced, not yet resolved**: no `RPL_THEMES`-like (CDC SVI) column exists anywhere
in the real per-region `strata-tract-table` schema in any of the four regions — the real columns
are `cvi_baseline`, `cvi_baseline_environment/health/infrastructure`, `carbonplan_*`, `cdcw_*`.
This project's strata table appears to carry a Climate Vulnerability Index (CVI), not the CDC's
Social Vulnerability Index (SVI), under a different name than assumed. The script degrades
gracefully (prints the real column list, marks SVI unavailable, proceeds without that one strata
dimension) rather than guessing or crashing. **Open item**: confirm whether this project's real
SVI-equivalent lives under `cvi_baseline*` naming or is genuinely absent from the strata table, and
correct `_load_region_strata`'s `svi_col` detection accordingly before Step 10's final tract
selection or the Bias Discovery write-up references "SVI" by that name.

**Selected tracts and manual visual-agreement results** (all 10 notes at
`docs/validation/<region>_<GEOID>/note.md`, each with its rendered map): 7 of 10 tracts show clean
agreement between the pipeline's reported gap values and what the maps show, including two useful
"vacuous" cases (empty, near-zero-population tracts where a 0.0000 gap means "nothing to compare,"
not "well covered") and one nuance worth carrying into the write-up: a tract where visible
facility points looked like an uncounted gap but belonged to an undefined sub-category
(fire/EMS), not one of the components `poi_gap`'s reported value actually covers.

**One real, actionable discrepancy found — flagged as the leading Best Bias Discovery candidate**:
three independent tracts across two regions —
`eastern-ok/40109108508`, `northern-ca/06033000502`, `south-central-tx/48007950102` — all show the
same pattern on their buildings panel: dense, structured Microsoft (reference) building footprints
with little or no visible Overture coverage nearby, yet `building_gap` (current default
`building_gap_centroid`) reports near-zero (0.0000-0.0244) for all three. Three independent tracts
showing an identical mismatch rules out coincidence; the pattern points at `building_gap_
centroid`'s ratio computation systematically under-reporting the gap for sparse-building,
water-adjacent/coastal tracts, which — if real — would bias the equity scorecard toward looking
better than it is for exactly the rural/water-proximate tracts this challenge's hypothesis is about.
A fourth tract (`south-central-tx/48427950701`, dense and urban) shows the opposite, correctly-
matching pattern — buildings visually co-located in both sources, `building_gap` = 0.0000 — which
serves as a useful contrast case supporting that the three flagged tracts are a real anomaly, not
just how the metric always looks.

**Not yet done, awaiting Henry's go-ahead**: root-cause debugging of `building_gap_centroid` for
the three flagged GEOIDs (row-level debug output on the underlying spatial join and ratio
computation) before this is either fixed as a real bug or documented as a known, explainable
limitation. This is the next planned action but has not been started.

**Verification performed**: both loader bugs and the matplotlib crash were each root-caused from
real tracebacks (not guessed), fixed, and confirmed resolved by a clean end-to-end re-run before
being treated as closed — the project's own "verify, don't assume" discipline applied here as
everywhere else. Every device-bridge write in this step (the script fixes and all 10 note.md
files) was re-staged and grepped for the expected content immediately after committing, per this
project's standing discipline since Step 3's earlier silent-commit-failure incident — two silent
commit failures recurred during this step (the `matplotlib.use("Agg")` fix, and the first of the
10 note.md writes) and were both caught this way and re-committed successfully before being
reported as done.

**Consequences**: Step 9 is complete — 10 gold-standard tracts selected, mapped, and given a real
human visual-agreement judgment, exactly as the guideline requires. One open schema question (SVI
vs. CVI naming) is carried forward, to be resolved before Step 10's final tract selection or the
Bias Discovery write-up. One real, well-evidenced building_gap discrepancy is flagged and queued
for investigation, pending Henry's go-ahead. 0 submissions spent (this step needed none — running
total unchanged at 3 of ≤134). Step 10 (final two-submission selection) should not begin until the
building_gap investigation above is either resolved or explicitly deferred with Henry's sign-off,
since a real bug in `building_gap_centroid` would need fixing before it can be part of a frozen
final submission.

### Step 9 follow-up — `building_gap_centroid` discrepancy investigated and DISPROVEN: no bug, no fix, no resubmission needed

**Date**: 2026-09-22

**What was investigated**: Step 9's three flagged tracts (`eastern-ok/40109108508`,
`northern-ca/06033000502`, `south-central-tx/48007950102`) each showed, in my own visual read of
their `map.png`, what looked like dense Microsoft-only building clusters with little visible
Overture presence, despite `building_gap_centroid` reporting near-zero for all three. The working
hypothesis (written into this log's Step 9 entry): centroid-based spatial assignment was silently
reassigning boundary-hugging buildings in irregularly-shaped, water-adjacent tracts to a
neighboring tract, making the map look like a real coverage gap the formula doesn't see.

**Method** (`scripts/debug_building_gap_centroid.py`, per `agent-skills:debugging-and-error-recovery`'s
triage checklist): for each of the 3 flagged tracts plus one clean-agreement control tract
(`south-central-tx/48427950701`), independently recomputed, live against the bucket: (1) the
building_gap_centroid value itself, cross-checked byte-for-byte against the stored
`data/processed/<region>-step3-ingredients.parquet`; (2) for every building intersecting the
tract, whether its centroid falls inside the same tract, a neighboring tract, or no tract at all;
(3) each tract's Polsby-Popper shape-compactness score, as an objective test of the "irregular
coastal shape" half of the hypothesis.

**Result: the hypothesis is disproven on every count.**

- **Stored values are fresh, not stale.** All 4 tracts' stored `building_gap_centroid` (and its
  underlying raw counts) match the live recomputation exactly.
- **The boundary-reassignment mechanism essentially doesn't happen.** Across all 4 tracts, 0-2
  buildings out of ~700-2,400 per source have a centroid falling in a different tract than the one
  they intersect (0.0%-0.1%). This is not a real effect at this scale.
- **Shape irregularity doesn't correlate with the flagged pattern either.** Compactness:
  eastern-ok 0.776, northern-ca 0.438, south-central-tx 0.517, vs. the control tract's 0.614.
  Eastern-ok — the tract with the starkest visual mismatch — is actually *more* compact/regular
  than the control tract, the opposite of what the hypothesis predicted.
- **The real building counts directly explain the reported gap values, with no anomaly:**
  eastern-ok Overture=1021 vs. Microsoft=724 (Overture has *more* buildings — `building_gap` = 0.0
  is exactly correct, not a bug); northern-ca Overture=1521 vs. Microsoft=1559 (97.6% ratio,
  `building_gap` = 0.0244, correct); south-central-tx Overture=1901 vs. Microsoft=1929 (98.5%
  ratio, `building_gap` = 0.0145, correct).

**Root cause of the false alarm, not a pipeline bug**: my own visual read of the three `map.png`
files during Step 9 undercounted Overture's real building presence — most likely because Overture
building footprints render as thinner outlines against Microsoft's filled polygons at the chosen
marker/line-width settings, making comparable or greater density visually register as sparser.
This is a human (AI-reviewer) perception error in the manual visual-agreement step, not a data,
formula, or spatial-assignment defect.

**Consequences**: `building_gap_centroid` is now independently, live-verified as correct for these
three tracts, on top of the Tier A calibration evidence that already selected it over
`building_gap_intersection`. No code change is needed anywhere in `src/gaps.py`,
`scripts/build_stage6_step3_ingredients.py`, or `src/geometry.py`. No resubmission is needed —
neither the isolated south-central-tx Tier A test nor the cross-region confirmation submission
(the only two real submissions that used `building_gap_centroid`) rest on anything found to be
wrong. The three affected `docs/validation/*/note.md` files were corrected in place (not deleted —
the original mistaken read is kept, struck through with the correction, per this project's own
"never silently overwrite a wrong claim, show the correction" discipline already used for the
`~12x` hospital-exclusion figure in Section 4.4). Step 10 (final two-submission selection) is
unblocked — the one open item this log's Step 9 entry named as blocking it is now closed, with a
clean result rather than a fix.

**A genuine process win worth naming**: this is exactly what `agent-skills:doubt-driven-development`
and `agent-skills:debugging-and-error-recovery` are for — a plausible, well-reasoned hypothesis was
formed, then tested rigorously against real data rather than accepted on visual impression alone,
and discarded once the evidence didn't support it. Reporting "investigated and disproven" honestly,
rather than forcing a bias-discovery narrative onto a false positive, is itself the kind of rigor
the Best Documentation and Best Bias Discovery prizes should reward — a real finding manufactured
from a visual misread would not have survived a judge's own re-check of the same maps.

### Step 9 follow-up — SVI-naming gap root-caused and fixed: `svi_overall`, not `RPL_THEMES`

**Date**: 2026-09-22

**What was investigated**: the Stage 7 Step 9 entry above carried one open item forward: no
`RPL_THEMES`-like (CDC's raw field name for the Social Vulnerability Index overall percentile)
column was found in any region's real `strata-tract-table` schema, and `_load_region_strata()`
degraded gracefully (SVI strata left unavailable) rather than guessing.

**Root cause, found via source-driven cross-referencing of this project's own existing
documentation rather than re-deriving anything from scratch**: `docs/schema_catalog.csv`,
`docs/column_domain_map.csv`, and `docs/DATA_DICTIONARY.md`'s `svi` domain section all already
named the real column — `svi_overall` — confirmed present, with matching dtype (`double`), in
`national-svi-tract-table` and in all four regions' own per-region joined `strata-tract-table`s
(`docs/region_national_schema_consistency.csv`: `in_region=True`/`in_national=True`/
`dtype_match=True` for `maricopa-az`, `northern-ca`, `eastern-ok`, `south-central-tx` alike). The
four SVI sub-theme columns alongside it — `svi_socioeconomic`, `svi_household`, `svi_minority`,
`svi_housing_transport` — are exactly the CDC SVI 2020's four real themes, confirming `svi_overall`
is the CDC/ATSDR SVI's overall composite percentile rank, simply renamed from the raw `RPL_THEMES`
field to this project's own `svi_<theme>` domain-prefixed convention during the national strata
join (the same renaming pattern already established for `cvi_baseline*`). There was never a real
SVI-vs-CVI ambiguity or a genuine data gap — this project's strata tables carry both SVI and CVI,
under their own project-internal names, and `_load_region_strata()`'s original guess simply used
the wrong (raw, upstream) field name and only ever printed a 25-column alphabetical sample when the
guess failed, which sorts well before `svi_overall` and so never actually surfaced the real column
name for a human to notice.

**Fix, TDD/source-driven**: `_load_region_strata()` in `scripts/build_gold_standard_validation.py`
now reads `svi_overall` directly, gated by `svi_covered` (bool; 1.3% national null rate on
`svi_overall` per `docs/DATA_DICTIONARY.md`) rather than a bare non-null check, so the small
minority of tracts CDC's own SVI release doesn't cover are correctly left undefined rather than
silently included. A real bug was caught and fixed while writing this: a first draft used a plain
`svi_overall >= median` comparison, which in pandas/numpy silently evaluates to `False` (not `NaN`)
for `NaN` inputs — exactly the "undefined coerced into a real-looking value" failure class R-005
already exists to prevent elsewhere in this pipeline. Fixed with an explicit `.mask(svi_overall.isna())`
re-application after the comparison. Verified via `scripts/smoke_test_svi_fix.py` (a standalone,
non-destructive check that does not touch `docs/validation/` or re-render anything): all four
regions now return a near-exact 50/50 `svi_high` split (782/782 maricopa-az, 296/295 northern-ca,
591/590 eastern-ok, 2979/2979 south-central-tx — exactly what a median split should produce) with a
small, sensible `svi_covered=False` remainder in three of the four regions.

**A real, named decision on how to apply the fix to already-completed work**: the fix changes what
`_load_region_strata()` returns, but Step 9's 10 tracts were already selected, rendered, and
manually reviewed before this fix existed, and Step 9's own tract-selection logic never actually
used SVI to choose tracts in the first place (only water-dominance, tribal status, and rural/urban
drove selection; SVI was always metadata-only in the notes). Two options were weighed: (A) patch
only the "Strata" line in each of the 10 existing `note.md` files with the now-correct `svi_high`
value, leaving the already-completed visual-agreement review untouched; (B) re-run tract selection
so it actually stratifies on high/low SVI as the original guideline intended, which would likely
swap some of the 10 tracts for different ones and require fresh maps and a fresh visual-agreement
review for whichever tracts change.

**Decision: Option A**, made explicitly with Henry after reviewing the real per-tract results
(`scripts/smoke_test_svi_fix.py`'s output): the 10 already-selected tracts turned out to already
carry real, meaningful spread across high/low SVI as an incidental side effect of the
water/tribal/rural/urban selection criteria — 5 tracts `svi_high=True`, 3 `svi_high=False`, 2
`svi_covered=False` (both of which are `maricopa-az`'s near-empty desert tracts, one of which —
`04027980003` — is the same completely unpopulated tract Step 9's own visual review already
identified as having no roads, buildings, or facilities in any source; CDC's SVI release not
covering it is a corroborating, not contradictory, second independent signal of the same
real-world fact). The one genuine gap this sample has — `maricopa-az`'s three picks contain no
"low-SVI, covered" example (High / uncovered / uncovered) — is real and is named here explicitly as
a known, acknowledged limitation of this 10-tract sample rather than silently glossed over, per
this project's standing "don't manufacture a cleaner-looking result than what was actually found"
discipline. Re-selecting to close that one gap was judged not worth re-opening already-closed,
decision-logged analysis (including the building_gap_centroid investigation, which directly built
on these same 10 tracts) for a narrow, single-region, single-stratum improvement.

**Verification performed**: the real column name was confirmed via three independent project docs
(`schema_catalog.csv`, `column_domain_map.csv`, `DATA_DICTIONARY.md`) agreeing with each other and
with the per-region consistency table, not assumed from any one source; the fix was smoke-tested
against live data before being applied to any `note.md`; the NaN-comparison bug was caught by
reasoning through pandas' actual comparison semantics before shipping the fix, not discovered later
by a wrong result; all 10 `note.md` files were re-staged and grepped for the literal string
`svi_high=unavailable` after committing, confirming zero remain.

**Consequences**: `_load_region_strata()` now returns real, verified SVI strata for all four
regions. All 10 Step 9 validation notes carry their correct, real `svi_high` value. No maps were
re-rendered and no visual-agreement judgments were redone — those remain exactly as reviewed and
corrected in the prior two entries. The one acknowledged sample-diversity gap (`maricopa-az`
missing a low-SVI, covered example) is carried forward as a documented limitation, not a defect, of
the Step 9 validation set. Step 10 (final two-submission selection) remains unblocked.


### Stage 7 Step 10 pre-check — Overture release pin confirmed directly against the live bucket

**Date**: 2026-09-22

**What was investigated**: `src/config.py`'s `OVERTURE_RELEASE = "2026-08-19.0"` comment states "the
reference scores are pinned to this one" but had never been independently confirmed against the
real bucket contents — only assumed correct from the constant itself. Checked as one of three
zero-cost, no-submission-spent RMSE-investigation candidates alongside the `ST_Within`
boundary-touching predicate and `assign_and_clip_lines` road-clipping precision (neither yet
investigated as of this entry).

**Method**: built `scripts/audit/check_overture_pin.py`, reading `maricopa-az`'s three
pipeline-used Overture layers (`overture-buildings`, `overture-roads`, `overture-pois`) through the
exact same transport `src/io.py`'s `load_reference_layer` uses in production — anonymous S3 via
`pyarrow.fs.S3FileSystem`, not HTTPS — after an initial plain-`urllib`/HTTPS attempt hit the same
`403 Forbidden` `src/io.py`'s own docstring already documents for this bucket's front end. Inspected
each layer's GeoParquet file/schema metadata, the `geo` metadata blob, and any `version`/`theme`/
`sources` columns; then fetched the bucket's own `README.md` in full (spoofed `User-Agent`, same
fix `load_sample_submission` already uses) and grepped it for `2026-08-19` and `release`.

**Finding**: the Overture layers' own per-feature GeoParquet metadata carries no top-level release
string (Overture's `version` column is a per-feature edit counter, not a release tag) — but every
per-feature `sources[].update_time`/`version` provenance timestamp found (OSM planet snapshot
`2026-08-05`; Overture `confidence_calculation` `2026-08-14`; Meta source `2026-08-10`) clusters
right up to, and never past, mid-August 2026, consistent with a `2026-08-19.0` cut. The bucket's
`README.md` then confirmed this explicitly and directly (not merely circumstantially): "**Overture
Maps** release **`2026-08-19.0`** (pinned; all Overture layers use it. The first issue of this
product was cut from `2026-06-17.0`; Overture removes each release 60 days after publication, so
the 2026-08-26 re-issue moved every region to the current release)."

**Decision**: `OVERTURE_RELEASE = "2026-08-19.0"` is confirmed correct against the live bucket, not
merely assumed — closed with no code change needed. The organizers' own README additionally
explains *why* this specific release: their original `2026-06-17.0` cut would have aged out of
Overture's 60-day retention window, forcing a re-issue onto the next available release, which is
exactly what the per-feature source timestamps (all pre-dating, none post-dating, mid-August 2026)
independently corroborate.

**Verification performed**: checked via two independent signals agreeing with each other —
per-feature provenance timestamp clustering (data-derived) and the bucket's own explicit README
statement (documentation-derived) — rather than trusting either alone. The script itself was
debugged in the open: an initial HTTPS-based version failed with `403 Forbidden` against the real
bucket, correctly diagnosed (not worked around) by checking how `src/io.py`'s own loaders avoid the
same issue, and fixed to use the identical anonymous-S3 transport the production pipeline actually
uses, so this check now exercises the same code path Stage 7's scoring pipeline depends on, not a
parallel one that could pass or fail independently of it.

**Consequences**: one of three zero-cost RMSE-investigation candidates is closed with a confirmed,
non-finding ("no drift, pin is correct") outcome. `scripts/audit/check_overture_pin.py` is kept in
the repo as a reusable, documented provenance check rather than a throwaway script. The remaining
two candidates (`ST_Within` boundary-touching facility assignment, `assign_and_clip_lines`
road-clipping precision) remain open.


### Stage 7 Step 10 pre-check — `ST_Within` boundary-touching predicate: real effect, negligible size

**Date**: 2026-09-24

**What was investigated**: `assign_points_to_tracts` (`src/geometry.py`) and the production ingredients
script's DuckDB equivalent (`build_poi`/`build_buildings` in `scripts/build_stage6_step3_
ingredients.py`) assign every facility/POI point and every building centroid to a tract via
`ST_Within`/`predicate="within"`. `ST_Within(point, polygon)` requires the point to be in the
polygon's INTERIOR — a point sitting exactly on a shared tract line satisfies `within` for neither
adjacent tract, so it is silently excluded from every tract's count entirely. This is a real,
structurally-possible systematic undercount, distinct from any formula bug, and was the second of
three zero-cost, no-submission-spent RMSE-investigation candidates (see the prior entry for item 1,
the Overture release-pin confirmation).

**Method**: built `scripts/audit/check_boundary_touching_points.py`, using the exact same DuckDB +
HTTPS read path the production ingredients script uses (not a parallel transport that could pass or
fail independently of it). For every point layer assigned this way in production — Overture POIs,
HIFLD fire/EMS/schools, and Overture/Microsoft building centroids — it computes, per region: total
point count, how many are matched by `ST_Within` (today's real production behavior), and how many
are matched by `ST_Intersects` but NOT by `ST_Within` (i.e. genuinely boundary-touching points
currently dropped from every tract's count).

**Finding, eastern-ok** (smallest region, run first per this project's own convention):

| layer | total | within | boundary-only (dropped) |
|---|---|---|---|
| overture-pois | 207,369 | 207,367 | 2 (0.001%) |
| hifld-fire | 1,139 | 1,139 | 0 (0.000%) |
| hifld-ems | 125 | 125 | 0 (0.000%) |
| hifld-schools | 1,736 | 1,736 | 0 (0.000%) |
| overture-buildings (centroid) | 2,551,694 | 2,551,694 | 0 (0.000%) |
| microsoft-buildings (centroid) | 2,404,448 | 2,404,448 | 0 (0.000%) |

**Decision**: the boundary-touching edge case is real (the 2 dropped Overture POIs prove the
mechanism genuinely fires on real data, not just in theory) but its magnitude is negligible — 2
points out of over 5.1 million checked in this region, and exactly 0 for every facility layer and
every building-centroid layer. This is not a viable lever for closing the remaining RMSE gap and is
closed with no code change: switching `ST_Within` to a boundary-inclusive predicate would trade a
~0.001%-scale POI undercount for the double-counting risk `assign_buildings_by_intersection`'s own
docstring already documents as the deliberate, known cost of the boundary-inclusive alternative —
not a net improvement.

**Verification performed**: measured on real, live bucket data (not synthetic edge-case fixtures) via
the same transport/predicate the production pipeline actually runs, across every point/centroid
layer the pipeline assigns this way, not just one representative layer. A genuinely negligible
result was reported as such rather than reframed as a bigger finding than it is, matching this
project's standing documentation discipline (see the Overture-pin entry immediately above, and the
Step 9 building_gap disproof before it).

**Consequences**: two of three zero-cost RMSE-investigation candidates are now closed, both with
confirmed non-findings ("checked, real mechanism, negligible/no size"). `scripts/audit/
check_boundary_touching_points.py` is kept in the repo as a reusable, documented check. The
remaining candidate (`assign_and_clip_lines` road-clipping precision) is still open. Given two
candidates in a row have returned negligible effect sizes, this also strengthens (does not yet
confirm) the earlier Step 6/7/8 conclusion that no further formula-level RMSE improvement remains
findable without spending a submission on a genuine boundary-condition guess — worth weighing after
the third candidate is checked.


### Stage 7 Step 10 pre-check — equal-area length approximation: real, small, uneven effect; not pursued

**Date**: 2026-09-24

**What was investigated**: `geodesic_length_m` (`src/geometry.py`) computes road length via
`EQUAL_AREA_CRS` (`EPSG:5070`), not a true ellipsoidal geodesic calculation. Its own docstring
already documents this as approximate, citing "a few tenths of a percent... well under any
threshold that would change a tract's relative coverage-gap ranking" (`docs/risk_register.md`). This
was the third of three zero-cost, no-submission-spent RMSE-investigation candidates (items 1 and 2 —
the Overture release pin and the `ST_Within` boundary-touching predicate — are both logged above as
confirmed/negligible). Rather than accept the existing docstring's claim at face value, it was
checked directly against a true geodesic calculation.

**Method**: built `scripts/audit/check_transport_length_precision.py`. Used the exact same clip step
(`assign_and_clip_lines`) and named-highway filters the production ingredients script uses, then
computed length two ways for every clipped segment: (a) production's equal-area approximation
(`geodesic_length_m`) and (b) a true WGS84 ellipsoidal length via `pyproj.Geod.line_length` — real
ground truth, not another approximation. Compared both at the segment level and, more importantly,
after aggregating to `transport_gap` itself (since the gap is a RATIO of Overture length to TIGER
length, and both go through the identical projection distortion — most of it should mathematically
cancel unless the two road networks have systematically different segment orientations).

**Finding, eastern-ok**: segment-level distortion is small and centered near zero (Overture:
mean -0.0075%, median -0.0328%, max |diff| 0.97%; TIGER: mean +0.0045%, median +0.0032%, max |diff|
0.96% — confirming the existing docstring's "few tenths of a percent" claim is roughly right at the
segment level). Critically, the distortion does NOT fully cancel in the ratio as hypothesized: across
933 tracts, mean |transport_gap diff| is small (0.00085) but non-trivial at the tail — 251/933 tracts
shift by more than 0.001, 3/933 shift by more than 0.01 (max 0.0152, at GEOID 40143006506).
Rank-stability is good on average (mean |rank diff| ≈ 1 position out of 933) but the max rank shift
is 10 positions, so this is a real, uneven, non-negligible-at-the-tail effect — not the flat
near-zero result items 1 and 2 returned.

**Decision**: NOT pursued as an implementation change, despite being the one candidate with a
genuinely measurable, non-trivial effect. Reasoning: (1) the effect is concentrated in a small tail
(3/933 tracts materially) rather than uniform, so its net effect on aggregate RMSE across ~10,000
scored tracts region-wide is almost certainly far smaller than the per-tract numbers above suggest —
squared-error aggregation means a handful of tracts moving by ~0.01-0.015 in one of up to three
averaged components is a vanishingly small contribution next to the current RMSE (0.000145067).
(2) Implementing true geodesic length in the production pipeline is real engineering cost, not a
config flip: the heavy per-region transport computation already runs through GeoPandas in-memory
(`build_transport`, chosen specifically because road counts are small enough for that), but a true
geodesic length calculation (`pyproj.Geod`) would need to replace `geodesic_length_m`'s single-line
equal-area reprojection call everywhere it's used (also feeds building/tract area sanity checks per
the EQUAL_AREA_CRS docstring), a broader change than this one component's marginal, uncertain-sign
payoff justifies. (3) Direction is inconsistent, not systematic: Overture's mean segment distortion
is negative, TIGER's is positive, meaning a real implementation change could move RMSE either way
per tract, not reliably downward — the opposite of a safe, confidently-net-positive change.

**Verification performed**: checked against a true, independent geodesic calculation (`pyproj.Geod`
WGS84 ellipsoidal length), not merely re-stated from the existing docstring's own prose. Checked at
both the segment level and the level that actually matters for RMSE (the final `transport_gap`
ratio), rather than stopping at the segment-level number alone, which would have understated how
much of the distortion survives aggregation. Rank-stability was checked explicitly, not assumed from
the mean-difference figure alone, since a small mean can still hide occasional real rank flips (which
this data shows: max rank shift of 10, well above the mean of ~1).

**Consequences**: all three zero-cost, no-submission-spent RMSE-investigation candidates are now
closed. Two returned negligible/confirmed-correct results (Overture pin, `ST_Within` boundary
touching); this one returned a real but small, uneven, engineering-costly-to-fix effect that is
knowingly left unaddressed, named here rather than silently dropped. `scripts/audit/
check_transport_length_precision.py` is kept in the repo as a reusable, documented check.
Consistent with the Stage 7 Step 8 (Tier C) conclusion already on record: no further
confidently-net-positive formula-level RMSE improvement remains findable without spending a real
submission on a genuine implementation change of uncertain sign — which this investigation
independently corroborates rather than merely repeats. Step 10 (final two-submission selection)
remains the next open task.


## Stage 7 Step 10 — Final two-submission selection: DECIDED

**Date**: 2026-09-24

**Decision D0XX** (see `docs/decision_log.md`'s own numbering convention for the exact ID to assign
at Step 13 close-out) — **Question**: which two submissions should be locked in as this project's
final Zindi selections? — **Options**: A. the single best-evidenced configuration
(`building_gap_centroid` + corrected nested `poi_gap`) submitted as both final slots; B. the
best-evidenced configuration plus a deliberately different "hedge" variant (e.g. the
`building_gap_intersection` starting baseline) as a diversity pick. — **Decision**: A. — **Evidence**:
see the adversarial doubt-driven-development pass below. — **Consequences**: both final submission
slots carry the frozen `src/gaps.py` default; Step 11 (scoring freeze) proceeds against this exact
configuration.

**Adversarial pass performed** (per this step's own required skill,
`agent-skills:doubt-driven-development`), against three specific questions:

1. **Is the RMSE gap between the top two candidates real, above the noise floor?** Verified directly
   against `mlflow.db`'s own logged run data (not merely `docs/scoring_assumptions.md`'s narrative
   summary of it) — 5 real runs recovered: `smoke-test` (no RMSE), `eastern-ok-focused-corrected-poi-
   gap` / Zindi submission `obUDeiZ9` (`building_gap_rule=intersection`, RMSE 0.00015295),
   `tier-a-noise-floor-repeat` (identical intersection config resubmitted, RMSE 0.00015295 —
   byte-identical to the run above, confirming the noise floor is exactly 0.00000000),
   `tier-a-building-rule-sctx-centroid` (south-central-tx only on centroid, RMSE 0.00014674),
   `tier-a-building-rule-all-centroid` / Zindi submission `RCPw2FP4` (all four regions on centroid,
   RMSE 0.000145067). The centroid variant's improvement (~5.16% relative vs. the intersection
   baseline) is many orders of magnitude larger than the exactly-zero noise floor — real signal, not
   resubmission jitter, confirmed from primary logged data rather than assumed from prior
   documentation.

2. **Is each candidate's supporting evidence actually cross-region-confirmed?** Only
   `building_gap_centroid` is. It passed both the isolated-region test (south-central-tx alone) and
   the mandatory cross-region confirmation (all four regions), per the Step 6 guideline's required
   sequencing. `building_gap_intersection` was never a competing, independently-confirmed candidate —
   it was Step 3's starting default, which calibration confirmed as strictly worse, not a tied
   alternative.

3. **Does the gold-standard validation set (Step 9) agree with both?** No — only with
   `building_gap_centroid`. Step 9's 10-tract manual validation set was built and reviewed entirely
   against the current pipeline default, which is `building_gap_centroid` (`src/gaps.py`'s
   `BUILDING_GAP_COLUMN`). All apparent disagreements found during that review (3 tracts flagged for
   `building_gap_centroid`'s reported values looking implausibly low) were investigated and
   positively disproven as visual misreads, not real defects — confirmed via live recomputation of
   actual building counts, per the Step 9 follow-up entries above. `building_gap_intersection` was
   never independently gold-standard-validated at all; it predates Step 9 and has no comparable
   evidence to weigh.

**Conclusion**: no genuine second candidate exists. The Step 10 guideline's own narrow exception
("if two candidates are within a margin plausibly attributable to noise... both are reasonable") does
not apply here — the gap is real, cross-region-confirmed, and far above the empirically-established
zero noise floor, and the only other real full-pipeline submission on record (`building_gap_
intersection`, RMSE 0.00015295) is confirmed worse by every measure checked, not tied. Per the
guideline's corrected rule, deliberately selecting it as a "diverse second pick" would reintroduce
exactly the wrong heuristic ("hedge with a diverse second pick") this project's own critical-review
process already identified and rejected when writing this step's rule.

**Final selection**: both of the two final Zindi submission slots are set to the current frozen
`src/gaps.py` default configuration — `building_gap_centroid`, the corrected nested `poi_gap`
(`poi_gap_hifld` mean-of-defined-among-{fire,ems,schools}, then meaned with the CBP half), and the
capped-ratio formula applied identically to all three components. This matches Zindi submission
`RCPw2FP4`, whose generated file is on disk at `submissions/tier_a/02-building-rule-all-centroid.csv`.

**Open item carried to Step 11 (not a blocker for this decision, but must be resolved before the
freeze)**: `src/gaps.py` was last modified ~1.7 seconds after `02-building-rule-all-centroid.csv` was
generated (per file timestamps: CSV at 1789991372837 ms, `gaps.py` at 1789993109723 ms) — almost
certainly just the doc-comment recording the calibration win (`BUILDING_GAP_COLUMN`'s comment
citing this exact result), not a logic change, but this must be verified bit-for-bit — regenerate the
submission from the current code and diff it against the stored CSV — as part of Step 11's freeze,
not assumed from the near-simultaneous timestamps alone.

**Separate documentation gap noted for Step 13's close-out**: `docs/experiments/
mlflow_runs_export.csv`, which the Step 5 guideline states should exist from the first real
submission onward, was never actually created — `docs/experiments/` contains only `.gitkeep`. The
underlying data exists and was recovered directly from `mlflow.db` for this Step 10 verification, so
nothing is lost, but the intended standalone CSV export artifact is missing and should be generated
before Step 13's close-out, particularly given this project's Best Documentation ambitions.

---

## 2026-10-05 — Stage 7 Step 11 — Scoring freeze (Gate C): LOCKED

**Context**: Step 10's final two-submission selection closed with both slots set to the single
best-evidenced configuration (`building_gap_centroid`, nested `poi_gap`, capped-ratio formula
everywhere). Step 11 requires producing the versioned, frozen scoring artifact per `scoring/README.md`'s
own spec: `scoring/v1/formula.yaml`, `scoring/v1/assumptions.md`, `scoring/v1/checksum.txt`.

**What was verified before freezing** (not just assembled from memory):

- `git status --short` / `git diff --stat` on all six scoring-relevant source files (`src/gaps.py`,
  `src/geometry.py`, `src/features.py`, `src/io.py`, `src/schemas.py`, `src/config.py`) against
  commit `5afea9bfe094c223adc019b2cb188a54a235a290` — all six returned an EMPTY diff. The only file
  under `scripts/` or `src/` with any diff was `scripts/build_submission.py`, which gained an
  optional `building_gap_overrides` kwarg (default path unaffected — confirmed harmless).
- Output reproducibility: `md5sum` + `diff -q` on `submissions/02-eastern-ok-focused-early-submission.csv`
  vs. `submissions/tier_a/02-building-rule-all-centroid.csv` — byte-for-byte identical
  (`2f1cc43b742d125555fb12162638a810` both). The frozen logic reproduces the winning `RCPw2FP4`
  submission exactly; this directly confirms the reproducibility concern carried over from Step 10.
- SHA-256 computed for `src/gaps.py` and its five direct dependencies, matched against the verified
  commit and date.

**Artifacts produced and committed to the working tree**:

- `scoring/v1/formula.yaml` — chosen formula, parameters, and evidence pointers for all three gap
  components, plus the ensembling non-applicability rationale (Tier C).
- `scoring/v1/assumptions.md` — frozen, dated (2026-10-05) verbatim snapshot of
  `docs/scoring_assumptions.md` as it stood at freeze time, with Step 10's four pre-check items
  folded in as a clearly separated post-snapshot addendum rather than edited into the snapshot body.
- `scoring/v1/checksum.txt` — the six SHA-256 hashes, the md5 reproducibility proof, and
  re-verification instructions.

**Effect of this freeze**: per Gate C, no further change to scoring logic (`src/gaps.py` or its
five dependencies) is permitted without a reproducible regression test demonstrating a defect.
This does not block Stage 8 (Bias Discovery) or Stage 9 (analysis) work, which consume the frozen
scorer's output rather than modify it.

**Not yet done at this entry's time of writing**: the git commit itself (staging
`scoring/v1/*` as one clearly-labeled, atomic commit per the guideline's own
`agent-skills:git-workflow-and-versioning` pointer) has not been made — to be confirmed with Henry
before committing.

---

## 2026-10-05 — Stage 7 Step 12 — Automated flattened submission notebook: BUILT AND VERIFIED

**What's done**: `scripts/submission/build_submission_notebook.py` generates `submission/
coverage_gap_solution.ipynb` from the frozen `src/gaps.py` entry point (`score_all_regions`/
`score_region`/`capped_ratio_gap`/`coverage_gap_score`) — not hand-maintained in parallel with
`src/`. The generator walks `gaps.py`'s real `from src.X import name` dependency graph
automatically (both module-level and the function-local imports `gaps.py`/`features.py`
deliberately use to dodge circular imports), inlining every symbol transitively needed — no
hand-written list of "which functions to copy" to drift from the real modules over time.

**Scope decision, made explicit rather than silently assumed**: the actual import chain reachable
from `score_all_regions` is `src.gaps` -> `src.features` (`assert_competition_only`) ->
`src.schemas` (`COMPETITION_ALLOWED_COLUMNS`) -> `src.config` (`REGIONS`). `src/geometry.py` and
`src/io.py` are never imported by this chain — by `gaps.py`'s own module docstring, that layer
(spatial assignment, raw data loading) already ran once to materialize `data/processed/<region>-
tract-features.parquet`, and the frozen scoring computation (`scoring/v1/checksum.txt`'s subject)
reads only those tables. So the generator correctly inlines nothing from `geometry.py`/`io.py` —
this is the real, already-frozen architecture boundary, not an omission.

**Verification performed** (in order):
1. The generator was built and tested against the real `src/gaps.py`, `src/features.py`,
   `src/schemas.py`, `src/config.py` directly (not a mock) before being delivered, catching two
   real bugs in the dependency walk itself: (a) a nested nested `from src.schemas import
   COMPETITION_ALLOWED_COLUMNS` import line inside `assert_competition_only`'s body needed
   stripping (identified and removed via its AST line range, not a text/regex match — a docstring
   in that same function merely *mentioning* "from src.schemas import ..." as documentation would
   have false-positived a naive text-based check); (b) module emission order initially broke
   because `score_all_regions`'s `regions: list[str] = REGIONS` default value is evaluated at
   function-definition time, so `src.config`'s `REGIONS` had to be inlined before `src.gaps`'s own
   section in the flattened file — fixed with an explicit per-module topological sort based on the
   real dependency edges discovered during the walk, not source-file declaration order.
2. The flattened source's self-check cell re-asserts every one of `tests/test_gap_arithmetic.py`'s
   hand-computed golden-case values (capped-ratio edge cases, the two-defined-of-three mean, the
   nested `poi_gap` two-stage mean, the frozen `building_gap_centroid` default and its override) —
   confirmed to pass against the real, current `src/gaps.py`, not a stale copy.
3. A genuine AST-based check (parsing the rendered output and scanning for any remaining
   `ast.ImportFrom`/`ast.Import` targeting `src`) confirms zero project-local imports in the
   generated file — deliberately not a text/`grep`-style check, for the same false-positive reason
   as item 1 above.
4. First real run on Henry's machine (`python -m scripts.submission.build_submission_notebook`)
   surfaced a genuine runtime issue the fixture-only self-check couldn't catch: Jupyter's default
   working directory is the notebook's own folder (`submission/`), not the repo root, so the
   notebook's final `score_all_regions()` cell failed with `FileNotFoundError` on the relative
   `data/processed/` path. Fixed by adding a small repo-root-finder cell (walks up from the current
   working directory looking for a `data/processed/` folder) to the generator's own notebook
   output — not a one-off hand-edit to the generated `.ipynb`, which would have silently
   desynchronized it from the generator on the next regeneration.
5. Re-verified end-to-end on Henry's machine after the fix: all cells ran successfully, confirming
   the flattened notebook reproduces a real four-region scored table from the frozen logic with
   zero project-local imports — exactly the artifact `submission/README.md` says gets submitted for
   code review if this project places in the top 10.

**Why**: this project's own rule, stated directly in the challenge's requirements: "Custom packages
in your submission notebook will not be accepted." The modular `src/` layout is correct for
development and the GitHub portfolio, but is itself exactly the kind of custom-package dependency a
code reviewer could flag. Generating the flattened notebook (rather than hand-maintaining a second
copy) removes the real risk of that copy silently drifting from the actual frozen `src/` logic.

**Deliverable**: `scripts/submission/build_submission_notebook.py` (generator, committed);
`submission/coverage_gap_solution.ipynb` (generated artifact, committed, reproducible by rerunning
the generator) — both delivered to and verified on Henry's machine, not just produced in isolation.

---

## 2026-10-05 — Stage 7 Step 13 — Close-out: docs reconciled with Stage 7's real, verified outcome

**What's done**: every Stage 7 artifact and open item checked directly against what the stage
actually produced, not assumed complete:

1. **`docs/scoring_assumptions.md`** — final read-through confirms every tracked ambiguity already
   carries a real validation status (`README-confirmed`, `RMSE-experiment-confirmed`, or
   `self-check-consistent`); none left `unconfirmed`. No edit needed — the frozen snapshot already
   taken at Step 11 (`scoring/v1/assumptions.md`) remains an accurate point-in-time copy.
2. **`docs/risk_register.md`** — three real updates, not routine housekeeping:
   - **R-003 closed.** `notebooks/03_building_vs_housing_analysis.ipynb` was still genuinely empty
     at the start of Step 13 despite being a named Stage 7 deliverable — found by checking the file
     directly rather than trusting the step list. Built using the already-loaded, already-schema-
     confirmed ACS housing data (`docs/data_manifest.md` Section 7) and Stage 6's already-
     materialized building-footprint counts; shows the housing-unit-to-building-footprint ratio is
     not clustered near 1:1 and varies widely both within and across regions, confirming
     `building_gap`'s exclusive use of footprint counts (never housing units) was the right call.
   - **R-009 corrected**, matching this register's own established practice (R-004/R-005) of fixing
     a plan to match reality rather than leaving a stale status: the water-dominated-tract
     confound mitigation does not land as a `gaps.py` scoring-table column (that would be scope
     creep against the Step 11 freeze) — it already exists as the standalone, committed
     `docs/validation/water_dominated_geoids.json` from Step 9's gold-standard validation build.
     Stage 8/9 joins on `GEOID` against this file; status corrected from "Open — planned for Stage
     7/8" to "Mitigated — mechanism exists and is committed."
   - **R-012 added, found live during R-003's own fix.** `notebooks/03_building_vs_housing_
     analysis.ipynb`'s first draft copied `01_eda.ipynb`'s `sys.path` setup verbatim (adding both
     `REPO_ROOT` and `REPO_ROOT / "src"`), which crashed with `ImportError: cannot import name
     'mean' from 'statistics'` on the real machine: `src/statistics.py` (a Stage 9 placeholder,
     currently just a docstring) shadows the real stdlib `statistics` module the instant `src/`
     itself sits on `sys.path`, and `geopandas.explore` imports `from statistics import mean`
     internally. `01_eda.ipynb` only avoids this by the happenstance of importing `geopandas`
     before its own path insertion runs — not a deliberate guard. Fixed in the new notebook by
     only adding `REPO_ROOT` to `sys.path` (sufficient, since every import in this project is
     package-qualified). Logged as a standing, not-fully-closed risk: the durable fix (renaming
     `src/statistics.py`, or auditing every sys.path setup) is deferred to before Stage 9 populates
     that module for real.
3. **`docs/experiments/mlflow_runs_export.csv`** — a named Stage 7 deliverable
   (`PROJECT_BLUEPRINT.md`'s Stage 7 section) that did not exist yet at the start of Step 13.
   Generated via `scripts/mlflow_log.py`'s already-built `export` command on Henry's machine; the
   5 exported runs match `docs/scoring_assumptions.md`'s and this log's own documented RMSE trail
   exactly (0.00015295 noise-floor repeat, 0.00014674 isolated south-central-tx, 0.000145067
   cross-region-confirmed frozen result) — real confirmation, not just a file existing.
4. **`README.md`** — stage badge/checklist updated to Stage 7 complete; headline RMSE
   (0.000145067, the frozen `scoring/v1/` result) referenced now that a real number exists.
5. **`PROJECT_BLUEPRINT.md`** — Stage 7's own exit criteria (Gate B → Gate C) confirmed met against
   the real, verified outcome: both fixture tiers green (`tests/test_gap_arithmetic.py`,
   `tests/test_geometry_assignment.py`); every Stage 5/7 self-check passed and re-verified
   (transport-only-undefined, any-of-three-undefined, noise floor, cross-region confirmation);
   gold-standard validation set agrees (Step 9); `docs/scoring_assumptions.md` fully resolved;
   versioned scoring artifact produced and frozen (`scoring/v1/`); final two submissions selected
   (both the single best-evidenced `RCPw2FP4` configuration, per Step 10's corrected rule); the
   generated flattened notebook runs top-to-bottom, verified twice on Henry's real machine (once
   against fixtures alone, once against the real four-region feature tables after the working-
   directory fix).

**Why**: identical discipline to every prior stage's close-out — a stage is not done until its own
named deliverables and its own risk register's open items are checked directly against the stage's
actual, current state, not assumed complete because the step-by-step guideline was followed in
order. Two of Step 13's three real findings (the empty notebook, the missing mlflow export) were
caught exactly this way — by checking the filesystem, not by re-reading the guideline's own summary
of what should already exist.

**Gate C status**: Stage 7 (Reference Reconstruction Engine) is closed, frozen, and documented.
Step 14 (the adversarial verification pass) is the one remaining step before Stage 8 (Bias
Discovery) begins.
