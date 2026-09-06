"""Stage 3 Step 9 — enforcement test for the exit criterion itself.

Steps 1-8 built and unit-tested the SCRIPTS that produce Stage 3's governance artifacts.
`tests/test_build_data_dictionary.py` (Step 8's own test suite) tests `scripts/build_data_
dictionary.py`'s pure functions against synthetic fixtures — it never looks at the real, committed
`docs/schema_catalog.csv` or `docs/DATA_DICTIONARY.md` at all. This file is different in kind, not
degree: it is the standing, permanent contract that the real, committed OUTPUT ARTIFACTS themselves
— the actual files Henry's live run produced and that ship in this repository — are correct, complete,
internally consistent, and reproducible from their own real inputs. This is Stage 3's exit criterion
(Gate A, "Data Trusted," in `PROJECT_BLUEPRINT.md`'s terms): once this file passes, the data-audit
phase is closed and every later stage (Bias Discovery hypothesis mining chief among them) can read
`docs/schema_catalog.csv` as a trusted, load-bearing fact rather than something that might silently
be stale or hand-edited out of sync with the real data.

Every test here reads the real, already-committed files under `docs/` — there is no synthetic
fixture in this file at all, deliberately, since the whole point is to check the real artifact, not
a stand-in for it. Tests are skipped (not failed) if a required file does not yet exist, matching
this project's established convention for every other Stage 3 test module — but once Step 8 has
been run for real (as it now has), every test here runs for real and enforces for real.

Runs as part of the ordinary `pytest` invocation — no separate script, no CLI, no live bucket
access needed anywhere in this file. This is intentional: Henry's standing instruction is to build
only what a stage actually asks for, and "an enforcement test" means exactly that — test code, not
another script or tool.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import scripts.build_data_dictionary as build_mod
import scripts.tag_candidate_hypotheses as tag_mod

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"

SCHEMA_CATALOG_PATH = build_mod.DEFAULT_CATALOG_OUTPUT_PATH
DICTIONARY_PATH = build_mod.DEFAULT_DICTIONARY_OUTPUT_PATH

_REQUIRED_UPSTREAM_PATHS = [
    SCHEMA_CATALOG_PATH,
    DICTIONARY_PATH,
    build_mod.DEFAULT_NATIONAL_SCHEMA_PATH,
    build_mod.DEFAULT_DOMAIN_MAP_PATH,
    build_mod.DEFAULT_NULL_PROFILE_PATH,
    build_mod.DEFAULT_CLASSIFICATION_PATH,
    build_mod.DEFAULT_CANDIDATE_HYPOTHESES_PATH,
    build_mod.DEFAULT_REGION_CONSISTENCY_PATH,
]
REAL_ARTIFACTS_PRESENT = all(p.exists() for p in _REQUIRED_UPSTREAM_PATHS)

pytestmark = pytest.mark.skipif(
    not REAL_ARTIFACTS_PRESENT,
    reason="Stage 3 Step 8's real output artifacts (docs/schema_catalog.csv, docs/DATA_DICTIONARY.md) "
    "and/or their upstream inputs are not present yet — run scripts/build_data_dictionary.py first.",
)

# Six columns Step 7 confirmed, live, are absent from every one of the four regions' own joined
# strata tables (docs/data_manifest.md Section 4.17) — a fixed, named regression set, not derived
# fresh in this file, so a change to this list is itself a signal something upstream drifted.
_EXPECTED_MISSING_FROM_ALL_REGIONS = {
    "state_usps", "state_name", "AWATER", "INTPTLAT", "INTPTLON", "tract_vintage",
}


@pytest.fixture(scope="module")
def schema_catalog() -> pd.DataFrame:
    return pd.read_csv(SCHEMA_CATALOG_PATH)


@pytest.fixture(scope="module")
def schema_catalog_keep_na() -> pd.DataFrame:
    # A second read with keep_default_na=False for the checks that specifically care whether a
    # cell is a real empty string vs. missing — see tag_mod.parse_tags's own docstring for why a
    # plain pd.read_csv() is not safe for blank candidate_hypotheses cells.
    return pd.read_csv(SCHEMA_CATALOG_PATH, keep_default_na=False)


@pytest.fixture(scope="module")
def dictionary_text() -> str:
    return DICTIONARY_PATH.read_text(encoding="utf-8")


# -------------------------------------------------------------------------------------------
# The single most safety-critical invariant in this entire project
# -------------------------------------------------------------------------------------------


def test_allowed_for_scoring_is_false_for_every_single_row_without_exception(schema_catalog):
    """This is Gate A's actual scoring-safety condition. national-strata-tract-table and its
    region-level counterpart both live entirely under strata/, never reference/ — the challenge's
    own rule is that the scored coverage-gap computation may only use reference/ data. If this test
    ever fails, it means a `strata/` column could influence the submitted leaderboard number, which
    would not just be a bug — it would look like an attempt to smuggle disallowed signal into the
    scored computation. This must be checked directly against the real file, not just trusted from
    Step 5's original reasoning."""
    bad = schema_catalog.loc[schema_catalog["allowed_for_scoring"] != False, "column_name"].tolist()  # noqa: E712
    assert bad == [], f"{len(bad)} column(s) have allowed_for_scoring != False: {bad}"


