"""
src/bias_api_replica.py — Stage 9 (Statistical confirmation & Bias Discovery writeup).

Owned by Stage 9. Responsible for a local replica of the five official Bias Score metrics —
Coverage Disparity Ratio, POI Desert Index, Emergency Access Gap, Road Network Equity Ratio, and
Climate-Justice Composite — computed locally from the frozen Stage 7 output. Serves two purposes:
the novelty-screening step in Stage 8/9's hypothesis funnel (checking a candidate finding isn't
just a restatement of a fixed metric), and a redundancy guard applied before the Bias Discovery
writeup is finalized — Gate D's exit criteria explicitly requires the replica to confirm no
flagship finding restates one of these five metrics.

Confirmed real stratification grid (empirical, 2026-09-07, via the Stage 0.5 smoke-test
submission's "Show Scoring Rubric" breakdown — see PROJECT_BLUEPRINT.md Stage 9 and
docs/decision_log.md): the live scorecard reports nine stratum rows, not the five metric names —
Rural vs Urban, Tribal vs Non-Tribal, High Social Vulnerability, High Climate Vulnerability, Summer
Drought, Winter Drought, Wildfire Hazard, Summer Heat, and an intersectional High Hazard + High
Vulnerability row. Drought is split Summer/Winter and heat is Summer-Heat-only, finer than the
README's five-metric summary implies on its own. This module's redundancy-guard role must
replicate the metrics at this exact 9-row grid, not only at their coarsest grouping, or it can
miss a finding that only restates an official metric once split this finely.

Intentionally empty — populated in Stage 9.
"""
