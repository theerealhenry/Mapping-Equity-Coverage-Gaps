"""
src/gaps.py — Stage 7 (Reference Reconstruction Engine).

Owned by Stage 7. This is the Reference Reconstruction Engine itself (System A) — the deterministic
computation, not a trained model, at the center of this project. Responsible for reading only
`competition`-tagged columns from the Stage 6 feature tables and producing the composite
`coverage_gap_score` per tract, computed as the capped-ratio formula `1 - min(1, overture/
reference)` per component (transport, building, POI), with undefined components excluded from the
mean entirely (never zeroed) — the exact edge cases `tests/test_gap_arithmetic.py` exists to lock
down before this module is ever run against real data. Calls into `src/geometry.py` for every
spatial assignment (point-in-polygon, centroid-in-polygon vs. intersection, line-clip-and-sum) —
`gaps.py` owns the formula and orchestration, `geometry.py` owns every spatial operation, by
explicit design so no component re-implements its own slightly different spatial logic.

Intentionally empty — populated in Stage 7.
"""
