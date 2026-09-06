"""
scripts/submission/build_submission_notebook.py — Stage 7 (Reference Reconstruction Engine: build,
test, calibrate, freeze).

Owned by Stage 7. Generates the flattened reproduction notebook (`submission/coverage_gap_
solution.ipynb`) from the approved, frozen source modules: strips project-local imports, inlines
the necessary functions, writes the flattened notebook, executes it against the golden-case
fixtures, and validates the output schema. This automates the submission notebook rather than
hand-maintaining it in parallel with `src/` — the flattened notebook is a **generated artifact**,
not a hand-edited one, closing the real synchronization risk that would otherwise exist between the
modular portfolio code and the actual Zindi-review artifact (see `submission/README.md`).

Intentionally empty — populated in Stage 7.
"""
