"""
tests/test_gap_arithmetic.py — Stage 7 (Reference Reconstruction Engine: build, test, calibrate,
freeze).

Owned by Stage 7. Will hold the golden-case arithmetic fixtures: hand-constructed inputs covering
the coverage-gap formula's edge cases — `overture=0` -> gap 1, `overture>=reference` -> gap 0
(capped, never negative), `reference=0` -> undefined (excluded from the mean entirely, never
zeroed). Per the blueprint, both fixture tiers (this file and `test_geometry_assignment.py`) must
pass against 3-4 hand-fabricated micro-tracts before the pipeline is ever run against real data.

Intentionally empty — no test functions yet. Populated in Stage 7, before `src/gaps.py` is run
against real data.
"""
