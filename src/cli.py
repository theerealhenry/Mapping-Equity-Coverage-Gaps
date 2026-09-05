"""
src/cli.py — canonical command-line interface for the Bias Bounty Mapping Equity Challenge pipeline.

This is the one interface every stage of the project is actually run through, on any platform
(including Windows, where `make` is not native). The `Makefile` is a thin wrapper around these same
subcommands, never an independent path — if a target isn't reachable through this CLI, it doesn't
exist. Each subcommand corresponds to one stage in PROJECT_BLUEPRINT.md Section 3; the mapping is
listed below and repeated in each subcommand's own `--help` text.

    python -m src.cli audit                              # Stage 2 — data audit & validation contracts
    python -m src.cli eda                                 # Stage 5 — exploratory data analysis
    python -m src.cli features --region eastern-ok        # Stage 6 — feature engineering
    python -m src.cli score --region eastern-ok           # Stage 7 — Reference Reconstruction Engine
    python -m src.cli build-submission                    # Stage 7 — flattened notebook + submission CSV
    python -m src.cli validate-submission                 # Stage 7 — pre-submission validator

Every subcommand is currently a stub (raises NotImplementedError) until its stage is built — this
is intentional at Stage 0: the interface's *shape* is what needs to be right early, since every
later stage is written against it. Running any stub prints which stage implements it and exits with
status 2, so `python -m src.cli --help` and `python -m src.cli <command> --help` are both usable
immediately, before any pipeline code exists.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.config import REGIONS

logger = logging.getLogger("bias_bounty")

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Logging ---------------------------------------------------------------------------------------


def _configure_logging(verbosity: int) -> None:
    """-v => INFO, -vv (or more) => DEBUG, default => WARNING."""
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")


# --- Subcommand handlers -----------------------------------------------------------------------
# Each handler receives the parsed argparse.Namespace and returns a process exit code (0 = success).
# All of them are stubs until their stage is built (see module docstring for the stage mapping);
# NotImplementedError is the deliberate signal that a handler is scaffolded but not yet implemented,
# distinct from any other exception a real implementation might raise later.


def _not_implemented(stage: str, deliverable: str) -> None:
    raise NotImplementedError(
        f"Not yet implemented — this is {stage} of PROJECT_BLUEPRINT.md Section 3.\n"
        f"Expected deliverable: {deliverable}"
    )


def cmd_audit(args: argparse.Namespace) -> int:
    """Stage 2 — audit every layer in every region: schema, nulls, geometry validity, CRS.

    Delegates entirely to `scripts/audit/audit_bucket.py`'s own CLI — that module is where this
    logic actually lives and is tested (`tests/test_audit_bucket.py`); this handler just translates
    `python -m src.cli audit`'s parsed arguments into the equivalent `audit_bucket.py` invocation.
    Stage 2 is complete (see `docs/data_manifest.md` Section 4.8/4.9), so this is a real, working
    command now, not a permanent stub — the import is deliberately local to this function, not at
    module scope, so importing `src.cli` itself (e.g. for `--help`) never pulls in pandera/pyarrow
    for a subcommand that isn't being run, matching this module's existing lazy-import discipline
    for every other stage's handler."""
    from scripts.audit.audit_bucket import main as audit_main

    argv: list[str] = []
    if args.region:
        argv += ["--region", *args.region]
    if args.layers:
        argv += ["--layers", *args.layers]
    if args.skip_strata:
        argv.append("--skip-strata")
    if args.output is not None:
        argv += ["--output", str(args.output)]
    return audit_main(argv)


def cmd_eda(args: argparse.Namespace) -> int:
    """Stage 5 — exploratory data analysis: phenomenology, self-checks against published stats."""
    _not_implemented(
        "Stage 5 (Exploratory data analysis)",
        "notebooks/01_eda.ipynb",
    )
    return 0


