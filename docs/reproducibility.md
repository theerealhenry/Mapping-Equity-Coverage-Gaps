# Reproducibility

Status: living document, started at Stage 0, filled in fully at Stage 11. Every section below
describes what this project actually does — not an aspirational plan — and is updated whenever the
real setup changes.

## Environment setup

This project is developed locally on Windows, in VS Code, using Miniconda for environment
management (not `venv`/`virtualenv`).

Exact commands used to create the environment:

```powershell
conda create -n bias-bounty python=3.11
conda activate bias-bounty
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Python is pinned to **3.11**, not the 3.12 the challenge's own tutorial notebook specifies in its
PEP 723 header. That tutorial's 3.12 requirement is driven entirely by its interactive-map
dependencies (`arro3-core`, `geoarrow-rust-io`) — packages this project's own pipeline never uses.
Every dependency this project actually needs was verified to install and import cleanly under
Python 3.11 (see "Dependency compatibility investigation" below), so 3.11 was kept rather than
matched to the tutorial notebook for its own sake.

To reproduce the environment from scratch on a clean machine:

```powershell
conda create -n bias-bounty python=3.11
conda activate bias-bounty
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m src.cli --help
pytest
```

All three of the last commands must succeed with zero errors before any pipeline code is
considered to be running against a trustworthy foundation (Stage 0 exit criteria).

## Dependency compatibility investigation

Before finalizing `requirements.txt`, every top-level dependency the project's full stack needs
(Section 1 of `PROJECT_BLUEPRINT.md`) was installed together in a disposable Python 3.11
environment and actually imported, rather than pinned from documentation alone. This surfaced two
real, non-obvious conflicts that would otherwise have appeared mid-project, most likely right when
Stage 7's MLflow tracking was first wired up:

**`numpy==2.5.1` does not exist for Python 3.11.** The version originally carried over from the
challenge tutorial notebook's own pin requires Python >=3.12. Resolved by pinning `numpy==2.4.6`,
the latest 2.x release that supports 3.11.

**Every released version of `mlflow` — including the current latest, 3.15.2 — declares
`pandas<3` as a hard dependency.** `pandas==3.0.3` (the tutorial notebook's own pin) and any real,
usable version of `mlflow` cannot be installed in the same environment; pip's resolver reports
`ResolutionImpossible`. Critically, installing `mlflow` *unpinned* alongside `pandas==3.0.3` does
not fail loudly — pip silently backtracks all the way to `mlflow==1.26.1` (a release from 2022),
which is missing years of tracking-UI, model-registry, and logging functionality, and in fact
fails to even `import` in this environment (a `protobuf` API mismatch: `mlflow==1.26.1` expects an
old `google.protobuf` layout that the protobuf version pulled in by the rest of the stack no longer
provides). A silent downgrade to a broken, ancient package is a worse failure mode than an explicit
error, and it is exactly the kind of problem that stays invisible until the moment MLflow is
actually exercised.

Resolved by pinning `pandas==2.3.3` (latest stable 2.x) instead of the tutorial notebook's
`3.0.3`. With that one change, the entire stack — `pandas`, `geopandas`, `pyarrow`, `duckdb`,
`numpy`, `matplotlib`, `obstore`, `pandera`, `mlflow`, `scikit-learn`, `lightgbm`, `shap`,
`optuna`, `streamlit`, `pytest` — installs together with no resolver conflicts, and every package
was confirmed to actually `import` successfully (not just install) in the same environment. This
has no material cost to the project: nothing in the pipeline (Stages 2–12) depends on a pandas-3
feature, and pandas 2.3.x is materially more battle-tested than 3.0.3, which had only been out a
few months at time of writing.

**`shap` is pinned to `0.51.0`, not the newer `0.52.0`**, because `0.52.0` requires Python >=3.12
and this project targets 3.11. `0.51.0` has no functional gap relevant to this project (SHAP
values for the Stage 8 explanatory model, standard tree-explainer usage).

One item was not fully verifiable inside the automated check: DuckDB's `spatial` and `httpfs`
extension downloads (`INSTALL spatial; LOAD spatial;`) were blocked by network egress rules in the
sandbox used to run this check, not by any incompatibility in DuckDB 1.5.4 itself — this is
confirmed working directly once run from the actual development machine (Stage 2 onward
depends on it; if it does not load cleanly there, that becomes the first real Stage 2 finding).

The rule going forward: any new dependency added to `requirements.txt` after Stage 0 gets the same
treatment — installed together with the full existing stack in a throwaway environment and
actually imported — before its pin is added here, rather than trusting a package's documentation
or its latest PyPI version number in isolation.

## Seed policy

_Filled in at Stage 7/8/9 once stochastic operations exist (Optuna sampler, Stage 8 train/
validation splits and clustering, Stage 9 bootstrap/permutation tests). A single `SEED` constant
lives in `src/config.py`; every stochastic call in the project imports it rather than hardcoding
its own value._

## How to run each stage

Filled in incrementally as each stage's `src/cli.py` subcommand is implemented. See
`PROJECT_BLUEPRINT.md` Section 3 for what each stage produces.

**Stage 2 — data audit** (`python -m src.cli audit`): runs `scripts/audit/audit_bucket.py` against
the live bucket for every region and every reference layer with a registered `src/schemas.py`
contract, writing `docs/audit_findings.csv` and exiting non-zero if any region/layer combination
fails to load and validate cleanly. Supports the same flags as `audit_bucket.py`'s own CLI,
forwarded as-is: `--region <name...>` (restrict to specific regions), `--layers <name...>`
(restrict to specific layers), `--skip-strata` (skip the per-region strata-table check for faster
iteration), `--output <path>` (default `docs/audit_findings.csv`). On a clean machine this takes
several minutes end-to-end (44 region/layer combinations, up to ~11.5M rows for South-Central
Texas's largest layers) — `--region`/`--layers` are for fast iteration on a subset while developing
against this stage, not the way to sign off Gate A, which requires the full, unrestricted run. The
same audit logic is also run narratively, with figures and a full interpretation, in
`notebooks/00_data_audit.ipynb` — run either one to reproduce the numbers cited in
`docs/data_manifest.md` Sections 4.8–4.9.

_Remaining stages filled in as their subcommands are implemented._

## MLflow tracking location

_Filled in at Stage 7. Three experiments: `competition-scoring`, `diagnostic-modeling`,
`bias-discovery`, tracked to a local file-store/SQLite backend (`mlruns/`, gitignored). A flat
export (`docs/experiments/mlflow_runs_export.csv`) is committed so run history survives even
without the local tracking store._

## How CI mirrors local runs

_Filled in at Stage 10. GitHub Actions installs the exact `requirements.txt` into a fresh Python
3.11 environment on every push and runs the same `pytest` suite and CLI smoke checks used locally
— no divergence between "how Henry runs it" and "how CI runs it."_
