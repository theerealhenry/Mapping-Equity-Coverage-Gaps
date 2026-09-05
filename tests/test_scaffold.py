"""
Stage 0 scaffolding tests.

These are deliberately NOT pipeline tests — no gap arithmetic, no geometry assignment, no real data
is touched here (those come in Stage 7: tests/test_gap_arithmetic.py, tests/test_geometry_assignment.py).
This file's job is narrower and specific to Stage 0's exit criterion: prove the *scaffolding itself*
— src/config.py and src/cli.py, the two files every later stage is built on top of — is sound,
before any pipeline code exists. A trivial `assert True` would technically satisfy "the test suite
passes," but would not have caught either of the two real bugs this project already hit before a
single pipeline stage was written: a stray leftover artifact that broke `import src.config`
entirely, and a Makefile variable name that silently clobbered the system PATH. The tests below are
scoped to catch exactly that class of problem going forward.
"""

from __future__ import annotations

import argparse

import pytest

from src import config
from src.cli import build_parser, main


# --- src/config.py -------------------------------------------------------------------------------


def test_config_module_imports_cleanly():
    """Regression test for the stray-artifact bug that broke `import src.config` at Stage 0:
    if config.py ever has a syntax error again, this fails immediately and specifically, instead
    of surfacing later as a confusing import error somewhere deep in a pipeline stage."""
    assert config is not None


def test_seed_is_a_fixed_integer():
    assert isinstance(config.SEED, int)


def test_regions_list_is_the_single_source_of_truth():
    """Every per-region dict in config.py must have exactly the same key set as REGIONS — if a
    region is ever added/renamed/removed, this fails until every dict is updated together, instead
    of one dict silently drifting out of sync with the others."""
    assert set(config.SCORED_TRACT_COUNTS) == set(config.REGIONS)
    assert set(config.REGION_TRACT_COUNTS) == set(config.REGIONS)


def test_scored_tract_counts_match_published_figures():
    """Direct regression test for the confirmed tract counts recorded in docs/data_manifest.md —
    9,379 scored tracts total, split as documented. If these ever change, it's a real finding, not
    something that should silently slip through."""
    assert config.SCORED_TRACT_COUNTS == {
        "maricopa-az": 1593,
        "northern-ca": 591,
        "eastern-ok": 1192,
        "south-central-tx": 6003,
    }
    assert sum(config.SCORED_TRACT_COUNTS.values()) == 9379


def test_maricopa_includes_the_documented_new_mexico_tract():
    assert config.MARICOPA_NM_TRACT_GEOID == "35023970000"


def test_reference_url_helpers_build_expected_paths():
    """These helpers are called by every future data-loading script — a typo here would silently
    404 against the bucket rather than fail loudly, so they're worth pinning down now."""
    assert config.reference_url("eastern-ok", "overture-buildings") == (
        "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
        "/reference/eastern-ok/eastern-ok-overture-buildings.parquet"
    )
    assert config.sample_submission_url("maricopa-az") == (
        "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
        "/reference/maricopa-az/maricopa-az-sample-submission.csv"
    )
    assert config.strata_national_url(config.STRATA_NATIONAL_JOINED_TABLE) == (
        "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
        "/strata/national/national-strata-tract-table.parquet"
    )


def test_reference_s3_path_matches_its_https_url_counterpart():
    """reference_s3_path and reference_url must always describe the SAME object via the two
    equivalent access routes (docs/data_manifest.md Section 1) -- a drift between them would mean
    DuckDB (HTTPS) and geopandas/pyarrow (S3) silently read two different things."""
    https_url = config.reference_url("eastern-ok", "overture-buildings")
    s3_path = config.reference_s3_path("eastern-ok", "overture-buildings")
    assert https_url.endswith(s3_path.split("/", 1)[1])  # same key, past the bucket-host segment
    assert s3_path == (
        "us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
        "/reference/eastern-ok/eastern-ok-overture-buildings.parquet"
    )


def test_strata_s3_path_helpers_match_their_https_url_counterparts():
    """Added in Stage 2 Step 4 (src/io.py) to fix an asymmetry: reference layers had both an S3
    and an HTTPS path builder, strata tables only had HTTPS. Pinned here the same way
    test_reference_s3_path_matches_its_https_url_counterpart pins the reference-layer pair, so a
    typo in either new function fails loudly here rather than 404ing against the live bucket."""
    assert config.strata_s3_path("maricopa-az", "census-tracts") == (
        "us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
        "/strata/maricopa-az/maricopa-az-census-tracts.parquet"
    )
    assert config.strata_s3_path("maricopa-az", "census-tracts") == config.strata_url(
        "maricopa-az", "census-tracts"
    ).replace("https://data.source.coop/", "us-west-2.opendata.source.coop/")

    assert config.strata_national_s3_path(config.STRATA_NATIONAL_JOINED_TABLE) == (
        "us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
        "/strata/national/national-strata-tract-table.parquet"
    )
    assert config.strata_national_s3_path(
        config.STRATA_NATIONAL_JOINED_TABLE
    ) == config.strata_national_url(config.STRATA_NATIONAL_JOINED_TABLE).replace(
        "https://data.source.coop/", "us-west-2.opendata.source.coop/"
    )


