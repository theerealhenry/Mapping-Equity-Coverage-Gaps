"""
scripts/mlflow_log.py — Stage 7 Step 5: the two-step MLflow submission-logging discipline.

Every real submission from this point forward gets logged in TWO calls, not one, because the
RMSE doesn't exist yet at upload time:
  1. log-submission  -- called immediately when the file is uploaded to Zindi. Logs the
                         formula/assignment parameters plus the submission CSV and a
                         docs/scoring_assumptions.md snapshot as artifacts. Prints a run_id.
  2. log-result       -- called once Zindi's leaderboard posts a score for that run_id.

This exists specifically because "log it later" is the exact failure mode this project has
already flagged once under deadline pressure (Stage 6/prior-stage experience) -- treat both calls
as part of "submitting a file", not an optional follow-up that can slip.

Run with:
  python -m scripts.mlflow_log log-submission --name smoke-test --csv submissions/01-smoke-test-submission.csv --params mode=smoke
  python -m scripts.mlflow_log log-result --run-id <id printed by the previous command> --rmse 0.1234
  python -m scripts.mlflow_log export
"""

from __future__ import annotations

import argparse
from pathlib import Path

import mlflow

EXPERIMENT_NAME = "bias-bounty-coverage-gap-submissions"
SCORING_ASSUMPTIONS_PATH = Path("docs/scoring_assumptions.md")
EXPORT_PATH = Path("docs/experiments/mlflow_runs_export.csv")


def log_submission(name: str, csv_path: Path, params: dict[str, str]) -> str:
    """Call at upload time. Returns the MLflow run_id -- write it down; log_submission_result
    needs it once the leaderboard score posts."""
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params(params)
        mlflow.log_artifact(str(csv_path))
        if SCORING_ASSUMPTIONS_PATH.exists():
            mlflow.log_artifact(str(SCORING_ASSUMPTIONS_PATH))
        mlflow.set_tag("stage", "7")
        mlflow.set_tag("rmse_status", "pending")
        run_id = run.info.run_id
    print(f"Logged submission '{name}' -- run_id={run_id}")
    print("Save this run_id: log-result needs it once the leaderboard score posts.")
    return run_id


def log_submission_result(run_id: str, rmse: float) -> None:
    """Call once Zindi's leaderboard posts a score for this run_id."""
    with mlflow.start_run(run_id=run_id):
        mlflow.log_metric("rmse", rmse)
        mlflow.set_tag("rmse_status", "confirmed")
    print(f"Logged rmse={rmse} for run_id={run_id}")


def export_runs() -> None:
    """Refreshes docs/experiments/mlflow_runs_export.csv from every run logged so far -- the
    real, versioned, committable record of the experiment log, not just what's sitting in the
    local ./mlruns store."""
    mlflow.set_experiment(EXPERIMENT_NAME)
    runs = mlflow.search_runs(experiment_names=[EXPERIMENT_NAME])
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    runs.to_csv(EXPORT_PATH, index=False)
    print(f"Exported {len(runs)} run(s) to {EXPORT_PATH}")


def _parse_params(pairs: list[str]) -> dict[str, str]:
    params = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        params[key] = value
    return params


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    log_cmd = sub.add_parser("log-submission")
    log_cmd.add_argument("--name", required=True)
    log_cmd.add_argument("--csv", required=True, type=Path)
    log_cmd.add_argument("--params", nargs="*", default=[], help="key=value pairs")

    result_cmd = sub.add_parser("log-result")
    result_cmd.add_argument("--run-id", required=True)
    result_cmd.add_argument("--rmse", required=True, type=float)

    sub.add_parser("export")

    args = parser.parse_args()
    if args.command == "log-submission":
        log_submission(args.name, args.csv, _parse_params(args.params))
    elif args.command == "log-result":
        log_submission_result(args.run_id, args.rmse)
    else:
        export_runs()


if __name__ == "__main__":
    main()
