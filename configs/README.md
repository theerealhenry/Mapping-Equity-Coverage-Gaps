# configs/

This directory holds genuinely environment-specific settings only — the kind of thing that
legitimately differs between two machines running this same project (for example, a local
data-cache path override, or a machine-specific credentials file location).

It does **not** hold region, layer, or formula constants. Those live in `src/config.py` by
explicit design (see `PROJECT_BLUEPRINT.md` Section 1's "no per-region YAML configs" rule): the
four study regions, the source-table names, and every scoring constant are fixed, versioned facts
about this competition, not configuration that should vary by environment or be edited casually.
Putting them here instead of in `src/config.py` would split one fact across two places and
reintroduce exactly the per-region-YAML sprawl the project deliberately avoided.

This directory is empty as of Stage 4 — nothing in this project has needed an environment-specific
setting yet. It exists now so that if one is ever needed, it has an obvious, already-agreed-upon
home rather than prompting an ad hoc decision mid-stage.
