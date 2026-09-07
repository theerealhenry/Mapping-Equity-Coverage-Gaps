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
