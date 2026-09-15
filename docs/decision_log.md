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