# -------------------------------------------------------------------------------------------
# Shape and completeness
# -------------------------------------------------------------------------------------------


def test_schema_catalog_has_exactly_233_rows_with_no_duplicate_column_names(schema_catalog):
    assert len(schema_catalog) == 233
    dupes = schema_catalog.loc[schema_catalog["column_name"].duplicated(), "column_name"].tolist()
    assert dupes == [], f"duplicate column_name(s) in schema_catalog.csv: {dupes}"


def test_exactly_one_region_only_row_and_it_is_frac_inside_aoi(schema_catalog):
    region_only = schema_catalog.loc[schema_catalog["region_only"] == True, "column_name"].tolist()  # noqa: E712
    assert region_only == ["frac_inside_aoi"]


def test_every_real_national_column_is_present_in_schema_catalog(schema_catalog):
    national_schema = pd.read_csv(build_mod.DEFAULT_NATIONAL_SCHEMA_PATH)
    national_columns = build_mod.load_national_joined_columns(national_schema)
    missing = set(national_columns["column_name"]) - set(schema_catalog["column_name"])
    assert missing == set(), f"national column(s) missing from schema_catalog.csv: {missing}"


@pytest.mark.parametrize(
    "upstream_path_attr,upstream_label",
    [
        ("DEFAULT_DOMAIN_MAP_PATH", "column_domain_map.csv (Step 2)"),
        ("DEFAULT_CLASSIFICATION_PATH", "column_classification.csv (Step 5)"),
        ("DEFAULT_CANDIDATE_HYPOTHESES_PATH", "column_candidate_hypotheses.csv (Step 6)"),
    ],
)
def test_every_national_schema_catalog_column_has_full_traceability_to_every_upstream_step(
    schema_catalog, upstream_path_attr, upstream_label
):
    """Every one of the 232 real national columns must be traceable to every upstream Stage 3 step
    that classified it — not just merged once and forgotten. Checked in both directions: a column
    schema_catalog.csv carries but an upstream file doesn't (the missing-match gap Step 8's own
    review pass already found and fixed once — this locks it in permanently against the real
    committed files) and the reverse (an upstream file classifies a column schema_catalog.csv
    somehow dropped)."""
    upstream = pd.read_csv(getattr(build_mod, upstream_path_attr))
    national_rows = schema_catalog.loc[~schema_catalog["region_only"]]
    missing_from_upstream = set(national_rows["column_name"]) - set(upstream["column_name"])
    missing_from_catalog = set(upstream["column_name"]) - set(national_rows["column_name"])
    assert missing_from_upstream == set(), (
        f"national column(s) in schema_catalog.csv with no matching row in {upstream_label}: "
        f"{missing_from_upstream}"
    )
    assert missing_from_catalog == set(), (
        f"column(s) in {upstream_label} with no matching row in schema_catalog.csv: {missing_from_catalog}"
    )


# -------------------------------------------------------------------------------------------
# Internal consistency
# -------------------------------------------------------------------------------------------


def test_every_column_with_allowed_for_bias_false_has_no_candidate_hypotheses(schema_catalog_keep_na):
    """Mirrors Step 6's own tagging rule (`tag_candidate_hypotheses.tag_column`: `if not
    allowed_for_bias: return [], ...`), now enforced against the real, final, merged artifact
    rather than only inside the generator script. A column disallowed for bias analysis must never
    carry a candidate tag, regardless of role or domain."""
    disallowed = schema_catalog_keep_na.loc[schema_catalog_keep_na["allowed_for_bias"] == False]  # noqa: E712
    bad = disallowed.loc[disallowed["candidate_hypotheses"] != "", "column_name"].tolist()
    assert bad == [], f"allowed_for_bias=False column(s) with a non-blank candidate_hypotheses: {bad}"


