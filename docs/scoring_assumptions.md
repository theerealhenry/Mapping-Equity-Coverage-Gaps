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

## 2. Building-assignment rule (centroid-in-polygon vs. geometric intersection) — OPEN

**Ambiguity**: for a building whose footprint straddles a tract boundary, is it assigned to the
tract containing its centroid, or credited (fully or partially) to every tract its geometry
intersects?

**Evidence**: the README does not state this rule explicitly for `building_gap`. `src/geometry.py`
(Stage 6) already implements both variants as `building_gap_centroid` and
`building_gap_intersection` columns, so both are available to calibrate between.

**Working hypothesis (current, starting default only)**: `src/gaps.py` uses
`building_gap_intersection` — `claude/final-project-plan.md`'s stated working bias toward the more
conservative, boundary-inclusive rule, pending real calibration evidence. **This is explicitly not
frozen** — Stage 7 Step 6 (Tier A) is where this gets decided by designed-experiment calibration
(three regions held fixed, one region's rule varied, RMSE delta attributed to the change).

**Validation status**: `unconfirmed`.

**Evidence pointer**: none yet — awaiting Step 6.

---

## 3. Does the capped-ratio formula apply identically to `transport_gap` and `building_gap`? — OPEN

**Ambiguity**: the README states the capped-ratio formula (`1 - min(1, overture/reference)`)
explicitly for the POI/HIFLD component. `claude/final-project-plan.md` Section 0 flags that this
was never separately confirmed in the README's own words for `transport_gap` or `building_gap` —
it's a reasonable, but unconfirmed, extrapolation.

**Working hypothesis (current)**: the same capped-ratio formula applies to all three components;
Stage 6 materialized `transport_gap`/`building_gap_centroid`/`building_gap_intersection` on that
assumption.

**Validation status**: `unconfirmed` (a discussion-board question covering this was drafted per
the final project plan; check its status before Tier A begins per Stage 7 Step 0's preflight).

**Evidence pointer**: none yet — awaiting a discussion-board answer or Step 6 RMSE evidence.