def cmd_features(args: argparse.Namespace) -> int:
    """Stage 6 — build the tract-indexed feature table for one region."""
    _not_implemented(
        "Stage 6 (Feature engineering)",
        f"data/processed/{args.region}-tract-features.parquet",
    )
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    """Stage 7 — run the Reference Reconstruction Engine for one region."""
    _not_implemented(
        "Stage 7 (Reference Reconstruction Engine: build, test, calibrate, freeze)",
        "src/gaps.py output — per-tract coverage_gap_score for the requested region",
    )
    return 0


def cmd_build_submission(args: argparse.Namespace) -> int:
    """Stage 7 — generate the flattened, self-contained submission notebook and CSV."""
    _not_implemented(
        "Stage 7 (Reference Reconstruction Engine: build, test, calibrate, freeze)",
        "submission/coverage_gap_solution.ipynb (generated) + the submission CSV",
    )
    return 0


def cmd_validate_submission(args: argparse.Namespace) -> int:
    """Stage 7 — local pre-submission validator: row count, GEOID set, value range, no blanks."""
    _not_implemented(
        "Stage 7 (Reference Reconstruction Engine: build, test, calibrate, freeze)",
        "a pass/fail validation report for a submission CSV, run before every upload",
    )
    return 0


# --- Parser construction -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Constructs the CLI's argument parser. Kept separate from main() so tests can call
    build_parser().parse_args([...]) directly without invoking process exit / logging setup."""
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description=(
            "Bias Bounty Mapping Equity Challenge — pipeline CLI. "
            "Each subcommand corresponds to one stage in PROJECT_BLUEPRINT.md Section 3."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase log verbosity (-v = INFO, -vv = DEBUG)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    p_audit = subparsers.add_parser(
        "audit", help="Stage 2 — audit the source bucket (schema, nulls, geometry, CRS)"
    )
    p_audit.add_argument(
        "--region",
        nargs="*",
        choices=REGIONS,
        default=None,
        help="restrict to specific region(s) (default: all four)",
    )
    p_audit.add_argument(
        "--layers",
        nargs="*",
        default=None,
        help=(
            "restrict to specific reference layer(s) (default: every layer with a registered "
            "schema — see scripts/audit/audit_bucket.py's own --help for the valid names)"
        ),
    )
    p_audit.add_argument(
        "--skip-strata",
        action="store_true",
        help="skip the per-region strata-table audit (faster iteration on reference layers alone)",
    )
    p_audit.add_argument(
        "--output",
        type=Path,
        default=None,
        help="CSV output path (default: docs/audit_findings.csv)",
    )
    p_audit.set_defaults(func=cmd_audit)

    p_eda = subparsers.add_parser("eda", help="Stage 5 — run exploratory data analysis")
    p_eda.set_defaults(func=cmd_eda)

    p_features = subparsers.add_parser(
        "features", help="Stage 6 — build the tract feature table for one region"
    )
    p_features.add_argument(
        "--region", required=True, choices=REGIONS, help="study region to build features for"
    )
    p_features.set_defaults(func=cmd_features)

    p_score = subparsers.add_parser(
        "score", help="Stage 7 — run the Reference Reconstruction Engine for one region"
    )
    p_score.add_argument(
        "--region", required=True, choices=REGIONS, help="study region to score"
    )
    p_score.set_defaults(func=cmd_score)

    p_build_submission = subparsers.add_parser(
        "build-submission",
        help="Stage 7 — generate the flattened submission notebook + submission CSV",
    )
    p_build_submission.set_defaults(func=cmd_build_submission)

    p_validate_submission = subparsers.add_parser(
        "validate-submission",
        help="Stage 7 — validate a submission CSV before uploading it (row count, GEOID set, ranges)",
    )
    p_validate_submission.add_argument(
        "--path",
        type=Path,
        default=REPO_ROOT / "submissions" / "submission.csv",
        help="path to the submission CSV to validate (default: submissions/submission.csv)",
    )
    p_validate_submission.set_defaults(func=cmd_validate_submission)

    return parser


# --- Entry point -------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    try:
        return args.func(args)
    except NotImplementedError as exc:
        logger.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
