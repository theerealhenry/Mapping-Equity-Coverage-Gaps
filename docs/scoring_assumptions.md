# Scoring Assumptions

Populated starting Stage 7 (created and used from Stage 5's EDA summary onward, per
`PROJECT_BLUEPRINT.md`). Records what the scorer does and why — one row per genuine ambiguity,
evidence, hypothesis, validation status, and linked submission evidence. Distinct from
`docs/decision_log.md`: this file documents the scorer's actual behavior and its open/resolved
ambiguities, not the reasoning trail behind unrelated implementation choices.

Columns: **Ambiguity** — the specific scoring question; **Evidence for/against** — what the
README/Evaluation doc actually says; **Working hypothesis** — what `src/gaps.py` currently
implements; **Validation status** — one of `unconfirmed`, `self-check-consistent`,
`README-confirmed`, `discussion-board-confirmed`, `RMSE-experiment-confirmed`; **Evidence
pointer** — the specific submission(s), test(s), or doc passage the status is based on.

**Stage 7 Step 7 (Tier B sensitivity) status**: all three rows below are resolved as of Step 6; a
dedicated doubt-driven-development pass in Step 7 (see `docs/decision_log.md`) found no defensible
small variation left to test around any of them — every candidate the Step 7 guideline names, plus
every other latent two-implementation choice checked in the codebase (`cbp_estab_bus` vs.
`cbp_estab_res`), is already closed by real-data evidence from Stage 5/6. Tier A logic confirmed
robust; 0 additional submissions spent.

---

## 1. `poi_gap`'s internal structure — RESOLVED, README-confirmed

**Ambiguity**: does `poi_gap` weight its four sub-parts (fire, EMS, schools, CBP establishments)
equally in one flat mean, or does it combine them in some other structure?

