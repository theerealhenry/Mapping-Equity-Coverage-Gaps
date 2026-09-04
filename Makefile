# Thin convenience wrapper around src/cli.py — the canonical interface (see src/cli.py's module
# docstring). Every target here does nothing but call `python -m src.cli <command>`; if a target
# isn't reachable through that CLI, it doesn't belong here either. This exists for convenience on
# macOS/Linux — it is never the *only* way to run a stage. `make` is not native on Windows, so the
# primary development machine for this project (Henry's, Windows + Miniconda) always uses the CLI
# directly (`python -m src.cli <command>`), and this file is kept in lockstep with it for anyone
# reviewing or running the project on macOS/Linux instead.
#
# Usage: make <target> [REGION=<region>] [SUBMISSION_PATH=<path>]
#   e.g. make features REGION=eastern-ok
#        make score REGION=south-central-tx
#        make validate-submission SUBMISSION_PATH=submissions/my-submission.csv
#
# NOTE: the validate-submission path variable is deliberately named SUBMISSION_PATH, not PATH.
# `make` exports command-line variable assignments into the recipe's own environment — naming it
# PATH would silently clobber the real system PATH inside the recipe's shell and break every
# subsequent command in it (confirmed directly: `make validate-submission PATH=...` produces
# `make: python: No such file or directory`, since `python` can no longer be found on the
# overwritten PATH). This is exactly the kind of subtle failure worth avoiding in the one interface
# every later stage depends on.

.PHONY: help install audit eda features score build-submission validate-submission test

help:
	@echo "Available targets (all are thin wrappers around 'python -m src.cli <command>'):"
	@echo "  install               pip install -r requirements.txt"
	@echo "  audit                 Stage 2 — audit the source bucket"
	@echo "  eda                   Stage 5 — run exploratory data analysis"
	@echo "  features REGION=<r>   Stage 6 — build the tract feature table for one region"
	@echo "  score REGION=<r>      Stage 7 — run the Reference Reconstruction Engine for one region"
	@echo "  build-submission      Stage 7 — generate the flattened submission notebook + CSV"
	@echo "  validate-submission   Stage 7 — validate a submission CSV (SUBMISSION_PATH=<path>, optional)"
	@echo "  test                  run the pytest suite"
	@echo ""
	@echo "REGION must be one of: maricopa-az, northern-ca, eastern-ok, south-central-tx"
	@echo "(the same list src/cli.py itself enforces — see src/config.py:REGIONS)."

install:
	pip install -r requirements.txt

audit:
	python -m src.cli audit

eda:
	python -m src.cli eda

features:
ifndef REGION
	$(error REGION is required, e.g. make features REGION=eastern-ok)
endif
	python -m src.cli features --region $(REGION)

score:
ifndef REGION
	$(error REGION is required, e.g. make score REGION=eastern-ok)
endif
	python -m src.cli score --region $(REGION)

build-submission:
	python -m src.cli build-submission

validate-submission:
ifdef SUBMISSION_PATH
	python -m src.cli validate-submission --path $(SUBMISSION_PATH)
else
	python -m src.cli validate-submission
endif

test:
	pytest