def test_no_candidate_hypotheses_value_is_a_dropped_candidate(schema_catalog_keep_na):
    """`Wildfire-Rebuilt Areas` and `Heat-Island x SVI` were explicitly dropped from the ten-
    candidate Bias Discovery pool (PROJECT_BLUEPRINT.md's Stage 9 table) and must never appear as a
    tag anywhere in the final artifact — a real regression here would mean dropped work silently
    resurfaced, exactly the kind of inconsistency a Best Bias Discovery judge could catch."""
    for _, row in schema_catalog_keep_na.iterrows():
        tags = tag_mod.parse_tags(row["candidate_hypotheses"] if row["candidate_hypotheses"] else None)
        for tag in tags:
            assert tag not in tag_mod.DROPPED_CANDIDATES, (
                f"{row['column_name']!r} is tagged with dropped candidate {tag!r}"
            )


def test_every_candidate_hypotheses_value_is_a_member_of_the_canonical_ten_candidate_pool(schema_catalog_keep_na):
    unknown: dict[str, list[str]] = {}
    for _, row in schema_catalog_keep_na.iterrows():
        tags = tag_mod.parse_tags(row["candidate_hypotheses"] if row["candidate_hypotheses"] else None)
        bad_tags = [t for t in tags if t not in tag_mod.ALL_CANDIDATES]
        if bad_tags:
            unknown[row["column_name"]] = bad_tags
    assert unknown == {}, f"column(s) tagged with an unrecognized candidate name: {unknown}"


def test_no_row_has_the_vintage_lookup_failure_sentinel(schema_catalog):
    """`vintage_status` is populated by a hand-typed dict lookup (`VINTAGE_STATUS_BY_SOURCE_TABLE`),
    not a DataFrame merge — `build_catalog`'s own `assert_no_missing_vintage_status` should have
    already caught this at generation time, but this test enforces it independently against the
    real committed file, in case that file was ever hand-edited after the fact."""
    bad = schema_catalog.loc[
        schema_catalog["vintage_status"].isin(["MISSING_VINTAGE_ENTRY", "not_profiled"]), "column_name"
    ].tolist()
    assert bad == [], f"column(s) with a vintage lookup failure sentinel: {bad}"


def test_the_six_columns_confirmed_missing_from_every_region_match_step_7_exactly(schema_catalog):
    national_rows = schema_catalog.loc[~schema_catalog["region_only"]]
    actually_missing = set(
        national_rows.loc[national_rows["present_in_all_four_regions"] == False, "column_name"]  # noqa: E712
    )
    assert actually_missing == _EXPECTED_MISSING_FROM_ALL_REGIONS, (
        f"the set of national columns absent from every region's own joined table has drifted: "
        f"expected {_EXPECTED_MISSING_FROM_ALL_REGIONS}, got {actually_missing}"
    )


# -------------------------------------------------------------------------------------------
# frac_inside_aoi — a direct regression lock on the constant-value bug Step 8's own review pass
# found and fixed. This is not a hypothetical: this exact column was hand-classified
# allowed_for_bias=True before the live read proved it constant, and that was wrong.
# -------------------------------------------------------------------------------------------


def test_frac_inside_aoi_is_correctly_classified_given_its_confirmed_constant_real_value(schema_catalog_keep_na):
    row = schema_catalog_keep_na.loc[schema_catalog_keep_na["column_name"] == "frac_inside_aoi"]
    assert len(row) == 1, "frac_inside_aoi must appear exactly once in schema_catalog.csv"
    row = row.iloc[0]
    assert int(row["n_distinct"]) == 1, (
        "frac_inside_aoi's real live n_distinct is no longer 1 — this project's four study regions "
        "may now contain a tract that straddles its own region's AOI boundary. This is a genuine "
        "data-vintage change, not a bug: if this legitimately happened (e.g. the data package was "
        "refreshed), this test's expectation needs a deliberate update, and frac_inside_aoi's "
        "allowed_for_bias classification should be re-examined by hand, not just have this "
        "assertion loosened."
    )
    assert row["allowed_for_bias"] == False, (  # noqa: E712
        "frac_inside_aoi is constant (n_distinct=1) but allowed_for_bias is not False — the "
        "constant-value override (scripts/build_data_dictionary.py's build_frac_inside_aoi_row) "
        "did not fire; this is the exact bug Step 8's own review pass found and fixed once already."
    )
    assert row["candidate_hypotheses"] == "", "a constant column must carry no candidate tag"
    assert row["allowed_for_scoring"] == False  # noqa: E712
    assert "constant" in row["bias_reason"].lower()


# -------------------------------------------------------------------------------------------
# CSV integrity
# -------------------------------------------------------------------------------------------


