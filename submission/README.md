# submission/

This directory's one file, `coverage_gap_solution.ipynb`, is a **generated artifact** — do not
hand-edit it. It's produced by `scripts/submission/build_submission_notebook.py` at the Stage 7
freeze, and does not exist yet.

`coverage_gap_solution.ipynb` is the flattened, public-packages-only reproduction notebook — the
file actually submitted for code review if this project places in the top 10 (48 hours to submit
after the leaderboard closes, per the competition's code-review requirement). It strips
project-local imports and inlines the necessary functions from the approved, frozen `src/` modules,
so it can run standalone without this repository's package structure.

Because it is generated, not authored, any change to its content must be made by changing the
frozen source it's generated from and re-running the generator — never by editing this notebook
directly. Hand-editing it would silently desynchronize it from the actual `src/` logic it's meant
to faithfully reproduce, which is exactly the risk `build_submission_notebook.py` exists to close.