**Evidence**: the challenge README states directly: *"For each type, `1 - min(1, overture /
hifld)` per tract, undefined where the tract has no HIFLD facility of that type; `poi_gap_hifld`
is the mean over the defined types... The CBP half (all Overture places against CBP
establishments) is unchanged, and `poi_gap` is the mean of the two halves."* This is an explicit,
unambiguous two-stage nested mean: `poi_gap_hifld = mean(defined among {fire, ems, schools})`,
then `poi_gap = mean(poi_gap_hifld, poi_gap_cbp)` — not a flat four-way mean.

**Working hypothesis (current, correct)**: `src/gaps.py`'s `_poi_gap_for_row()` implements the
nested two-stage mean exactly as quoted above.

**History**: Step 3's original implementation used a flat mean of all four sub-parts instead. This
is silently wrong whenever 2 or 3 of {fire, ems, schools} are defined *together with* CBP for the
same tract — in that case a flat mean under-weights CBP by roughly 2x-3x relative to the correct
nested mean (when only one HIFLD type or only CBP is defined, the two formulas happen to agree, so
the bug is not universal — it specifically affects tracts with multiple recorded facility types,
which skews toward denser/urban tracts). The bug was found via source-driven re-reading of the
README (prompted by hunting for a "free win" before Tier A calibration spent any submission
budget), not by a test or a leaderboard result — the original flat-mean implementation had no
test locking down its internal structure, only the outer arithmetic (`coverage_gap_score`'s
defined-only mean) was tested. Fixed in `src/gaps.py`; regression-tested in
`tests/test_gap_arithmetic.py` (`test_poi_gap_uses_nested_mean_not_flat_mean_when_hifld_and_cbp_
both_defined`, plus three symmetric single-half-defined/none-defined cases).

**Validation status**: `README-confirmed`.

**Evidence pointer**: challenge `README.md` (project doc); `tests/test_gap_arithmetic.py` (4 new
tests, all passing); `docs/decision_log.md`'s corresponding entry for the fix's code-review pass.

---

## 2. Building-assignment rule (centroid-in-polygon vs. geometric intersection) — RESOLVED, RMSE-experiment-confirmed

**Ambiguity**: for a building whose footprint straddles a tract boundary, is it assigned to the
tract containing its centroid, or credited (fully or partially) to every tract its geometry
intersects?

**Evidence**: the README does not state this rule explicitly for `building_gap`. `src/geometry.py`
(Stage 6) already implements both variants as `building_gap_centroid` and
`building_gap_intersection` columns, so both were available to calibrate between.

**Working hypothesis (now, resolved)**: `src/gaps.py`'s `BUILDING_GAP_COLUMN` is
`building_gap_centroid`. Superseded the starting default (`building_gap_intersection`, the
conservative boundary-inclusive rule stated in `claude/final-project-plan.md`) after Stage 7 Step
6's designed-experiment calibration produced a real, noise-floor-exceeding RMSE improvement in
both its isolated-region test and its mandatory cross-region confirmation.

**Calibration trail**:
- Noise floor: exactly 0.00000000 (submission `FnrJ3ywM` reproduced the all-intersection baseline
  byte-for-byte and scored identically to `obUDeiZ9`, 0.00015295 both) — any nonzero delta is real
  signal, not resubmission jitter.
- Isolated-region test (south-central-tx only, on `building_gap_centroid`, three other regions held
  at intersection): submission `mz879CNt`, RMSE 0.00014674 — a ~4.06% relative improvement over the
  0.00015295 baseline.
- Mandatory cross-region confirmation (all four regions on `building_gap_centroid`): submission
  `RCPw2FP4`, RMSE 0.000145067 — a further improvement, confirming the isolated-region win
  generalizes and is not sctx-specific. Leaderboard rank moved 92 -> 90 -> 83 across the three
  submissions.

**Validation status**: `RMSE-experiment-confirmed`.

**Evidence pointer**: `scripts/tier_a_calibration.py`; submissions `FnrJ3ywM` (noise floor),
`mz879CNt` (isolated-region, RMSE 0.00014674), `RCPw2FP4` (cross-region confirmation, RMSE
0.000145067); `src/gaps.py`'s `BUILDING_GAP_COLUMN`; `tests/test_gap_arithmetic.py`
(`test_score_region_defaults_to_centroid_building_column`); `docs/decision_log.md`'s Tier A
closing entry.

---

## 3. Does the capped-ratio formula apply identically to `transport_gap` and `building_gap`? — RESOLVED, self-check-consistent

**Ambiguity**: the README states the capped-ratio formula (`1 - min(1, overture/reference)`)
explicitly for the POI/HIFLD component. `claude/final-project-plan.md` Section 0 flags that this
was never separately confirmed in the README's own words for `transport_gap` or `building_gap` —
it's a reasonable, but unconfirmed, extrapolation.

**Working hypothesis (current)**: the same capped-ratio formula applies to all three components;
Stage 6 materialized `transport_gap`/`building_gap_centroid`/`building_gap_intersection` on that
assumption.

**Resolution**: no alternate formula was ever built to substitute in, so this was never testable
as a submission-based factorial cell. Resolved instead by two free self-checks, one per component:

- `transport_gap`: Stage 5's own EDA self-check (`docs/eda_findings.md` Finding 5) — the
  Overture/TIGER named-highway length ratio (which the README states directly should fall in
  [0.71, 1.59] under the capped-ratio formula) falls inside that band in all four regions —
  eastern-ok 0.719 (right at the floor), maricopa-az 1.296, northern-ca 1.173, south-central-tx
  consistent with the same finding.
- `building_gap`: no README-stated sanity band exists for buildings (unlike transport), so this
  was checked against a weaker but still meaningful bar — do whole-region Overture/Microsoft
  building-footprint count ratios come out as sane, non-degenerate positive numbers, with no
  region wildly out of line with the other three? Using the raw region-total row counts already
  recorded in `docs/data_manifest.md` Section 4 (Overture / Microsoft): maricopa-az
  2,908,224/2,610,544 = 1.114, northern-ca 1,164,724/1,138,335 = 1.023, eastern-ok
  2,551,694/2,404,448 = 1.061, south-central-tx 11,463,801/10,619,119 = 1.080. All four ratios
  cluster tightly in [1.02, 1.11] — Overture has slightly *more* raw building footprints than
  Microsoft everywhere, no region is an outlier, and nothing near-zero or negative that would
  signal a broken join or a formula that misbehaves for this component. This is a coarser check
  than transport's tract-level, README-anchored band (no equivalent published band exists for
  buildings, and these are whole-region raw counts, not the tract-clipped, subtype-filtered counts
  `src/geometry.py` actually uses), but it is real evidence against the formula producing garbage
  for `building_gap`, gathered for free from data already loaded in Stage 6 rather than spent from
  the submission budget.

**Validation status**: `self-check-consistent` (both components).

**Evidence pointer**: `docs/eda_findings.md` Finding 5 (transport-gap ratio sanity bound, Step 5);
`docs/data_manifest.md` Section 4 building row counts (Stage 6, cited above for the building-gap
check). Zindi's discussion/Chat tab was not found to carry an organizer statement on either
question as of this review (Stage 7 Step 6 close-out) — if one appears later, it supersedes this
self-check per the guideline's discussion-board-is-authoritative rule, but Tier A does not need to
spend budget chasing it further given the self-check evidence already in hand.