# --- src/cli.py ------------------------------------------------------------------------------------


def test_help_flag_exits_zero(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0


def test_no_command_is_rejected():
    """`command` is required — running the CLI with nothing at all must fail argparse's own
    validation (exit code 2), never silently do nothing."""
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2


@pytest.mark.parametrize("region", ["maricopa-az", "northern-ca", "eastern-ok", "south-central-tx"])
def test_features_accepts_every_real_region(region):
    parser = build_parser()
    args = parser.parse_args(["features", "--region", region])
    assert args.region == region
    assert args.command == "features"


def test_features_rejects_an_invalid_region():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["features", "--region", "not-a-real-region"])
    assert exc_info.value.code == 2


def test_features_requires_region():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["features"])
    assert exc_info.value.code == 2


def test_score_accepts_a_real_region():
    parser = build_parser()
    args = parser.parse_args(["score", "--region", "eastern-ok"])
    assert args.region == "eastern-ok"


def test_audit_accepts_its_full_flag_set():
    parser = build_parser()
    args = parser.parse_args(
        [
            "audit",
            "--region",
            "eastern-ok",
            "northern-ca",
            "--layers",
            "overture-buildings",
            "census-cbp",
            "--skip-strata",
            "--output",
            "somewhere.csv",
        ]
    )
    assert args.region == ["eastern-ok", "northern-ca"]
    assert args.layers == ["overture-buildings", "census-cbp"]
    assert args.skip_strata is True
    assert str(args.output) == "somewhere.csv"


def test_audit_defaults_are_none_when_no_flags_given():
    """Defaults must be None/False here, not audit_bucket.py's own defaults duplicated — cmd_audit
    relies on omitting a flag entirely from the forwarded argv when it's None/False, letting
    audit_bucket.py's parser apply its own defaults exactly once, in one place."""
    parser = build_parser()
    args = parser.parse_args(["audit"])
    assert args.region is None
    assert args.layers is None
    assert args.skip_strata is False
    assert args.output is None


def test_audit_rejects_an_invalid_region():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["audit", "--region", "not-a-real-region"])
    assert exc_info.value.code == 2


def test_validate_submission_default_path_is_set():
    parser = build_parser()
    args = parser.parse_args(["validate-submission"])
    assert args.path.name == "submission.csv"
    assert args.path.parent.name == "submissions"


@pytest.mark.parametrize(
    "argv",
    [
        ["eda"],
        ["features", "--region", "eastern-ok"],
        ["score", "--region", "eastern-ok"],
        ["build-submission"],
        ["validate-submission"],
    ],
)
def test_every_still_unbuilt_subcommand_is_a_clean_stub(argv):
    """Every subcommand whose stage hasn't been built yet is expected to be unimplemented right
    now — this pins that down explicitly, so the moment a stage really is implemented, this
    specific test starts failing and has to be deliberately updated (as already happened for
    "audit" below, once Stage 2 was built), rather than a stub silently staying a stub past its
    stage. "audit" is deliberately excluded from this list — see the cmd_audit tests below, which
    replaced its stub-behavior coverage once Stage 2 wired it up for real."""
    assert main(argv) == 2


def test_main_accepts_an_explicit_argv_list():
    """main() takes an explicit argv rather than reading sys.argv, specifically so it's callable
    like this from a test without subprocessing or monkeypatching sys.argv. Uses "eda" (still a
    genuine stub) rather than "audit", which now really runs (see the cmd_audit tests below)."""
    assert main(["eda"]) == 2


# --- src/cli.py: cmd_audit (Stage 2 is built; this subcommand is real, not a stub) ---------------


def test_cmd_audit_forwards_parsed_arguments_to_audit_bucket_main(monkeypatch):
    """cmd_audit is a thin translator from `python -m src.cli audit` flags to
    `scripts/audit/audit_bucket.py`'s own CLI, not a re-implementation of any audit logic — that
    logic is already tested in tests/test_audit_bucket.py. This confirms the translation is
    correct without ever touching the network: audit_bucket's real `main` is monkeypatched out."""
    import scripts.audit.audit_bucket as audit_bucket

    captured: dict = {}

    def fake_audit_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(audit_bucket, "main", fake_audit_main)

    exit_code = main(
        [
            "audit",
            "--region",
            "eastern-ok",
            "maricopa-az",
            "--layers",
            "overture-buildings",
            "--skip-strata",
            "--output",
            "custom_output.csv",
        ]
    )
    assert exit_code == 0
    assert captured["argv"] == [
        "--region",
        "eastern-ok",
        "maricopa-az",
        "--layers",
        "overture-buildings",
        "--skip-strata",
        "--output",
        "custom_output.csv",
    ]


def test_cmd_audit_with_no_flags_forwards_an_empty_argv(monkeypatch):
    """No flags passed to `python -m src.cli audit` must forward no flags at all to
    audit_bucket.py's CLI — letting THAT parser apply its own defaults (all four regions, every
    registered layer, strata included), rather than cmd_audit silently re-deciding defaults of its
    own that could drift from audit_bucket.py's."""
    import scripts.audit.audit_bucket as audit_bucket

    captured: dict = {}

    def fake_audit_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(audit_bucket, "main", fake_audit_main)

    assert main(["audit"]) == 0
    assert captured["argv"] == []
