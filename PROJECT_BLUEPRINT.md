# Project Blueprint — Bias Bounty Mapping Equity Challenge

**Author:** Henry Otsyula
**Status:** Single source of truth for how this project is built, stage by stage, self-contained.
This document does not point elsewhere for the substance of any decision — every fact, formula,
rule, and piece of reasoning that governs how the project is built is written out here in full.
Update it whenever a real decision changes something below — it should always describe what the
project actually does, not an aspirational plan that's drifted from reality.

---

## 0. What this project is, honestly

This project computes a **coverage-gap score** for 9,379 U.S. Census tracts across four study
regions (Maricopa County AZ, the Northern California fire corridor, Eastern Oklahoma tribal
statistical areas, South-Central Texas along I-35/I-37) by comparing Overture Maps data against
four independent reference datasets — Census TIGER/Line roads, Microsoft building footprints,
USGS/HIFLD critical facilities, and Census County Business Patterns establishment counts — then
evaluates how those coverage gaps are distributed across communities defined by social
vulnerability (CDC SVI), climate vulnerability (U.S. CVI), tribal land status, and heat/wildfire/
drought hazard exposure.

**The strategic objective, stated precisely**: win the accuracy leaderboard (1st place), win Best
Bias Discovery, and win Best Documentation. It is worth being precise about this because the
challenge's own rules make an unusual distinction that's easy to blur: every submission
automatically receives a Bias Scorecard (five equity metrics broken down by strata), but that
scorecard **does not affect leaderboard ranking at all** — the leaderboard is decided by RMSE
alone. Best Bias Discovery is a separate prize, judged from a written narrative about a disparity
pattern the automated scorecard doesn't surface, not from the scorecard's own numbers. So "win the
Bias Score" is not a coherent goal — the correct framing is that the accuracy engine and the Bias
Discovery narrative are two different deliverables competing for two different prizes, built from
the same underlying computation but evaluated by entirely different mechanisms.

### 0.1 What kind of system this is — the Reference Reconstruction Engine

The competition's evaluation target is organizer-generated and deterministic: submissions are
scored by RMSE "against organiser-computed reference coverage gap scores." That single fact
should shape how every downstream piece of this project is named and reasoned about. The core
pipeline this project builds is not fitting a model to data — it is **reconstructing a specific,
hidden, deterministic computation** that the organizers already ran once and are not sharing. Every
formula question, every spatial-assignment choice, every self-check exists to close the gap
between our reconstruction and their (unseen) original. Calling this a "model" invites the wrong
mental model (pun acknowledged) — it invites hyperparameter-tuning instincts that don't apply here.
This project instead calls it the **Reference Reconstruction Engine**, and treats it with the
discipline appropriate to reverse-engineering a deterministic specification: golden-case fixtures
instead of a held-out test set, a designed-experiment calibration protocol instead of
hyperparameter search, and — critically — an explicit acknowledgment that repeatedly querying the
public leaderboard to compare candidate reconstructions is itself a noisy measurement process that
needs its own statistical discipline (Stage 7).

Four distinct systems sit downstream of the Reference Reconstruction Engine, each with a different
objective, and keeping them conceptually and architecturally separate is the single most important
structural decision in this project:

```
                    ┌─────────────────────────────────┐
                    │      CHALLENGE DATA PACKAGE      │
                    │   reference / strata / boundaries│
                    └────────────────┬──────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │   DATA GOVERNANCE (Stages 0–4)   │
                    │ schema contracts / CRS / audit / │
                    │ data dictionary / repo structure │
                    └────────────────┬──────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │        FEATURE LAYER             │
                    │  tract-indexed base table with   │
                    │  explicit feature_role tagging   │
                    │  (competition / research /       │
                    │   diagnostic) — Stage 6           │
                    └────────┬──────────────┬──────────┘
                             │              │
              ┌──────────────┘              └──────────────┐
              ▼                                            ▼
   ┌───────────────────────────┐              ┌───────────────────────────┐
   │  REFERENCE RECONSTRUCTION │              │   EQUITY RESEARCH ENGINE  │
   │        ENGINE (Stage 7)   │              │      (Stages 8–9)         │
   │  road / building / POI    │              │  bias hypothesis mining   │
   │  gap, composite, defined- │              │  Bias API replica         │
   │  ness — deterministic,    │              │  statistical confirmation │
   │  frozen after Gate C      │              │  flagship narrative       │
   └──────────────┬─────────────┘              └──────────────┬────────────┘
                  │                                            │
                  ▼                                            ▼
   ┌───────────────────────────┐              ┌───────────────────────────┐
   │  SYSTEM A — COMPETITION   │              │  SYSTEM C — EXPLANATORY   │
   │  Objective: minimize RMSE │              │  ML ENGINE (part of       │
   │  controlled calibration,  │              │  Stage 8)                 │
   │  scoped ensembling, final │              │  Objective: explain       │
   │  submission selection     │              │  patterns in our own      │
   └──────────────┬─────────────┘              │  reconstructed data,     │
                  │                            │  never forecast the      │
                  │                            │  hidden true score       │
                  │                            └──────────────┬────────────┘
                  │                                            │
                  └──────────────────┬─────────────────────────┘
                                     ▼
                    ┌─────────────────────────────────┐
                    │  SYSTEM B — DOCUMENTATION /       │
                    │  MODEL CARD (Stage 11)            │
                    │  methodology / evidence / limits  │
                    └────────────────┬──────────────────┘
                                     │
                    ┌────────────────┴──────────────────┐
                    ▼                                    ▼
       ┌────────────────────────┐          ┌───────────────────────────┐
       │  ZINDI SUBMISSION       │          │  SYSTEM D — PRESENTATION/  │
       │  generated flattened    │          │  DEPLOYMENT ENGINE         │
       │  notebook, reproducible │          │  (Stage 12): static,      │
       │  from a frozen snapshot │          │  precomputed Streamlit app │
       └────────────────────────┘          └───────────────────────────┘
```

Reading this diagram left to right by objective: **System A (the Competition Engine)** exists to
minimize RMSE against the frozen Reference Reconstruction Engine's output, under a controlled,
budget-aware calibration protocol. **The Equity Research Engine** exists to discover disparity
patterns the automated scorecard doesn't surface, through hypothesis mining and statistically
confirmed evidence. **System C (the Explanatory ML Engine)**, which lives inside Stage 8, exists
only to explain patterns in our own already-computed data — it is never used to forecast the
hidden true score, and every place its output is cited, that distinction is restated. **System D
(the Presentation/Deployment Engine)** exists to expose the finished results interactively. These
four objectives do not need to be maximized simultaneously by the same artifact, and treating them
as one undifferentiated "the model" is exactly the framing this document deliberately avoids.

### 0.2 Precision on what "no ground truth" actually means

There is no per-tract ground-truth coverage-gap label available for any tract, at any point in
this project — but it would be imprecise to say there is "no training signal at all." What
actually exists is a single **noisy aggregate external evaluation signal**: one RMSE number per
submission, computed against a random ~30% public slice of the 9,379 tracts. That signal is real
and it is used, extensively, throughout Stage 7's calibration protocol. It is simply not the kind
of signal ordinary supervised learning needs — there is no way to compute a per-tract residual to
regress against. The precise statement of the limitation is: **fitting a supervised residual-
correction model (LightGBM/XGBoost/CatBoost "learning systematic residuals") is statistically
infeasible given a 300-submission budget queried against 9,379 unknown per-tract values — not
impossible in some absolute information-theoretic sense, just infeasible at the sample size and
query budget this competition actually provides.** The valid use of the aggregate RMSE signal is
model *selection* over a small number of interpretable, deterministic candidates (Stage 7's
designed-experiment calibration) — not model *fitting* against residuals that were never
computable in the first place. This precision matters because a knowledgeable reviewer could
reasonably ask "but you do have feedback from Zindi" — yes, and the document should be exact about
what that feedback can and can't legitimately be used for.

That said, this project does perform real, honest machine learning — just not on the competition
target. **System C, the Explanatory ML Engine (Stage 8)**, trains models to explain our own
already-computed `coverage_gap_score` from strata/vulnerability features. This is legitimate,
standard explanatory-modeling practice: X → Ŷ (our reconstruction), never X → Y (the organizer's
hidden true score). SHAP output from this model must always be framed as "factors associated with
our reconstructed coverage-gap measure," never as "this factor causes worse mapping equity" —
that distinction is written directly into the model card and restated everywhere SHAP evidence is
cited in the Bias Discovery writeup. Unsupervised clustering (also Stage 8) genuinely earns its
place too, surfacing disparity archetypes the five fixed Bias API metrics can't see because they
never combine features.

This framing — stated here, and restated in the shipped `README.md` and `docs/methodology.md` —
is itself part of what makes this a senior-level submission: a reviewer who understands ML will
respect "we identified there was no valid supervised-learning signal for the competition target,
and built the right, honestly-scoped tool for the actual problem" far more than a forced narrative
that doesn't hold up under a second look.

---

## 1. Technology stack (and why each piece earns its place)

