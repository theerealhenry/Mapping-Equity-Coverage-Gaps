# scoring/

Holds this project's versioned scoring artifacts — the frozen, exact record of what
`src/gaps.py` computed at the moment of the Stage 7 scoring freeze (Gate C).

## Versioning scheme

Each freeze gets its own numbered subdirectory: `v1/` for the first (and expected) freeze. A
`v2/` (and so on) would only ever be created if the Stage 7 freeze is redone — per Gate C's
explicit re-freeze rule in `PROJECT_BLUEPRINT.md`, a re-freeze happens only if evidence surfaces
after the original freeze that contradicts a formula assumption *and* there is still enough
calendar time and submission budget to redo the calibration protocol properly. A late,
unincorporated contradiction that's transparently documented (in `docs/scoring_assumptions.md`
and `docs/decision_log.md`) is the default, better outcome — a new `v2/` is the exception, not
the routine.

## What each version's directory holds

Produced at the Stage 7 freeze, not now:

- `formula.yaml` — the exact chosen formula and parameters.
- `assumptions.md` — a frozen snapshot of `docs/scoring_assumptions.md` at freeze time.
- `checksum.txt` — a hash of the frozen `src/gaps.py` logic.

The actual scored output (`coverage_scores_v1.parquet`) stays gitignored like other large data;
only its checksum and metadata are committed here. Every submission and every downstream artifact
(Stage 8's training data, Stage 9's analysis) carries `scorer_version`, `feature_version`, and
`git_commit` in its own metadata, so any result can be traced back to the exact frozen logic that
produced it.

`scoring/v1/` exists as of Stage 4 with no content yet — the freeze itself is Stage 7's work.