def test_national_position_never_round_trips_as_a_float_in_the_real_committed_file():
    """Regression guard for the "1.0"-style integer-as-float CSV corruption this project has hit
    multiple times before (Steps 1, 2, and 7) — checked against the RAW TEXT of the real, committed
    file, not a re-parsed DataFrame (reading the CSV back with plain pd.read_csv() would itself
    upcast a column with any NaN to float64, silently masking exactly the bug this test exists to
    catch — see tests/test_build_data_dictionary.py's identical-purpose test for the same reasoning
    applied to a freshly-generated file; this one checks the real file Henry's machine produced)."""
    raw_lines = SCHEMA_CATALOG_PATH.read_text(encoding="utf-8").splitlines()
    header = raw_lines[0].split(",")
    position_idx = header.index("national_position")
    bad_lines = []
    for line in raw_lines[1:]:
        value = line.split(",")[position_idx]
        if value.endswith(".0"):
            bad_lines.append(line[:80])
    assert bad_lines == [], f"national_position round-tripped as a float on {len(bad_lines)} row(s): {bad_lines}"


# -------------------------------------------------------------------------------------------
# The strongest check: is the committed artifact actually reproducible from its own real inputs?
# -------------------------------------------------------------------------------------------


def _extract_frac_inside_aoi_profile(row: pd.Series) -> tuple[dict, list[str]]:
    """Recovers the exact `combined_profile`/`regions_included` values that produced the committed
    `frac_inside_aoi` row, by parsing them back out of `profile_scope` (n_rows, regions_included)
    and reading the numeric fields directly off the row (n_null, pct_null, n_distinct, min, max,
    mean) — so this test can re-derive the row deterministically without needing live bucket access
    (this file, like every other Stage 3 test module, runs with no network at all)."""
    match = re.search(r"\(([\d,]+) tracts across \d+ region\(s\): ([^)]*)\)", row["profile_scope"])
    assert match, f"could not parse profile_scope: {row['profile_scope']!r}"
    n_rows = int(match.group(1).replace(",", ""))
    regions_text = match.group(2)
    regions_included = [] if regions_text == "none" else [r.strip() for r in regions_text.split(",")]
    combined_profile = {
        "n_rows": n_rows,
        "n_null": int(row["n_null"]),
        "pct_null": float(row["pct_null"]),
        "n_distinct": int(row["n_distinct"]),
        "min": float(row["min"]),
        "max": float(row["max"]),
        "mean": float(row["mean"]),
    }
    return combined_profile, regions_included


def test_committed_schema_catalog_is_reproducible_from_its_own_real_committed_inputs(schema_catalog, tmp_path):
    """The definitive Gate A check: rebuild the entire catalog from the real, already-committed
    Step 1/2/3/5/6/7 outputs (never from schema_catalog.csv itself, except to recover
    frac_inside_aoi's live-read profile, which cannot be re-fetched offline — see
    `_extract_frac_inside_aoi_profile`) and assert it matches the committed file exactly. If this
    ever fails, `docs/schema_catalog.csv` has drifted from its own generator and inputs — most
    likely a hand-edit, or a stale file left over from before an upstream CSV was regenerated —
    and must be rebuilt with `python -m scripts.build_data_dictionary` before this project's data
    can be trusted downstream."""
    national_schema_csv = pd.read_csv(build_mod.DEFAULT_NATIONAL_SCHEMA_PATH)
    domain_map = pd.read_csv(build_mod.DEFAULT_DOMAIN_MAP_PATH)
    null_profile = pd.read_csv(build_mod.DEFAULT_NULL_PROFILE_PATH)
    classification = pd.read_csv(build_mod.DEFAULT_CLASSIFICATION_PATH)
    candidate_hypotheses = pd.read_csv(build_mod.DEFAULT_CANDIDATE_HYPOTHESES_PATH)
    region_consistency = pd.read_csv(build_mod.DEFAULT_REGION_CONSISTENCY_PATH)

    national_columns = build_mod.load_national_joined_columns(national_schema_csv)
    region_presence = build_mod.summarize_region_presence(region_consistency)

    committed_frac_row = schema_catalog.loc[schema_catalog["column_name"] == "frac_inside_aoi"].iloc[0]
    combined_profile, regions_included = _extract_frac_inside_aoi_profile(committed_frac_row)

    catalog_columns_template = (
        list(national_columns.columns)
        + ["source_table", "domain", "attribution_method"]
        + ["n_null", "pct_null", "n_distinct", "min", "max", "mean", "sentinel_note"]
        + ["role", "allowed_for_scoring", "scoring_reason", "allowed_for_bias", "bias_reason"]
        + ["candidate_hypotheses", "candidate_hypotheses_reason"]
        + ["present_in_regions", "missing_from_regions", "present_in_all_four_regions"]
        + ["region_only", "profile_scope", "vintage_status", "vintage_note"]
    )
    frac_row = build_mod.build_frac_inside_aoi_row(
        catalog_columns_template, combined_profile, regions_included=regions_included
    )
    rebuilt = build_mod.build_catalog(
        national_columns, domain_map, null_profile, classification, candidate_hypotheses, region_presence, frac_row
    )

    # Round-trip BOTH sides through the identical CSV write/read cycle before comparing — this is
    # what schema_catalog.csv actually IS (a CSV, not a DataFrame), and it neutralizes harmless
    # dtype artifacts (e.g. an int column with one NaN reading back as float64 on both sides
    # equally) without masking a real value difference.
    rebuilt_path = tmp_path / "rebuilt_schema_catalog.csv"
    rebuilt.to_csv(rebuilt_path, index=False)
    rebuilt_reloaded = pd.read_csv(rebuilt_path).sort_values("column_name").reset_index(drop=True)
    committed_sorted = schema_catalog.sort_values("column_name").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        rebuilt_reloaded[committed_sorted.columns.tolist()], committed_sorted, check_dtype=False
    )


