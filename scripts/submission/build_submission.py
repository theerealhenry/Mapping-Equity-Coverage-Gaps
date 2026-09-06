"""
scripts/submission/build_submission.py — Stage 7 (Reference Reconstruction Engine: build, test,
calibrate, freeze).

Owned by Stage 7. Builds the scored CSV from the frozen `src/gaps.py` logic and enforces
`feature_role` at the boundary: an automated check fails loudly if any non-`competition`-tagged
column (in particular anything derived from an external, non-provided data source) is referenced
anywhere in the path that produces the scored submission. This physically enforces the challenge's
own rule that the scored coverage-gap computation must use only the datasets provided for this
challenge — a Stage 6 feature-table design constraint, checked for real at the point a submission
is actually produced.

Intentionally empty — populated in Stage 7.
"""