| Tool | Role | Why this one |
|---|---|---|
| **DuckDB** (+ httpfs, spatial) | Primary engine for large spatial aggregations directly against cloud-hosted GeoParquet | Handles the multi-hundred-MB Overture layers without full local materialization; SQL-based aggregation is easy to test and reason about |
| **GeoPandas / Shapely** | Interactive geometry work, golden-case fixtures, map rendering | The right tool for small, precise, inspectable geometry operations and plotting |
| **pandas / pyarrow** | Tabular manipulation, parquet I/O | Standard, public, submission-notebook-safe |
| **pandera** | Schema/contract validation for every input layer | Lightweight, pip-installable (not a "custom package" — it's a public dependency, same category as pandas), turns "we eyeballed the schema once" into an enforced, re-runnable contract that fails loudly if a layer's shape changes |
| **pytest** | Two-tier automated test suite | Arithmetic-correctness fixtures and geometry-assignment fixtures are different failure modes and are tested separately (Stage 7) |
| **MLflow** (local file-store or SQLite backend) | Experiment tracking, split into three named experiments: `competition-scoring`, `diagnostic-modeling`, `bias-discovery` | Free, self-hosted, no external account needed; three separate experiments keep the tracking store coherent instead of an undifferentiated dumping ground |
| **scikit-learn + LightGBM + SHAP** | The explanatory model (Stage 8) and clustering | Standard, well-understood tools for explanatory modeling and feature-importance evidence — not used to generate submission values, only to explain our own computed output |
| **Optuna** | Hyperparameter optimization for the Stage 8 explanatory models | Efficient search with native nested-run logging into MLflow — used only where a real trained model with a real target exists (Stage 8), never for the Reference Reconstruction Engine, which has no valid target to tune against |
| **argparse (standard library)** | `src/cli.py` — the canonical command-line interface | No new dependency needed for a handful of subcommands; `python -m src.cli <command>` works on any platform including Windows, where `make` is not native |
| **GitHub Actions** | CI/CD | Free, standard, runs the test suite, schema checks, and the generated-submission-notebook smoke test on every push |
| **Streamlit**, deployed on **Streamlit Community Cloud** (free tier) | The deployed, interactive Coverage Gap Explorer + Equity Profile Explorer panel | No server to manage, free, directly supports an interactive map + filter UI and a live call into the small explanatory model — genuinely lets a visitor "interact with it," not just look at a static image; ships from a small committed data bundle, not a live connection to the source bucket |

Nothing here is exotic or resume-padding for its own sake — each tool is doing a job the project
actually needs, and no tool is added anywhere it wouldn't be doing real work. That restraint
carries into the repository layout too: no per-region YAML configs (the computation is
region-agnostic; region metadata lives in one `src/config.py`), no dedicated `src/fairness/`/
`src/evaluation/`/`src/visualization/` packages beyond what's listed in Section 4, no project-wide
lineage/audit-trail system beyond the versioned scoring artifact described in Stage 7. The
following are explicitly **optional, adopted only if a real finding justifies them** — not
must-haves that would otherwise weaken the project: HDBSCAN (used only if the data actually shows
non-convex/variable-density cluster structure — k-means with PCA/silhouette inspection is the
default), a stacking ensemble for the explanatory model (a simple averaging ensemble is the
default; stacking is adopted only if it demonstrably beats both single models and the average), a
SHAP explainer on a stacked ensemble specifically, more than the core set of publication maps, and
every spatial statistic in the toolkit (Moran's I/Getis-Ord Gi* are used only where a
spatial-clustering claim is actually made, not by default).

---

## 2. Competition gates

The project is organized around five explicit, checkable gates, each of which must pass before
the next phase of work begins. This is the top-level control structure everything else in Section
3 operates inside.

- **Gate A — Data Trusted.** No pipeline code runs against real data until: every layer's pandera
  schema contract passes (Stage 2), the CRS utility has its own passing test (Stage 2), tract
  membership counts match the published figures (Stage 2/5), and geometry-validity QA is clean or
  every exception is documented with a decision (Stage 2).
- **Gate B — Scorer Trusted.** No submission is uploaded until: both test-fixture tiers are green
  (Stage 7), the transport-only-undefined and any-of-three-undefined self-checks both match
  published statistics (Stages 5 and 7), the gold-standard manual validation set agrees with the
  pipeline's own output (Stage 7), and the smoke-test submission has confirmed the platform
  accepts the file format.
- **Gate C — Scoring Frozen.** Once the discussion-board question is answered (or a firm deadline
  passes without an answer), the designed-experiment calibration protocol has run, and the final
  formula/spatial-assignment/ensemble choices are made, the Reference Reconstruction Engine is
  **frozen**: a versioned scoring artifact is produced (Stage 7), and after this point, no change
  to scoring logic is made without a reproducible regression test demonstrating a defect. Stage 8
  and Stage 9 both train and analyze against a dated snapshot of this frozen output, not a moving
  target. **If evidence surfaces after the freeze that contradicts a formula assumption** (for
  example, a late discussion-board answer, arriving at an unpredictable time — there is no
  guarantee it lands before the freeze), the response is not to silently rework Stages 7–9 under
  deadline pressure. It is documented explicitly as a known limitation and sensitivity note in
  `docs/scoring_assumptions.md` and `docs/decision_log.md`, with an honest statement of what would
  change if the new evidence were incorporated, and a re-freeze is only performed if there is
  still enough calendar time and submission budget to redo the calibration protocol properly (see
  the calendar in Section 6). A late, unincorporated contradiction that's transparently documented
  is a better outcome than a rushed, undocumented late change.
- **Gate D — Bias Discovery Frozen.** Only the hypotheses that survive the full funnel (Stage 9:
  screening → candidate scoring → statistical confirmation) appear in the final writeup. Once the
  writeup is drafted, no new candidate is added without going through the same funnel.
- **Gate E — Code Review Ready.** The generated flattened submission notebook (Stage 7/11) passes
  from a clean environment, every `docs/` file is complete, and the repository could survive a
  48-hour top-10 code-review request with zero prep, at any point from Stage 7 onward — not just
  at the very end.

---

## 3. Stage-by-stage blueprint

Each stage states: **Why** (the reasoning), **Activities**, **Tools**, **Deliverables**, **Exit
criteria** (what has to be true before moving on, tied to the gates in Section 2 where relevant).

### Stage 0 — Environment & reproducibility foundation

**Why**: Nothing downstream is trustworthy if the environment isn't pinned and reproducible from a
clean machine. This is also the fastest, cheapest signal of engineering maturity a reviewer sees —
it's the first thing anyone checks when they try to actually run the project.

**Activities**:
- Pin `requirements.txt` exactly: `pandas`, `geopandas`, `pyarrow`, `duckdb`, `numpy`,
  `matplotlib`, `obstore`, `jupyter`, `ipykernel`, `tqdm` (already pinned, matching the challenge
  tutorial notebook's own environment), plus `pandera`, `mlflow`, `scikit-learn`, `lightgbm`,
  `shap`, `optuna`, `streamlit`. No new dependency is needed for the CLI — `argparse` is standard
  library.
- Build `src/cli.py` as the canonical command-line interface, with subcommands mirroring the
  pipeline stages: `python -m src.cli audit`, `python -m src.cli eda`, `python -m src.cli features
  --region eastern-ok`, `python -m src.cli score --region eastern-ok`, `python -m src.cli
  build-submission`, `python -m src.cli validate-submission`. This is the interface a reviewer on
  any platform (including Windows, where `make` is not native) can actually run. A `Makefile` is
  then built as a thin convenience wrapper around these same commands (`make audit` simply calls
  `python -m src.cli audit`), not the only way to reproduce the project.
- Fix random seeds everywhere they're used (bootstrap/permutation in Stage 9, the explanatory
  model's train/validation split and any stochastic clustering in Stage 8, Optuna's sampler) and
  record them in one place (`src/config.py`).
- Initialize git, first commit, create the GitHub repository, set up branch protection on `main`
  requiring the CI check (Stage 10) to pass before merge.

**Deliverables**: `requirements.txt` (finalized), `src/cli.py`, `Makefile`, git repo initialized
and pushed, `docs/reproducibility.md` skeleton (filled in fully at Stage 11).

**Exit criteria**: a clean clone + `pip install -r requirements.txt` + `python -m src.cli --help`
+ `pytest` succeeds with zero pipeline code written yet (an empty test suite passing is fine at
this point — the point is the scaffolding works).

---

### Stage 1 — Data acquisition & governance

**Why**: The data lives in a public bucket at a pinned Overture release; before any analysis, the
project needs an explicit, documented contract for *which* data version it computes against and
how it's accessed, so results are reproducible months later even if the bucket's contents change
upstream. This stage is also when the one lever that can eliminate real uncertainty for free —
asking the competition organizer directly — gets pulled, since a response can take days (and, per
Gate C above, there is no guarantee it lands before the scoring freeze) and should be given the
most possible time to arrive.

**Activities**:
- Document the exact access pattern (HTTPS for DuckDB, anonymous S3 for pyarrow/geopandas) and
  the pinned Overture release (`2026-08-19.0`) in `src/config.py`.
- Record a lightweight data manifest: for every object the pipeline reads, its S3 key, size, and
  a content hash or `ETag` if cheaply available — not full DVC-style data versioning (overkill
  for a fixed, read-only public bucket), just enough that "did the upstream data change under us"
  is answerable later.
- No bulk local download by default — the pipeline reads directly from the bucket (bbox/column
  pushdown via DuckDB) except where a stage genuinely needs a local cache (Stage 6 onward);
  intermediate results are cached to `data/interim/` as parquet, gitignored.
- **Post a question to the Zindi discussion board**, in parallel with everything else, not gating
  on it: the discussion board has zero posts and the competition is only days old, so a clean,
  well-formed question now has the best odds of a direct organizer answer before the thread fills
  with noise, and it costs nothing against the submission budget. The question covers the two
  formula components still treated as working hypotheses rather than confirmed facts: whether the
  capped-ratio formula the challenge documentation states explicitly for the POI/HIFLD gap
  (`1 - min(1, overture/hifld)`) also applies to the building-footprint gap and the road-network
  gap, and what the spatial-assignment rule is for features that straddle a tract boundary
  (centroid-in-polygon vs. geometric intersection). Worst case: no answer, and Stage 7's
  designed-experiment calibration resolves it instead. Best case: skip an entire uncertain phase
  for free.
- Record every confirmed fact from direct verification against the live bucket (not the README's
  prose, actual `list_objects_v2`/schema/cell-value reads) in `docs/data_manifest.md`:
  - No answer-key or reference coverage-gap file is shipped anywhere in the public bucket — a
    direct scan of every region's `reference/` folder for anything gap/coverage/score/answer/
    solution/target/label-shaped returned zero matches in all four regions.
  - GEOID is pre-joined on exactly one layer: Census CBP (which ships as tract polygons with
    `cbp_estab`/`cbp_estab_bus`/`cbp_estab_res` already attached). Every other layer — Overture
    buildings/roads/POIs, Microsoft buildings, TIGER roads, all four HIFLD facility layers — is
    bare geometry with no tract identifier, so each one needs an explicit spatial join against
    tract polygons (`strata/<region>/<region>-census-tracts.parquet`).
  - Real Overture `categories.primary` facility-category strings are confirmed exact from live
    data (`fire_department`, `ambulance_and_ems_services`, `elementary_school`, `middle_school`,
    `high_school`, `school`, `private_school`, `public_school`, plus `hospital` — deliberately
    excluded from the facilities half of the POI gap since Overture over-counts hospitals roughly
    12x, which would otherwise make that term never show a deficit). The same live sample also
    surfaced two dozen near-miss categories a substring/fuzzy match would wrongly count —
    `driving_school`, `fire_protection_service`, `animal_hospital`, `emergency_pet_hospital`, and
    the sharpest example, `security_systems`, which literally contains the substring "ems" —
    concrete, real evidence that exact-match on `categories.primary` is required, not optional.
  - The real Zindi upload target is a single combined-region 17-column CSV (`region` column
    present, plus every component/`_defined` sub-column) across all 9,379 tracts. Each region's
    bucket-hosted `<region>-sample-submission.csv` is a different artifact — the manifest of which
    GEOIDs must be scored for that region (columns: `GEOID, transport_gap, building_gap, poi_gap,
    coverage_gap_score`), not the upload shape. A direct check of that manifest's cell values
    (not just its shape) confirms every value in every gap column is literally `0.0` — an inert
    placeholder, not a partial answer leak.
  - Confirmed region facts: eastern-ok 1,192 scored tracts, maricopa-az 1,593 (1,592 Arizona
    tracts plus one New Mexico tract, `35023970000`, Hidalgo County Tract 9700, where the region
    boundary meets the state line), northern-ca 591, south-central-tx 6,003 — 9,379 scored tracts
    total. Published per-region transport-only-undefined percentages (used as an early self-check
    in Stage 5): eastern-ok 21.2%, maricopa-az 54.6%, northern-ca 36.9%, south-central-tx 28.4%.
    A separate, genuinely different published statistic — the percentage of tracts with *at least
    one* of the three components undefined (used as a later self-check in Stage 7, once
    building/POI definedness logic exists): eastern-ok 21%, northern-ca 37%, south-central-tx
    28%, maricopa-az 55% (rounded). These two statistics are close for three of the four regions
    but are not the same measurement, and must never be conflated or treated as interchangeable.
  - **`transport_gap` is explicitly not comparable across regions** — the challenge documentation
    states this directly: Overture and TIGER draw the primary/secondary highway boundary
    differently per region, and the ratio between them ranges 0.71 to 1.59 across the four study
    regions for classification reasons that have nothing to do with actual mapping effort. This
    fact is recorded here because it has a direct downstream consequence for Stage 8: any
    diagnostic model or clustering pass that mixes `transport_gap` across regions risks partly
    learning a classification-scheme artifact rather than a genuine equity signal, and that risk
    has to be designed around explicitly, not discovered after the fact.
  - Confirmed competition mechanics from the live Zindi page: deadline October 31, 2026 (started
    August 28, 2026); public leaderboard is ~30% of the test set, private ~70%, a random partition
    of the same fixed 9,379-tract list (not a time-series or adversarial split); 10 submissions
    per day, 300 total; the top 2 submissions are selected for final private-leaderboard scoring;
    a top-10 finish gets 48 hours to submit code for review; the project's own rules state
    directly that "custom packages in your submission notebook will not be accepted"; every
    submission automatically receives a Bias Scorecard, but it **does not affect leaderboard
    ranking** — the leaderboard is decided by RMSE alone, and Best Bias Discovery is judged
    separately, from the methodology writeup; the scored coverage-gap computation must use only
    the datasets provided for the challenge — additional public data sources are permitted only
    for the Best Bias Discovery prize, never for the scored submission.

**Deliverables**: `src/config.py` (finalized bucket/version/region constants), the posted
discussion-board question, `docs/data_manifest.md` (object keys, sizes, access pattern, pinned
release, and every confirmed fact above).

**Exit criteria**: every layer the pipeline will touch is reachable and named in one place; no
script anywhere hardcodes a bucket path outside `config.py`; the discussion-board question is
live.

---

### Stage 2 — Data audit, validation contracts & catalog

**Why**: Before writing any transformation logic, establish ground truth about what's actually in
every layer, across all four regions — not just one region's `reference/` folder, which is as far
as verification has gone so far. This is where schema drift, nulls, invalid geometries, and
duplicate keys get caught cheaply, before they surface as confusing bugs three stages later. This
stage is what closes Gate A.

**Activities**:
- Generalize the existing bucket-verification script into `scripts/audit/audit_bucket.py`, run
  across all four regions plus `strata/` and `boundaries/` (not just `reference/eastern-ok/`,
  which is all that's been directly audited to date): full listings, schemas, row counts, null
  coverage per column, duplicate-GEOID checks, geometry validity (invalid/empty/multipart
  geometries), CRS consistency across every layer in every region.
- **Encode the audit's findings as enforced contracts, not just printed output**: a `pandera`
  schema per layer type (Overture buildings, Overture roads, Overture POIs, Microsoft buildings,
  TIGER roads, HIFLD facilities, CBP) in `src/schemas.py`, checked by `io.py` on every load. This
  is the senior-level upgrade over "we looked at it once and it seemed fine" — if a layer's shape
  ever changes, the pipeline fails loudly at load time with a clear message, not silently
  downstream.
- **Confirm the actual structure of Overture's `sources` field before Stage 6 builds anything
  against it** — its exact dataset-name granularity and value set are not yet directly verified
  (only that it's a list of structs, each carrying its own `confidence`, distinct from POIs where
  `confidence` is a flat column). This gates the source-provenance feature vector built in Stage 6.
- Run this as `notebooks/00_data_audit.ipynb` (human-readable narrative + figures, this is the
  project's data-integrity EDA pass) backed by the script (machine-runnable, CI-able against a
  small fixture-sized slice). This single audit notebook also absorbs what would otherwise be a
  separate "spatial QA" pass — geometry validity, CRS consistency, and tract-boundary integrity
  are data-audit concerns either way, and one well-scoped notebook covering both is tighter than
  two overlapping ones.
- CRS discipline established here and enforced everywhere downstream: `OGC:CRS84` (lon/lat)
  throughout. DuckDB's `spatial` extension follows EPSG authority axis order for the literal
  string `EPSG:4326` specifically (lat/lon, the opposite of CRS84), which silently produces
  `POINT(inf inf)`/NaN results if used carelessly — every transform goes through one shared,
  tested utility in `src/geometry.py` (`always_xy=True` / explicit CRS84 handling), never ad hoc
  per script.

**Deliverables**: `scripts/audit/audit_bucket.py`, `src/schemas.py` (pandera contracts),
`notebooks/00_data_audit.ipynb`, an audit findings summary appended to `docs/data_manifest.md`.

**Exit criteria (Gate A)**: every layer in every region has a passing schema contract; every known
null/geometry-validity issue is documented with a decision (drop, impute, or accept and note in
the risk register); the CRS utility in `src/geometry.py` has its own passing unit test before any
other geometry code is written against it; the `sources` field's real structure is confirmed.

---

### Stage 3 — Data dictionary

**Why**: The national strata table (`national-strata-tract-table.parquet`, 232 columns spanning
population, SVI, CVI, rurality, heat, wildfire, drought, and tribal domains) is the single biggest
unlock for Bias Discovery prioritization — you can't design a disparity crosstab against columns
you haven't inventoried. Doing this early, from the real schema rather than the challenge
documentation's prose description, prevents re-discovering column names piecemeal during Stage 9.
Building it as a governance artifact, not just a lookup table, is what makes Stage 6's
feature-role separation and Stage 1's external-data enforcement actually checkable later.

**Activities**: Inspect the real `national-strata-tract-table.parquet` schema directly; categorize
every column by domain, and record a richer field set per column than a simple lookup would need:
`column`, `source_table`, `dtype`, `domain`, `description`, `coverage` (which regions/tracts it's
populated for), `vintage` (the data year/version it reflects), `unit`, `level` (tract/county/
national), `null_semantics` (what a missing value actually means for this column — e.g. "SVI
unavailable" vs. "true zero"), `role` (identifying / measurement / weighting), `allowed_for_scoring`
(boolean — is this column permitted anywhere in the competition-submission path), `allowed_for_bias`
(boolean — permitted in Bias Discovery analysis only), and `candidate_hypotheses` (free text —
which Bias Discovery candidate(s), if any, this column feeds). This turns the dictionary into an
enforceable governance record, not just documentation: `allowed_for_scoring` is exactly the flag
Stage 6's `feature_role` tagging and Stage 1's external-data-provenance check are built against.

**Deliverables**: `docs/DATA_DICTIONARY.md` (human-readable), `docs/schema_catalog.csv`
(structured, queryable version of the same fields — so it can be joined/queried programmatically,
e.g. by Stage 8's explanatory model selecting features by domain and `allowed_for_scoring`/
`allowed_for_bias`, rather than only read by a human).

**Exit criteria**: every column used anywhere downstream (feature engineering, bias discovery,
explanatory model) is traceable to an entry in the dictionary, with its `role` and
`allowed_for_scoring`/`allowed_for_bias` flags set.

---

### Stage 4 — Repository restructure

**Why**: The project starts from a minimal scaffold; before real pipeline code is written, the
repository needs to be in the shape that code will actually live in, so nothing gets built in the
wrong place and moved later.

**Activities**: Create the full directory tree specified in Section 4 below; move the already-
scaffolded files (`README.md`, `.gitignore`, `requirements.txt`, `src/config.py`,
`docs/methodology.md`, `docs/bias_discovery.md`) into their final positions; create empty
placeholder files for everything else the tree names, to be filled in by later stages.

**Deliverables**: the full repository tree in place.

**Exit criteria**: repo matches the tree in Section 4; `pytest` still passes (imports resolve,
even with mostly-empty modules).

---

### Stage 5 — Exploratory data analysis (EDA)

**Why**: Before trusting any computed gap value, establish that the raw ingredients behave as
expected and that our own reproduction of the challenge's *published* summary statistics matches
— this is the cheapest, most direct correctness signal available, and it's checkable before the
full pipeline exists. This stage has two genuinely different goals, and keeping them distinct
prevents the EDA notebook from turning into an undifferentiated dump: **EDA-A, data integrity**,
is Stage 2's job (the audit notebook) — it is not repeated here. **EDA-B, phenomenology** — what
the data actually looks like and how its pieces relate — is this stage's job. This stage
deliberately only runs the self-checks that are answerable with just road and tract data — the
checks that need building/POI logic wait for Stage 7, so the work here isn't blocked on a pipeline
that doesn't exist yet.

**Activities**:
- Real-data verification of TIGER `MTFCC` values and Overture road `class` values against the
  documented filter (`MTFCC in (S1100, S1200)` for TIGER; `class in (motorway, trunk, primary,
  secondary)` for Overture) — the same kind of near-miss-category risk already proven real for
  POI categories in Stage 1 could apply here too, and this is the first point it's checkable.
- **Transport-only-undefined self-check**: reproduce the published per-region transport-undefined
  percentages (eastern-ok 21.2%, maricopa-az 54.6%, northern-ca 36.9%, south-central-tx 28.4% —
  recorded in Stage 1) from our own tract-level "does this tract have zero qualifying named-
  highway length" logic. This is a simple existence check on raw counts, doable the moment TIGER
  and tract polygons are loaded — the first real correctness gate, before any submission is spent.
- **Sanity-bound the transport-gap ratio** against the one piece of ground truth the challenge
  documentation gives away for free: the 0.71–1.59 cross-region ratio range (Stage 1). If our own
  per-region ratios fall wildly outside that band, that's a bug, caught with zero submissions
  spent.
- Reproduce the published tract counts per region (Stage 1), and the "every GEOID appears in
  exactly one region" invariant, as automated tests.
- **Face-validity check**: our own early computed component counts should correlate sensibly with
  intuition — dense urban tracts (downtown San Antonio, central Tucson/Phoenix metro) should show
  denser coverage; remote rural/tribal tracts should show sparser coverage. A spot map, eyeballed
  against what's already known about each region, is a cheap, real sanity check.
- **Local distribution sanity checks**: histograms of the raw counts feeding each component,
  checked for plausible shape (not degenerate) before any gap ratio is even computed.
- One-line equality check: whether `cbp_estab == cbp_estab_bus` exactly, or differs in edge cases
  (the CBP schema documents `cbp_estab` as "also the default," worth confirming directly rather
  than assuming).
- **Component correlation structure** (the phenomenology addition): once early component counts
  exist for at least one region, examine the pairwise correlation between the three raw
  components (transport, building, POI gap proxies) and each against the eventual composite. This
  tells us early whether the three components measure one underlying phenomenon, partially
  independent phenomena, or fundamentally different types of mapping failure — which directly
  informs how the Bias Discovery candidates in Stage 9 (especially component dominance and
  dispatch-blind reachability) get framed. Revisited more rigorously in Stage 7 once full gap
  values exist for all four regions.

**Deliverables**: `notebooks/01_eda.ipynb`, a short written EDA summary feeding the first entries
of `docs/scoring_assumptions.md` (created in Stage 7).

**Exit criteria**: our own transport-only-undefined percentages match the published ones within
rounding tolerance for all four regions, or a documented explanation exists for any mismatch; the
transport-gap ratio falls within the 0.71–1.59 band for all four regions.

**Exit criteria confirmed met — 2026-09-07.** Both criteria hold on live, real data across all four
regions, executed end-to-end in `notebooks/01_eda.ipynb`: the transport-only-undefined counts match
the published figures **exactly** (869/218/253/1,704 of 1,593/591/1,192/6,003 scored tracts), not
merely within rounding tolerance — achieved only after a genuine root-cause fix to the definedness
test itself (a bare spatial-join existence check silently miscounted boundary-vertex-touching road
segments; corrected to a clipped-length test, now a named requirement for this stage's own `gaps.py`
build). The transport-gap ratio falls inside `[0.71, 1.59]` in every region (0.719–1.542). Full
findings: `docs/eda_findings.md`; detailed evidence: `docs/data_manifest.md` Sections 4.21–4.27;
process record: `docs/decision_log.md`'s "Stage 5, Steps 2-13" entry. Stage 6 may begin.

---

### Stage 6 — Feature engineering

**Why**: This is the stage that turns raw joined geometry/counts into the actual analytical
variables everything downstream depends on — both the coverage-gap components themselves and the
richer feature set the explanatory model and Bias Discovery analysis need. Treating this as its
own explicit stage (rather than folding it silently into the scoring engine) is what makes the
downstream modeling honest and reviewable: every feature has a name, a definition, a place it was
built, and — new in this revision — an explicit **role** governing where it's allowed to be used.

**Activities**:
- **Core scoring features** (per tract, per component): Overture count/length, reference count/
  length, the capped-ratio gap value, and a `*_defined` boolean — for roads, buildings, and each
  POI facility sub-type plus CBP establishments. Tagged `feature_role = competition`.
- **Strata join features**: attach every relevant national-strata-table column (SVI decile,
  tribal status/sub-type, RUCA/RUCC/NCHS rurality codes, heat/wildfire/drought exposure, CVI
  pillars) to each scored tract. Tagged `feature_role = research` or `diagnostic` depending on
  where they're consumed — never `competition`, since strata data plays no role in computing the
  coverage-gap score itself.
- **Derived interaction features for Bias Discovery**, each tagged `feature_role = research`:
  - The dispatch-blind reachability signal — built here as several candidate definitions to be
    compared in Stage 9 rather than committing to one arbitrarily: a threshold-AND rule
    (`transport_gap > τ_T AND poi_gap > τ_F`), a normalized-Euclidean rule
    (`sqrt(T² + F²)/sqrt(2) > τ`), the simple product (`T × F > τ`), and a continuous "Dispatch
    Accessibility Risk Index." All four are computed; Stage 9 selects among them by
    interpretability, stability, and sensitivity analysis, not by which one seemed intuitive
    first.
  - Source-provenance features: a provenance-mix vector per tract — `osm_share`,
    `microsoft_share`, `google_share`, `other_share`, `n_sources`, `dominant_source`,
    `source_entropy` — built once Stage 2 has confirmed the real structure of the `sources` field.
  - Confidence-reporting features, split deliberately into two distinct variables rather than one:
    `confidence_reporting_rate` (the share of records in a tract with a non-missing confidence
    value — a missing value means "not reported," never "low confidence") and
    `mean_reported_confidence` (computed only among records that do report a value). Conflating
    these would condition on a non-random subset and mislead any downstream comparison.
  - Component-dominance feature: `dominant_component = argmax(transport_gap, building_gap,
    poi_gap)` per tract.
  - Definedness-pattern features: `n_components_defined` (0–3) and which specific component(s)
    are undefined — the raw material for the Measurement Eligibility Bias candidate (Stage 9).
  - Distance-to-tract-boundary for tribal edge-effect analysis, population-weighted versions of
    the gap statistics.
  - **Region as an explicit control feature**, carried alongside every derived feature — not
    because region itself is a Bias Discovery finding, but because `transport_gap` is explicitly
    not comparable across regions (Stage 1), and any pooled analysis in Stage 8 needs region
    available to control for or stratify by, so a classification-scheme artifact doesn't get
    mistaken for a vulnerability signal.
- All of this is written to one tidy, tract-indexed feature table per region
  (`data/processed/<region>-tract-features.parquet`) — the project's lightweight "feature store."
  Every column carries its `feature_role` (`competition` / `research` / `diagnostic`) as metadata,
  mirrored from `docs/schema_catalog.csv`'s `allowed_for_scoring`/`allowed_for_bias` flags. The
  scoring engine (Stage 7) is only permitted to read columns tagged `competition`; an automated
  check in `scripts/submission/build_submission.py` fails loudly if any non-`competition`-tagged
  column (in particular anything derived from an external, non-provided data source) is referenced
  anywhere in the path that produces the scored submission — this physically enforces the
  challenge's own rule that "the scored coverage gap computation must use only the datasets
  provided for this challenge."

**Tools**: DuckDB for the heavy joins/aggregations, `src/geometry.py` for all spatial-assignment
logic, `src/features.py` for the tidy feature-table assembly.

**Deliverables**: `src/features.py`, `data/processed/<region>-tract-features.parquet` (gitignored,
regeneratable), a feature dictionary entry per derived column appended to `docs/DATA_DICTIONARY.md`
and `docs/schema_catalog.csv`.

**Exit criteria**: one feature table per region, schema-validated (pandera), with every column
traceable to a definition and a `feature_role`; the scoring engine (Stage 7) reads only
`competition`-tagged columns; the explanatory model and Bias Discovery analysis (Stage 8/9) read
from this table rather than recomputing anything independently.

---

### Stage 7 — Reference Reconstruction Engine: build, test, calibrate, freeze

**Why**: This is the deterministic reconstruction at the center of the project (System A, Section
0.1). It gets the rigor a trained model would normally get — a held-out validation strategy
substitute (golden-case fixtures, since there's no real held-out label), versioned configuration,
and tracked experiments — precisely because it has no conventional training/validation loop to
lean on instead, and it ends with a hard freeze (Gate C) that everything in Stages 8–9 depends on.

**Activities — testing and freezing the spatial-assignment logic (built in Stage 6)**:
- `src/geometry.py` is the explicit, sole home for spatial-assignment logic — point-in-polygon
  (facilities), both candidate building-assignment rules (centroid-in-polygon and
  geometric-intersection), and line-clip-and-sum for roads — **built and unit-tested in Stage 6**,
  not here (Stage 6 Step 0's Ambiguity 1: Stage 6 cannot compute a single feature-table column
  without these primitives already in hand). This stage's job is to formally test the already-built
  primitives against the golden-case fixture suite below, and to **freeze**, via the calibration
  protocol, which candidate variant (e.g. centroid vs. intersection, for buildings) the scoring
  engine actually uses — not to author the primitives themselves.

**Activities — two-tier test suite, built before touching real data**:
- **Golden-case arithmetic fixtures** (`tests/test_gap_arithmetic.py`): hand-constructed inputs
  covering the formula's edge cases — `overture=0` → gap 1, `overture>=reference` → gap 0 (capped,
  never negative), `reference=0` → undefined (excluded from the mean entirely, never zeroed).
- **Golden-case geometry-assignment fixtures** (`tests/test_geometry_assignment.py`):
  hand-fabricated micro-geometries — a tract boundary polygon, one building that straddles it, one
  road that crosses it — with manually verified expected tract-assignment outputs. This is a
  distinct failure mode from arithmetic bugs, and belongs in its own fixture category.
- Both fixture tiers must pass against 3–4 hand-fabricated micro-tracts before the pipeline is
  ever run against real data.

**Activities — the scoring engine itself**:
- Formula: capped ratio `1 - min(1, overture/reference)` per component — the one component the
  challenge documentation states explicitly for the POI/HIFLD gap, treated as the working
  hypothesis for the building and transport gaps too until the discussion-board question (Stage 1)
  or the designed-experiment calibration below confirms or refutes it — with undefined components
  excluded from the mean entirely (not zeroed).
- **Open technical question resolved here**: does `poi_gap` itself follow the same "mean of
  defined parts" rule between the facilities half and the CBP-establishments half? The real
  submission template's separate `poi_defined` flag suggests yes — implement it that way and
  self-check against the template's structure.
- Build `gaps.py` (reads only `competition`-tagged columns from the Stage 6 feature tables),
  producing the composite `coverage_gap_score` per tract, calling into `geometry.py` for every
  spatial assignment.
- **Any-of-three-undefined self-check**: now that building/POI definedness logic exists, reproduce
  the published "at least one component undefined" percentages (Stage 1) — a genuinely different
  statistic from Stage 5's transport-only-undefined check.
- **Gold-standard manual validation set**: pick ~10 small, easy-to-eyeball tracts spread across
  regions and strata, and for each one build a small validation artifact — a rendered map
  comparing Overture vs. the reference layer, a screenshot, the pipeline's own computed values,
  and a short manual note on agreement.

**Activities — submission discipline, calibration, and experiment tracking**:
- A local pre-submission validator (row count, GEOID set, value range, no blanks) runs before
  every upload.
- **Submit the first real region early, deliberately, as a measurement instrument, not only once
  it's polished.** As soon as the eastern-ok scorer clears its own arithmetic tests, geometry
  tests, transport-only-undefined check, and a first-pass building/POI validation — even before
  every open formula question is resolved — submit it. The goal at that point isn't a good score,
  it's early information about submission shape, score magnitude, and whether the overall
  interpretation is broadly correct, cheaply, before more work is built on top of a possibly wrong
  foundation.
- **MLflow logging has an explicit two-step discipline, not an implicit one.** Public RMSE is not
  available to the pipeline automatically — it only exists after checking the Zindi leaderboard by
  hand, and assuming this gets copied into MLflow "automatically" is exactly the kind of thing
  that quietly gets skipped under deadline pressure. The actual workflow: immediately after
  uploading a submission, call `log_submission(params, rmse=None)` to create the MLflow run with
  its parameters (formula/assignment choices) and artifacts (the submission CSV, a
  `docs/scoring_assumptions.md` snapshot) logged right away; once the leaderboard score posts,
  call `log_submission_result(run_id, rmse)` to backfill the metric. Every submission gets both
  calls before it's considered "logged" — this is a checklist item, stated explicitly here rather
  than left as an assumption the tooling would somehow handle on its own.
- **Designed-experiment calibration, with an explicit statistical-noise discipline this project
  did not originally have.** Because a submission scores against the whole combined test set, hold
  three regions at a fixed, already-trusted value across a submission pair and vary only the
  candidate formula/assignment rule in the fourth. The RMSE delta between that pair is
  attributable entirely to the change in that one region — in principle. In practice, the public
  leaderboard RMSE for any candidate is itself a noisy estimate over a finite sample (~30% of each
  region's tracts), and repeatedly querying that noisy metric across dozens of isolated-region
  trials — even with zero fabricated per-tract labels — is a real multiple-comparisons risk,
  distinct from (not solved by) the earlier rejection of residual ML calibration. Concretely:
  northern-ca's public slice is only ~175 tracts; for a bounded [0,1] metric with plausible
  per-tract error variability on the order of 0.05–0.15, a rough √n argument puts the standard
  error of an RMSE estimate there around 0.005–0.01 — an observed delta smaller than that should
  not be trusted as a real effect. This project does not currently have a validated per-tract error
  variance to compute this precisely, so instead of trusting the rough number, it establishes an
  **empirical noise floor directly**: early in the calibration process, resubmit one already-scored
  variant unchanged and observe the RMSE jitter between the two identical runs. Any calibration
  "win" smaller than that observed jitter is treated as noise, not signal. Every isolated-region
  calibration win is additionally **required to be reconfirmed by a full four-region combined
  submission before it's treated as settled** — the cross-region confirmation step is a gate, not
  an optional follow-up. This is a real, acknowledged limitation of the calibration protocol, not
  a solved problem, and it is documented honestly as such in the "alternative weightings
  considered" section of the final writeup — which, done well, is itself strong evidence of
  methodological maturity.
- **The calibration protocol is explicitly tiered, to prevent the leaderboard from quietly
  becoming a hyperparameter optimizer**:
  - **Tier A — structural uncertainties**: only questions that change the actual implementation
    logic (spatial-assignment rule, whether the capped-ratio formula applies to building/transport
    gaps, POI half-definedness). Resolved first, and only here does the isolated-region factorial
    design run at its fullest extent.
  - **Tier B — plausible sensitivity analysis**: run only after Tier A is settled — small,
    well-motivated variations around the Tier-A-confirmed logic.
  - **Tier C — ensembling and small numerical variants**: run last, and scoped narrowly (below).
  The leaderboard is a validation instrument for choosing among a small number of independently
  motivated, interpretable candidates — not a training set to be searched over freely. That
  distinction governs every choice in this stage.
- **Ensembling, scoped narrowly and with an explicit physical-meaning guardrail.** Ensembling is
  legitimate **only when candidates differ in a continuous formula parameter** (e.g., a slightly
  different capping/saturation curve) — a weighted average of two such curves is interpretable and
  corresponds to a coherent underlying rule. It is **not** applied to candidates that differ in a
  *discrete* spatial-assignment rule: a 70/30 blend of "building counted if its centroid falls in
  the tract" and "building counted if it merely intersects the tract" does not correspond to any
  rule anyone could explain as "here's what we actually measured" — it would be numerically
  well-defined but physically meaningless, and would risk reading, under scrutiny, as exactly the
  leaderboard curve-fitting this project works hard to distinguish itself from. The
  spatial-assignment rule is therefore always a single, evidence-selected discrete choice, never a
  blend target. Where ensembling of formula-parameter variants is used, weights are restricted to
  a small, fixed grid — `{0, 0.25, 0.5, 0.75, 1}` — between at most two or three independently
  plausible candidates, each evaluated by its own public RMSE through the same designed-experiment
  protocol as everything else (not fit against a hidden label — there still isn't one). If an
  ensemble candidate wins on demonstrated RMSE under this scoped process, it is fully eligible to
  be one of the two final submissions.
- **Considered and explicitly rejected: residual ML calibration** (fitting LightGBM/XGBoost/
  CatBoost to "learn systematic residuals" between our deterministic computation and the true
  score). As stated precisely in Section 0.2: this is statistically infeasible given a
  300-submission budget queried against 9,379 unknown per-tract values, not impossible in some
  absolute sense — there is no way to compute a per-tract residual to train against at any
  achievable sample size here. The valid version of this instinct is the tiered designed-experiment
  calibration and narrowly-scoped ensembling above — model selection over a few interpretable
  variants using aggregate RMSE feedback, not regression on residuals that were never computable.
- **Final two-submission selection**: pick the top two candidates by demonstrated public RMSE
  among genuinely plausible variants (i.e., ones that also pass every self-validation check above
  and have cleared the cross-region confirmation gate, not just whatever scored lowest by chance)
  — not two "meaningfully different" variants chosen as a deliberate hedge. The public/private
  split is a random 30/70 partition of the same fixed list of tracts, so there is no real
  distribution-shift risk to hedge against by deliberately picking a weaker second candidate. One
  narrow, legitimate exception: if two candidates are within a small margin of each other on
  public RMSE and the difference is plausibly attributable to northern-ca's small public sample
  size (or is smaller than the empirical noise floor established above) rather than a real formula
  difference, both are reasonable picks and the choice between them can be made on which is
  better-evidenced/documented.
- **Submission budget, defined so it is provably capped at 300, not approximately so.** Reserve is
  defined as `300 − actual spend to date`, computed dynamically, never as an independently-quoted
  range that could be added on top of the other categories:

  | Category | Approx. submissions | Purpose |
  |---|---|---|
  | Smoke test | 1 | Confirm the platform accepts the file format |
  | Early eastern-ok measurement submission | 1 | Cheap, deliberately early information about score magnitude and interpretation correctness |
  | Tier A — structural calibration (formula variant × spatial-assignment rule, per region, three regions held fixed each time) | ≤ 80 | Isolate each region's marginal RMSE effect for each open formula question |
  | Noise-floor calibration (resubmit one already-scored variant unchanged) | 1–2 | Establish the empirical jitter threshold below which a delta isn't trusted |
  | Cross-region confirmation (mandatory gate on every Tier A "win") | ≤ 15 | Confirm an isolated-region win still wins combined before it's treated as settled |
  | Tier B — sensitivity analysis (only after Tier A is settled) | ≤ 20 | Smaller, well-motivated variations around the confirmed logic |
  | Tier C — ensemble-weight search (formula-parameter variants only) | ≤ 15 | Test the small fixed weight grid on at most two or three plausible candidates |
  | Regression checks after a pipeline/feature-engineering change | ≤ 10 | Cheap insurance against silent regressions as code evolves |
  | **Subtotal (structural work)** | **≤ 145** | |
  | **Reserve** | **300 − actual spend** (typically ~150+ remaining) | Held back deliberately for anything discovered late — a discussion-board answer, a Stage 2 audit finding, a Stage 8 finding that suggests a formula refinement — without panic-budgeting near the deadline |

**Activities — the scoring freeze itself (Gate C)**:
- Once the discussion board is answered (or a firm cutoff passes) and the calibration protocol
  above has produced a confirmed formula/assignment/ensemble choice, produce a **versioned scoring
  artifact**: `scoring/v1/formula.yaml` (the exact chosen formula and parameters), `scoring/v1/
  assumptions.md` (a frozen snapshot of `docs/scoring_assumptions.md` at freeze time), `scoring/v1/
  checksum.txt` (a hash of the frozen `gaps.py` logic). The actual scored output
  (`coverage_scores_v1.parquet`) stays gitignored like other large data, but its checksum and
  metadata are committed. Every submission and every downstream artifact (Stage 8's training data,
  Stage 9's analysis) then carries `scorer_version`, `feature_version`, and `git_commit` in its own
  metadata, so any result can be traced back to the exact frozen logic that produced it. After this
  point, no change to scoring logic happens without a reproducible regression test demonstrating a
  defect (Gate C, Section 2).
- **Automate the flattened submission notebook rather than hand-maintaining it in parallel with
  `src/`.** Build `scripts/submission/build_submission_notebook.py`, which takes the approved,
  frozen source modules, strips project-local imports, inlines the necessary functions, writes the
  flattened `submission/coverage_gap_solution.ipynb`, executes it against the golden-case fixtures,
  and validates the output schema. The flattened notebook becomes a **generated artifact**, not a
  hand-edited one — this closes a real synchronization risk that would otherwise exist between the
  modular portfolio code and the actual Zindi-review artifact.

**Deliverables**: `src/gaps.py`, `tests/test_gap_arithmetic.py`, `tests/test_geometry_assignment.py`,
`docs/scoring_assumptions.md`, `scoring/v1/` (formula.yaml, assumptions.md, checksum.txt),
`scripts/submission/build_submission_notebook.py`, `mlruns/` (gitignored), `docs/experiments/
mlflow_runs_export.csv` (committed flat export), the two final submission CSVs.

**Exit criteria (Gate B → Gate C)**: both fixture tiers green; every self-check from Stage 5 and
this stage passes; the gold-standard validation set agrees; `docs/scoring_assumptions.md` has a
validation status for every tracked ambiguity; the noise floor is established; every Tier A win is
cross-region-confirmed; the versioned scoring artifact is produced and the engine is frozen; final
two submissions selected per the rule above; the generated flattened notebook runs top-to-bottom
against fixtures.

---

### Stage 8 — Bias Discovery hypothesis mining & Explanatory/Unsupervised Equity Modeling

**Why**: This is where the Equity Research Engine (Section 0.1) generates and screens candidate
disparity patterns, using both unsupervised structure-finding and honest explanatory modeling —
all built against the **frozen** Stage 7 output (Gate C), so nothing here is training against a
moving target. It's explicitly renamed from an earlier "diagnostic model" framing to "Explanatory
& Unsupervised Equity Modeling" because that name is more defensible under scrutiny: it states
plainly what the ML in this project actually does and doesn't do.

**Activities — hypothesis funnel (structures the rest of this stage and Stage 9)**:
- Start from the full 232-column data dictionary (Stage 3) and Stage 6's derived features. Screen
  down: 232 columns → roughly 50 plausible hypotheses (domain-driven, not exhaustive
  combinatorics) → univariate screening against the composite and per-component gaps → roughly 15
  promising patterns → a novelty check against the Bias API replica (built later in this stage) to
  discard anything that just restates one of the five official metrics → roughly 5 serious
  candidates → each scored on the **Bias Candidate Rubric** below → 2–3 pre-registered hypotheses
  carried into Stage 9's confirmatory statistical analysis → the flagship narrative.
- **Bias Candidate Rubric**, mirroring the actual judging weights exactly (Impact 30 / Novelty 25
  / Evidence 25 / Reproducibility 20, summing to /100): every candidate that survives screening is
  scored on this rubric before being prioritized, so candidate selection is a documented,
  reproducible process rather than "which one do we like."

**Activities — two-mode clustering, deliberately separated to avoid a tautology**:
- **Cluster A — vulnerability/context archetypes.** Features: SVI, CVI, rurality codes, hazard
  exposure, population/density, tribal characteristics. **Coverage-gap variables are explicitly
  excluded from this clustering.** The question this asks: which community archetypes experience
  the highest mapping gaps — characterized *after* clustering, by joining the resulting archetypes
  back to the gap scores. Clustering on the gap components themselves and then observing "this
  cluster has high gaps" would be close to tautological, since the gap was a clustering input; this
  mode avoids that entirely.
- **Cluster B — mapping-gap archetypes.** Features: transport gap, building gap, POI gap
  (facilities and establishments halves separately), and the definedness pattern. This asks a
  different question: what *types* of mapping failure exist, characterized afterward against
  context features (SVI, tribal, hazard). This tells us who experiences which kind of gap, not
  just how much.
- **Method follows data, not the reverse**: start with PCA inspection and a k-means baseline with
  silhouette-based k selection and basic stability testing (repeated runs, bootstrap resampling of
  cluster assignments) for both modes. HDBSCAN is adopted only if the data actually shows
  non-convex or variable-density cluster structure that k-means demonstrably fails to capture —
  not chosen upfront.

**Activities — explanatory model (System C), trained only against the frozen Stage 7 snapshot**:
- The stated research question this model answers: *can the structural disparity patterns in our
  reconstructed coverage data be explained by independently defined vulnerability and geographic
  characteristics?* Never: does this model predict the organizer's hidden true score (it can't,
  and isn't asked to).
- **Region is included as an explicit control feature**, not omitted. Because `transport_gap` is
  not comparable across regions (Stage 1/6) and the composite score is heavily influenced by it, a
  pooled four-region model risks SHAP surfacing what's actually a region-level classification
  artifact and reporting it as an equity finding. Mitigation, applied together: region is always
  present as a feature so the model and SHAP can separate its effect from genuine
  vulnerability-feature effects; per-region models are also trained and compared against the
  pooled model as a robustness check; and **any SHAP finding substantially driven by
  `transport_gap` is flagged for extra scrutiny — checked against the per-region models and the
  Stage 5/7 component-correlation analysis — before it is allowed into the flagship Bias Discovery
  narrative**, precisely because that specific component has a known, documented,
  non-vulnerability-related source of cross-region variation.
- Train three candidate model families against the frozen coverage-gap scores: a linear/Ridge
  baseline, a Random Forest, and a LightGBM gradient-boosted regressor. Evaluate with repeated
  k-fold cross-validation (R², MAE) — this model genuinely does have a real target (our own frozen
  output), so ordinary CV is legitimate here in a way it wasn't for Stage 7.
- **Hyperparameter optimization**, deliberately scoped to this stage only (Stage 7's Reference
  Reconstruction Engine still has no valid target to tune against): tune LightGBM and Random
  Forest with Optuna, logged as nested MLflow runs (parent = HPO study, each trial = a child run),
  fixed seed and CV folds for reproducibility.
- **Ensembling the explanatory models** (a different, legitimate use of ensembling from Stage 7's
  scoped formula-ensembling — this one has a real target to validate against): compare a simple
  averaging ensemble of the three tuned models against the best single model by cross-validated
  performance; adopt whichever wins, honestly, rather than defaulting to the ensemble. Stacking is
  adopted only if it demonstrably beats both.
- **A hard gate on whether this model ships at all**: if the winning model's explanatory power is
  weak (R² near zero against our own computed scores), the honest outcome is to say so in
  `docs/model_card.md` — "the explanatory model was evaluated and found insufficiently
  explanatory, so it was not deployed" — rather than forcing a weak model into the writeup or the
  app for its own sake. That is a more senior outcome than deploying ML for its own visual appeal.
- Use SHAP (on whichever model wins) to produce global and local feature-importance evidence, with
  the framing discipline from Section 0.2 applied everywhere: "factors associated with our
  reconstructed coverage-gap measure," never "causes."
- Log every HPO trial and model/ensemble comparison to the `diagnostic-modeling` MLflow
  experiment. Register the winning model (MLflow registry or a `joblib` artifact) — this is what
  the deployed app's Equity Profile Explorer panel loads, only if the gate above is passed.

**Deliverables**: `src/diagnostics.py` (clustering, training, HPO, ensembling, SHAP), a
registered/saved model artifact (if the gate is passed), `docs/model_card.md` (including the
epistemic-framing statement from Section 0.2 and the go/no-go decision from the gate above),
contributions to `notebooks/04_bias_discovery.ipynb`, MLflow experiment entries.

**Exit criteria**: the hypothesis funnel has produced 2–3 pre-registered candidates for Stage 9;
both clustering modes are complete, characterized, and crossed against vulnerability strata; the
explanatory model's go/no-go gate decision is made and documented; any transport-gap-driven SHAP
finding has been checked against per-region models before being passed to Stage 9.

---

### Stage 9 — Statistical confirmation & Bias Discovery writeup

**Why**: A disparity claim without a confidence interval, a significance test, and a correction
for having screened many candidates reads as anecdotal to a judging panel scoring 25% on Evidence.
This stage takes the 2–3 pre-registered candidates from Stage 8's funnel and either confirms them
rigorously or drops them — it does not introduce new candidates (Gate D).

**Bias Discovery candidate pool, after the Stage 8 funnel and rubric scoring**:

| Tier | Candidate | Why it's here |
|---|---|---|
| **A — leading flagship candidates** | **Measurement Eligibility Bias**: are vulnerable communities systematically more likely to have one or more coverage-gap components *undefined* (not just worse-scored)? Computed as `P(component undefined \| SVI, tribal, rurality, hazard)` per component, using the definedness-pattern features from Stage 6. | Structurally different from every other candidate — it's rooted directly in the challenge's own "excluded from the mean, not zeroed" scoring rule, which the automated Bias API scorecard cannot see (it operates only on gap *values*, never on which components existed to be measured at all). Highly novel, highly reproducible, and it reframes the whole project's central finding from "some places are worse-mapped" to "some places are less *measurable* in the first place." |
| A | **Dispatch-blind reachability**: the compound transport × facility inaccessibility signal, defined rigorously via the multi-definition comparison built in Stage 6 and selected in Stage 8/9 by interpretability, stability, and sensitivity analysis rather than committed to arbitrarily. | Impact is about as concrete as this challenge gets — can emergency services actually reach this tract — and it's an interaction the five independent API metrics structurally cannot see, since they never combine components. |
| A | **Source provenance × vulnerability**: the provenance-mix vector (Stage 6) regressed against gap, both alone and with SVI/rurality/hazard as covariates — the second model distinguishes "source composition reflects geography" from "source composition matters independent of geography." | High on all four criteria; genuinely outside the 5 fixed metrics; the covariate-adjusted model is a real methodological upgrade over a simple crosstab. |
| **B — strong secondary** | Confidence reporting-rate vs. reported-confidence-value, kept as two distinct questions (Stage 6) | Avoids the missing-vs-low conflation that would otherwise undermine this candidate; highest novelty of anything considered, invisible to the entire scoring framework, not just the 5 official metrics. |
| B | Component dominance (`argmax` of the three gaps, crossed against vulnerability) | Concrete, tangible emergency-response narrative (tribal-rural → routing problem; high-SVI-urban → facility-visibility problem) that complements dispatch-blind without duplicating it. |
| B | Tribal legal/statistical/union sub-type + distance-to-boundary edge effect | Real dispatch/jurisdiction-confusion story, needs the distance-to-boundary geometry work from Stage 6 to execute well. |
| B | Population exposure vs. tract-weighted disparity, anchored to specific named tracts (e.g. "tract `<GEOID>`, population `<N>`, `<SVI/tribal/hazard status>`, diluted in the tract-mean statistic by `<M>` nearly-empty rural tracts nearby") | A real finding once anchored to concrete places; an abstract statistical critique otherwise. |
| **C — exploratory, kept only if data supports them** | Colonias in South-Central TX (needs an external registry, permitted for this prize only) | Named example in the challenge's own documentation, capping its novelty somewhat. |
| C | CVI pillar decomposition | Restatement risk unless it clearly decomposes past the composite metric. |
| C | RUCA vs. RUCC vs. NCHS disagreement | Touches the API's own rural/urban stratum; risks reading as a restatement unless the disagreement itself is the story. |
| **Dropped** | Wildfire-rebuilt areas | Only a single current-state building snapshot exists, no time-series — "rebuilt" cannot be distinguished from "always looked like this" from provided data alone. |
| **Dropped** | Heat-island × SVI | Too close to what the Climate-Justice Composite metric already computes. |

Two, at most three, focused and deeply-evidenced findings beat six shallow ones against a rubric
that rewards quantified, reproducible, named-tract evidence — Tier A is the candidate *pool* the
funnel and confirmatory analysis run against, not a commitment to write up all three; the actual
winner(s) emerge from the data, not from preference stated today.

**Activities — confirmatory statistical discipline**:
- Explicit separation between **exploration** (Stage 8's broad screening — candidate discovery,
  no correction needed, results are hypotheses, not claims) and **confirmation** (this stage —
  bootstrap confidence intervals, permutation tests for group differences, effect sizes, and a
  **Benjamini-Hochberg false-discovery-rate correction** applied across the small, pre-registered
  set of hypotheses actually tested here). This distinction — screen broadly, then test a small
  number of pre-specified hypotheses with correction — is what keeps the eventual "if we test
  enough things, something looks significant by chance" risk from undermining the Evidence score.
- Moran's I / Getis-Ord Gi* only where a spatial-clustering claim is actually made (conditional on
  the flagship finding needing it, not a default step) — shared helper functions live in
  `src/statistics.py`.
- **The local Bias API replica** (`src/bias_api_replica.py`) — the five official metrics
  (Coverage Disparity Ratio, POI Desert Index, Emergency Access Gap, Road Network Equity Ratio,
  Climate-Justice Composite), replicated locally from the frozen Stage 7 output. This is the
  novelty-screening step in the hypothesis funnel above, and a redundancy guard: if a pattern
  turns out to just restate one of these five metrics, it's caught here, before the writeup.
- **Confirmed real Bias Scorecard stratification grid (empirical, 2026-09-07)**. The Stage 0.5
  smoke-test submission (constant `0.5`, `docs/decision_log.md`) surfaced the live scorecard's own
  "Show Scoring Rubric" breakdown directly from Henry's account — nine stratum rows, not just the
  five metric names: Rural vs Urban, Tribal vs Non-Tribal, High Social Vulnerability, High Climate
  Vulnerability, Summer Drought, Winter Drought, Wildfire Hazard, Summer Heat, and an intersectional
  High Hazard + High Vulnerability row. This confirms drought is scored split Summer/Winter and heat
  only as Summer Heat, plus an intersectional row beyond the five headline metric names — finer than
  the README's five-metric summary implies on its own, and now confirmed directly rather than
  inferred from a third party's leaderboard screenshot (superseding the unconfirmed 2026-09-03 note
  in `verification-findings.md`). `src/bias_api_replica.py` must replicate this exact 9-row stratum
  grid, not just the 5 metric formulas in the abstract — a redundancy check that only reproduces the
  5 metrics at their coarsest grouping could still miss a finding that only restates one of them once
  split by, e.g., Summer vs. Winter Drought specifically.

**Deliverables**: `src/statistics.py`, `src/bias_api_replica.py`, `docs/bias_discovery.md` filled
in, supporting figures in `docs/figures/`, entries in the `bias-discovery` MLflow experiment
(hypothesis ID, stratum, effect size, CI, adjusted p-value, spatial statistic where applicable).

**Exit criteria (Gate D)**: every quantitative claim in the Bias Discovery writeup has an attached,
FDR-corrected confidence interval or significance statement; the Bias API replica confirms no
flagship finding is a restatement of one of the five official metrics; every kept candidate has a
named, quantified "who's affected" statement; the writeup is frozen once drafted — no new
candidate is added without re-running the funnel.

---

### Stage 10 — CI/CD

**Why**: A green build badge and an enforced test gate are the fastest way to demonstrate that
"reproducible" isn't just a claim in the README — and it directly protects the two-tier test suite
and the generated submission notebook from silently regressing while the project is actively
iterated on for two months.

**Activities**: GitHub Actions workflow running, on every push and PR: `pandera` schema checks
against a small cached data sample, the full two-tier pytest suite, a lint pass (`ruff`), a
notebook-execution smoke test for `00_data_audit.ipynb`/`01_eda.ipynb` against fixture data, and —
new — **execution of `scripts/submission/build_submission_notebook.py` followed by running the
generated flattened notebook against fixtures**. This proves, on every change, that the modular
portfolio code and the actual Zindi-review artifact still agree, closing the synchronization risk
that motivated automating the notebook generation in the first place.

**Deliverables**: `.github/workflows/tests.yml`, a passing badge referenced at the top of
`README.md`.

**Exit criteria**: CI is green on `main`, including the generated-notebook smoke test; branch
protection requires it to pass before merge.

---

### Stage 11 — Documentation

**Why**: Consolidated required content for the Best Documentation prize (the challenge's own prize
description names these almost as a rubric, treated as non-negotiable): edge cases, alternative
weightings actually tried and why rejected, full ETL + architecture diagram, runtime per script,
public + private RMSE, error handling, reproducibility.

**A real code-review trap, designed around from Stage 7 rather than retrofitted here**: the
project's own rules state directly, "Custom packages in your submission notebook will not be
accepted." The flattened, generated `submission/coverage_gap_solution.ipynb` (Stage 7) is the
artifact that actually gets submitted if code is ever requested — built and CI-tested well before
this stage, not assembled under deadline pressure.

**Concrete artifacts**:
- `docs/methodology.md` — overview, the four-system architecture diagram (Section 0.1), ETL,
  full formula definition per component, edge-case handling, alternative weightings considered and
  why rejected (including the honestly-documented calibration-noise limitation from Stage 7),
  validation and performance, error handling, reproducibility pointer, Bias Discovery pointer.
- `docs/DATA_DICTIONARY.md` and `docs/schema_catalog.csv` (Stages 3/6).
- `docs/data_manifest.md` (Stage 1) and `src/schemas.py`'s contracts, documented inline (Stage 2).
- **A dynamic risk register** (`docs/risk_register.md`): each entry carries an ID, description,
  probability, impact, a probability×impact score, mitigation, status, an owner, and a last-
  reviewed date — not a static table filled once. Example entry: `R-004 — Incorrect CRS axis
  order — Probability: High, Impact: Critical, Score: high, Mitigation: centralized CRS utility in
  src/geometry.py with its own unit test, Status: mitigated`. Also covers GEOID-as-integer
  truncation, ACS housing units in a denominator, hospital inclusion in the facilities count,
  zeroing vs. excluding undefined components, unfiltered road classes.
- **`docs/scoring_assumptions.md`** (Stage 7) — what the scorer does and why, one row per genuine
  ambiguity, evidence, hypothesis, validation status, linked submission evidence.
- **`docs/decision_log.md` (new, distinct from `scoring_assumptions.md`)** — why an implementation
  choice was made over its alternatives, which is a genuinely different document with a different
  audience than "what the scorer does." Example: `Decision D014 — Date: [date] — Question: how
  should boundary-crossing buildings be assigned? — Options: A. centroid, B. intersection, C.
  area-weighted split — Decision: B — Evidence: [link to the relevant calibration experiment] —
  Consequences: [what this implies downstream]`.
- `notebooks/03_building_vs_housing_analysis.ipynb` — why ACS housing units are excluded from any
  denominator, shown visually rather than only asserted in prose.
- `docs/reproducibility.md` — OS, CPU, RAM, Python version, exact package versions, full pipeline
  runtime per script/notebook per region, every random seed used anywhere, the Overture release
  pinned (`2026-08-19.0`), and every `git_commit`/`scorer_version`/`feature_version` tuple that
  appears in a logged artifact. Includes a **reproducibility demo** in the README itself — a short
  `git clone` / `pip install` / `python -m src.cli audit` / `python -m src.cli score --region
  eastern-ok` / `python -m src.cli validate-submission` sequence ending in a stated output
  checksum, so a reviewer can literally verify they reproduced the same result.
- `docs/model_card.md` (Stage 8) — training data (our own frozen computed scores), intended use
  (explanation only), the go/no-go gate decision, and known limitations (including the
  region-confound mitigation from Stage 8).
- `docs/experiments/mlflow_runs_export.csv` — flat, committed export of every MLflow run across all
  three experiments (`competition-scoring`, `diagnostic-modeling`, `bias-discovery`).
- `PROJECT_BLUEPRINT.md` (this document) linked from `README.md` as the architecture reference.
- **A README written as a short case study**: problem, approach, one headline finding with a
  number, the live app link, the reproducibility demo, how to reproduce.
- **Clean, meaningful commit history**, built continuously — small, well-scoped commits, matters
  directly if selected for the top-10 code-review window (Gate E).

**Exit criteria**: every required Best Documentation element above is present and filled in, not a
skeleton.

---

### Stage 12 — Deployment: the Presentation/Deployment Engine (System D)

**Why**: A static screenshot or a notebook a recruiter has to clone and run is a much weaker
portfolio signal than a live link that genuinely responds to interaction. This stage has a real
dependency the earlier draft of this blueprint missed: the app needs actual data to deploy with,
and that data was entirely gitignored — fixed explicitly below, not left for discovery at
deployment time.

**Activities**:
- **Fix the data-availability gap first.** `data/processed/` and `models/` are gitignored for good
  reason (multi-GB source-derived caches shouldn't be in git), but Streamlit Community Cloud
  deploys directly from the GitHub repository, so the app as originally scoped would have nothing
  to serve. Resolution: commit a small, derived **app data bundle** — the final frozen, scored
  tract tables (all 9,379 rows, a handful of columns each — a few MB, nothing like the multi-GB
  source layers) and the serialized winning explanatory model (if Stage 8's gate was passed) — to
  `app/data/`, as an explicit, narrow exception to the general gitignore rule, clearly commented in
  `.gitignore` explaining why this specific small bundle is committed while everything upstream of
  it is not.
- Build a Streamlit app (`app/explorer.py`), entirely static-data-driven: reads only from the
  committed `app/data/` bundle. **No live DuckDB querying, no live S3 access, no multi-GB data
  loaded at request time** — every number the app shows was computed upstream and frozen.
- The app's home page visually narrates the whole pipeline (Data → Reference Comparison →
  Coverage Gap → Equity Analysis → Discovery) and offers three ways to explore: **by tract**
  (GEOID, region, each component gap, defined/undefined status, SVI/CVI/rurality/hazard strata),
  **by community archetype** (the Cluster A/B results from Stage 8 — high-SVI, tribal, high
  wildfire, high heat, rural, and so on), and **by finding** (a dedicated view per flagship Bias
  Discovery result — Measurement Eligibility Bias, Dispatch-Blind Reachability, Source
  Provenance × Vulnerability — with its own supporting map and statistics).
- **The explanatory-model panel is renamed "Equity Profile Explorer," not "What-If."** A user
  selecting a hypothetical strata profile and getting a number back could easily read "what-if" as
  a causal claim ("if I change SVI, coverage becomes X") — which the model was never built to
  support (Section 0.2). The panel instead states its output as association: "this profile
  resembles tracts where the reconstructed coverage gap tends to be higher/lower," with its SHAP
  explanation shown as contributing factors, not causes.
- **Out-of-distribution safety on that panel.** A user can select an implausible combination (e.g.
  extreme rurality with enormous population density). The model will still return a number, but
  that doesn't make it meaningful. The app computes a simple distance-to-nearest-training-
  observation measure for the selected profile and displays "outside observed data distribution"
  when the profile is extrapolative, alongside the observed ranges for each input — a concrete,
  cheap safeguard against a misleadingly confident-looking output.
- Publication-quality maps (coverage-gap choropleth, POI-desert map, road-equity map, the
  dispatch-blind map, a hotspot map for the spatial finding) built here for double duty in both the
  app and `docs/figures/` — only the ones actually needed for the flagship findings, not every map
  imaginable.
- Deploy to Streamlit Community Cloud (free tier) from the `main` branch. Built without any
  assistant-branding artifacts, consistent with the project's sole-authorship requirement.

**Deliverables**: `app/explorer.py`, `app/data/` (the small committed bundle), `app/
requirements.txt`, a live URL linked prominently at the top of `README.md`.

**Exit criteria**: the deployed app loads from a cold start with real data (not a broken/empty
state), the map filters and click-through work, the Equity Profile Explorer panel returns a live
SHAP-based association explanation with an out-of-distribution warning where applicable, and the
app's own UI copy makes clear which panel is precomputed fact and which is an explanatory model's
output. This stage needs Stages 6–9 complete (feature tables, frozen scores, and — if it passed
its gate — the explanatory model) before it can go live.

---

### Stage 13 — Final submission & portfolio finalization

**Why**: The competition and the portfolio both need a clean, deliberate close.

**Activities**: final two-submission selection per Stage 7's rule; final commit-history cleanup
pass; confirm the generated `submission/coverage_gap_solution.ipynb` runs top-to-bottom with only
public packages from a clean environment and matches the frozen `scoring/v1/` checksum; final
read-through of every `docs/` file for the sole-authorship requirement (Henry Otsyula as the
stated author throughout, no mention of any AI assistant or other third party anywhere in the
shipped repository); tag a `v1.0` release on GitHub.

**Deliverables**: both final submissions uploaded to Zindi; a tagged `v1.0` GitHub release.

**Exit criteria (Gate E, continuously true from Stage 7 onward, verified one final time here)**:
both final submissions uploaded; repo, docs, and deployed app all in their finished state; project
is fully code-review-ready with zero prep needed if selected for the top-10 review window.

---

## 4. Repository structure

```
bias-bounty-mapping-equity/
├── README.md                       case-study narrative, live app link, headline finding,
│                                    reproducibility demo with checksum
├── PROJECT_BLUEPRINT.md            this document — architecture reference
├── Makefile                        thin convenience wrapper around src/cli.py
├── requirements.txt
├── .gitignore                       explicitly comments the app/data/ exception (Stage 12)
├── configs/                         small, flat — local-environment-only settings
├── src/
│   ├── cli.py                       canonical command-line interface (python -m src.cli ...)
│   ├── config.py                   region/layer/formula/seed constants
│   ├── schemas.py                  pandera contracts per layer (Stage 2)
│   ├── io.py                       GeoParquet ingestion + schema enforcement (GEOID etc. as str)
│   ├── geometry.py                  CRS validation, equal-area projection, length/area utilities,
│   │                                AND the sole home for spatial-assignment logic
│   ├── features.py                 feature-table assembly + feature_role tagging (Stage 6)
│   ├── gaps.py                     the Reference Reconstruction Engine (all three components),
│   │                                reads only feature_role=competition columns
│   ├── statistics.py                bootstrap CI / permutation test / FDR correction / Moran's I
│   │                                & Gi* helpers
│   ├── diagnostics.py               two-mode clustering + explanatory model + HPO + ensembling
│   │                                + SHAP (Stage 8)
│   ├── bias_api_replica.py         local replica of the 5 official Bias Score metrics
│   ├── viz.py                      shared plotting helpers (a module, not a package)
│   └── validate.py                 submission validator + the self-check suite
├── app/
│   ├── explorer.py                  the deployed Streamlit app — static-data-driven only
│   ├── data/                        small committed app-data bundle (frozen scores + serialized
│   │                                model) — the one deliberate exception to gitignoring data
│   └── requirements.txt
├── notebooks/
│   ├── 00_data_audit.ipynb          data-integrity EDA: schemas, nulls, geometry validity, CRS
│   │                                consistency, duplicate GEOIDs (all regions/folders)
│   ├── 01_eda.ipynb                 phenomenology EDA: self-checks, distributions, component
│   │                                correlation structure
│   ├── 02_pipeline_dev.ipynb        interactive pipeline development, one region at a time
│   ├── 03_building_vs_housing_analysis.ipynb
│   └── 04_bias_discovery.ipynb
├── scripts/
│   ├── audit/audit_bucket.py        all 4 regions + strata/ + boundaries/
│   ├── download/download_data.ps1
│   └── submission/
│       ├── build_submission.py              builds the scored CSV, enforces feature_role
│       └── build_submission_notebook.py     generates the flattened reproduction notebook
├── submission/
│   └── coverage_gap_solution.ipynb  GENERATED artifact — not hand-edited, see build script above
├── scoring/
│   └── v1/                          versioned scoring artifact, produced at the Stage 7 freeze
│       ├── formula.yaml
│       ├── assumptions.md
│       └── checksum.txt
├── tests/
│   ├── test_gap_arithmetic.py        golden-case ratio/formula edge cases
│   ├── test_geometry_assignment.py   hand-fabricated micro-geometry fixtures
│   └── test_schemas.py               pandera contract tests against fixture data
├── docs/
│   ├── methodology.md
│   ├── bias_discovery.md
│   ├── model_card.md
│   ├── decision_log.md              NEW — why we chose X over Y, distinct from scoring_assumptions
│   ├── data_manifest.md
│   ├── DATA_DICTIONARY.md
│   ├── schema_catalog.csv           includes feature_role / allowed_for_scoring / allowed_for_bias
│   ├── scoring_assumptions.md       what the scorer does; ambiguity tracker
│   ├── reproducibility.md
│   ├── risk_register.md             dynamic: ID/probability/impact/score/status/owner/reviewed
│   ├── validation/                  the ~10-tract gold-standard manual validation set
│   ├── experiments/
│   │   └── mlflow_runs_export.csv  flat export across all three MLflow experiments
│   └── figures/
├── data/                             gitignored local cache (raw/interim/processed)
├── mlruns/                           gitignored MLflow tracking store
├── models/                           gitignored explanatory-model artifacts (or MLflow registry)
├── submissions/                      gitignored except the two final selections
└── .github/workflows/tests.yml       CI: schemas + tests + lint + notebook smoke test +
                                       generated-submission-notebook smoke test
```

**Note on `scripts/` (recorded at Stage 4, the repository-restructure stage, so this deviation from
a naive reading of the tree above is on record rather than left as tribal knowledge)**: the tree
above names `scripts/audit/`, `scripts/download/`, and `scripts/submission/` as the only subfolders
this project's scripts get organized into. Every Stage 1-3 one-off inspection/build script
(`build_data_manifest.py`, `inspect_overture_sources.py`, and the nine Stage 3 data-dictionary
scripts) stays flat at `scripts/` root — the tree is not an exhaustive file listing, only the
load-bearing modules and the subfolders that need to exist. `scripts/verify_bucket.py` in
particular — the pre-Stage-2 one-off bucket check, superseded in function by `scripts/audit/
audit_bucket.py` — is **deliberately never moved, renamed, or deleted**: `build_data_manifest.py`'s
own docstring says it is "kept as-is as a record," and `src/schemas.py`, `audit_bucket.py`, and
`inspect_national_strata_schema.py` each reference it by its exact current path as "the original
script this was generalized from." Moving it would silently break four live cross-references for
zero functional benefit.

---

## 5. Mandatory vs. optional

**Mandatory (non-negotiable)**:
- Competition: the Scoring Freeze (Gate C) and its versioned artifact; the tiered calibration
  protocol with an established noise floor and mandatory cross-region confirmation; the
  narrowly-scoped ensembling rule (formula-parameter variants only, never discrete
  spatial-assignment blends); the automated, CI-tested generated submission notebook; a
  provably-capped submission budget.
- Bias Discovery: Measurement Eligibility Bias as a flagship-tier candidate; the hypothesis funnel;
  the exploration/confirmation split with FDR correction; the candidate-scoring rubric; two-mode
  (context-first and gap-first) clustering.
- Engineering: `feature_role` separation and the automated external-data-provenance check; git
  commit SHA / scorer version / feature version on every generated artifact; `src/cli.py` as the
  canonical, cross-platform interface.
- Deployment: the out-of-distribution warning on the Equity Profile Explorer panel;
  association-not-causal language throughout; a fully precomputed, statically-served app.

**Optional — adopted only if a real finding or result justifies it, not required by default**:
HDBSCAN (k-means is the default), a stacking ensemble for the explanatory model (simple averaging
is the default), SHAP on a stacked ensemble specifically, more than the core set of publication
maps, every spatial statistic in the toolkit (Moran's I/Gi* only where a spatial-clustering claim
is actually made), and per-region explanatory models as anything more than a robustness check on
the pooled model.

---

## 6. Calendar (Sep 3 – Oct 31, ~8.5 weeks)

Loose week-by-week pacing, not a rigid one-stage-per-week schedule — several stages run in
parallel in practice. Mainly a checkpoint against the risk that Bias Discovery statistical rigor
work crowds out documentation polish right before the deadline.

- **Week 1 (Sep 3–9)**: Stage 0 (environment, CLI), Stage 1 (data acquisition, discussion-board
  post posted immediately), Stage 2 (data audit — Gate A), Stage 3 (data dictionary), Stage 4
  (repo restructure).
- **Week 2 (Sep 10–16)**: Stage 5 (EDA), the two-tier test-fixture build at the start of Stage 7.
- **Weeks 3–4 (Sep 17–30)**: Stage 6 (feature engineering with feature-role tagging), the core of
  Stage 7 — pipeline built for eastern-ok, **the early eastern-ok submission goes out as soon as
  the scorer clears its own tests**, not held back for polish; pipeline then extended to the other
  three regions; any-of-three-undefined self-check; Gate B cleared.
- **Week 5 (Oct 1–7)**: Stage 7's tiered designed-experiment calibration across all four regions,
  the noise-floor establishment, cross-region confirmation, the scoped ensemble-weight search, the
  gold-standard validation set, the Scoring Freeze (Gate C) and versioned scoring artifact.
- **Week 6 (Oct 8–14)**: Stage 8 — hypothesis funnel, two-mode clustering, explanatory model
  training/HPO/ensembling with the region-confound mitigation, the go/no-go gate. Stage 9 begun in
  parallel — Bias API replica built early enough to screen candidates before they're written up.
- **Week 7 (Oct 15–21)**: Stage 9 finished (FDR-corrected confirmatory analysis, Gate D — writeup
  frozen), Stage 10 (CI green, including the generated-notebook test), Stage 11 (documentation
  polish pass, including the decision log and reproducibility demo).
- **Week 8 (Oct 22–28)**: Stage 12 — the app-data-bundle fix applied, Coverage Gap Explorer built
  and deployed (this is the earliest point its real dependencies are done); continued
  documentation polish; begin narrowing final-submission candidates.
- **Oct 29–31**: Stage 13 — final two-submission selection, last Gate E code-review-readiness
  pass, buffer for anything slipped from earlier weeks.
</content>
<parameter name="present_to_user">false</parameter>
