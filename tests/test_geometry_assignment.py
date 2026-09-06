"""
tests/test_geometry_assignment.py — Stage 7 (Reference Reconstruction Engine: build, test,
calibrate, freeze).

Owned by Stage 7. Will hold the golden-case geometry-assignment fixtures: hand-fabricated
micro-geometries — a tract boundary polygon, one building that straddles it, one road that crosses
it — with manually verified expected tract-assignment outputs. This is a distinct failure mode
from arithmetic bugs (covered by `test_gap_arithmetic.py`) and belongs in its own fixture category,
exercising `src/geometry.py`'s point-in-polygon, centroid-in-polygon vs. intersection, and
line-clip-and-sum logic directly.

Intentionally empty — no test functions yet. Populated in Stage 7, before `src/gaps.py` is run
against real data.
"""
