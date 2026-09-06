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
