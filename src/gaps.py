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

Step 2 status: only the pure-arithmetic core below exists (capped_ratio_gap, coverage_gap_score),
written test-first against tests/test_gap_arithmetic.py per this stage's TDD discipline. The real
pipeline — reading Stage 6's competition-tagged columns, calling src/geometry.py, producing
per-region scored tables — is Step 3's job and is not built yet.
"""

from __future__ import annotations


def capped_ratio_gap(overture: float, reference: float) -> float | None:
    """The challenge's capped-ratio gap formula: ``1 - min(1, overture / reference)``.

    Returns ``None`` (not ``0.0``) when ``reference == 0`` — there is nothing to compare against,
    so the value is undefined, not "fully covered". This is R-005 from the risk register: an
    undefined component must be excluded from `coverage_gap_score`'s mean entirely, never silently
    zeroed. Callers must not coerce this ``None`` into a number.

    The ratio is capped at 1 before subtracting, so a tract where Overture reports MORE than the
    reference (overture > reference) still floors at gap 0.0 — never negative.
    """
    if reference == 0:
        return None
    return 1 - min(1.0, overture / reference)


def coverage_gap_score(components: dict[str, float | None]) -> float | None:
    """The composite score: the arithmetic mean of only the DEFINED (non-``None``) component gap
    values. Divisor is however many components are defined (1, 2, or 3) — never a fixed 3, and an
    undefined component is excluded, not treated as 0. Returns ``None`` if every component is
    undefined for that tract."""
    defined = [v for v in components.values() if v is not None]
    if not defined:
        return None
    return sum(defined) / len(defined)