def test_committed_dictionary_markdown_matches_the_committed_schema_catalog(schema_catalog_keep_na, dictionary_text):
    """Closes a real gap this project's own review pass found: every other test in this file checks
    `docs/schema_catalog.csv` and `docs/DATA_DICTIONARY.md` separately, against fixed expectations —
    none of them actually confirmed the two files agree WITH EACH OTHER. Two files that are each
    individually plausible can still silently drift apart (a hand-edit to one but not the other, or
    a future code change to one rendering path but not the other) without any single-file check ever
    catching it. This test closes that gap directly: it re-renders the dictionary from the real,
    committed CSV (via `render_data_dictionary_markdown`, the exact same function `main()` calls) and
    asserts the result is byte-for-byte identical to the real, committed `DATA_DICTIONARY.md`.

    Uses the `keep_default_na=False` reading of the CSV, matching what `build_catalog()` actually
    produces in memory (a genuine Python '' for a blank candidate_hypotheses cell, never NaN) — this
    is also, not coincidentally, the exact case `render_data_dictionary_markdown`'s region-only
    section previously mishandled (rendering NaN as the literal string 'nan') until this review pass
    fixed it; using the plain-NA reading here would reintroduce that exact failure mode into this
    test rather than testing the real, correct behavior."""
    rebuilt_markdown = build_mod.render_data_dictionary_markdown(schema_catalog_keep_na)
    assert rebuilt_markdown == dictionary_text, (
        "DATA_DICTIONARY.md is not reproducible from the committed schema_catalog.csv via "
        "render_data_dictionary_markdown — the two committed files have drifted apart from each "
        "other (a hand-edit to one but not the other, or a rendering-logic change not reflected in "
        "the committed output, are the most likely causes). Regenerate both with "
        "`python -m scripts.build_data_dictionary`."
    )


# -------------------------------------------------------------------------------------------
# docs/DATA_DICTIONARY.md content checks
# -------------------------------------------------------------------------------------------


def test_dictionary_domain_table_row_counts_sum_to_232(dictionary_text):
    counts = [int(n) for n in re.findall(r"^### \S+ \((\d+) columns\)$", dictionary_text, flags=re.MULTILINE)]
    assert counts, "no '### <domain> (N columns)' headings found in DATA_DICTIONARY.md"
    assert sum(counts) == 232, f"domain table row counts sum to {sum(counts)}, expected 232: {counts}"


def test_dictionary_lists_exactly_the_six_columns_missing_from_every_region(dictionary_text):
    section_match = re.search(
        r"## Columns absent from every region's own joined table\n\n.*?\n\n((?:- `.*`.*\n)+)",
        dictionary_text,
    )
    assert section_match, "'## Columns absent from every region's own joined table' section not found or empty"
    names = set(re.findall(r"- `([^`]+)`", section_match.group(1)))
    assert names == _EXPECTED_MISSING_FROM_ALL_REGIONS


def test_dictionary_region_only_section_reflects_the_corrected_frac_inside_aoi_classification(dictionary_text):
    assert "## Region-only addition" in dictionary_text
    region_section = dictionary_text.split("## Region-only addition")[1].split("## Columns by domain")[0]
    assert "frac_inside_aoi" in region_section
    assert "allowed_for_bias=False" in region_section
    assert "candidate_hypotheses=''" in region_section


def test_dictionary_states_allowed_for_scoring_is_false_for_every_row(dictionary_text):
    assert "allowed_for_scoring is False for every single row" in dictionary_text
