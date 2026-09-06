"""Tests for scripts/tag_candidate_hypotheses.py (Stage 3 Step 6).

This step needs no live bucket access — every input is already committed, real data from Steps 2
and 5 (docs/column_domain_map.csv, docs/column_classification.csv) plus the fixed, already-written
Stage 9 candidate pool from PROJECT_BLUEPRINT.md (encoded, not re-derived, here). Tested against
small hand-built fixtures AND, where the real committed files are present, against the real 232-
column data itself.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import scripts.tag_candidate_hypotheses as mod

REAL_DOMAIN_MAP_CSV = Path(__file__).resolve().parent.parent / "docs" / "column_domain_map.csv"
REAL_CLASSIFICATION_CSV = Path(__file__).resolve().parent.parent / "docs" / "column_classification.csv"
REAL_INPUTS_PRESENT = REAL_DOMAIN_MAP_CSV.exists() and REAL_CLASSIFICATION_CSV.exists()


# --- tag_column: the allowed_for_bias=False override always wins --------------------------------


def test_allowed_for_bias_false_always_produces_no_tags_regardless_of_role_or_domain():
    for role in ["identifier", "vintage_metadata", "coverage_flag", "measurement", "geometry_measure", "population"]:
        tags, reason = mod.tag_column("some_column", role, "wildfire", allowed_for_bias=False)
        assert tags == []
        assert "allowed_for_bias=False" in reason


def test_allowed_for_bias_false_wins_even_for_an_explicitly_named_identity_metadata_column():
    """The identity-metadata per-column overrides must not bypass the allowed_for_bias guard."""
    tags, reason = mod.tag_column("aiannh_geoid", "identity_metadata", "tribal", allowed_for_bias=False)
    assert tags == []
    assert "allowed_for_bias=False" in reason


# --- tag_column: role-based defaults -------------------------------------------------------------


def test_coverage_flag_gets_only_measurement_eligibility_bias():
    tags, _ = mod.tag_column("svi_covered", "coverage_flag", "svi", allowed_for_bias=True)
    assert tags == [mod.MEASUREMENT_ELIGIBILITY_BIAS]


def test_derived_ever_flag_gets_meb_and_component_dominance():
    tags, _ = mod.tag_column("fod_ever", "derived_ever_flag", "wildfire", allowed_for_bias=True)
    assert set(tags) == {mod.MEASUREMENT_ELIGIBILITY_BIAS, mod.COMPONENT_DOMINANCE}


def test_geometry_measure_gets_tribal_edge_effect_and_dispatch_blind():
    tags, _ = mod.tag_column("ALAND", "geometry_measure", "geography", allowed_for_bias=True)
    assert set(tags) == {mod.TRIBAL_SUBTYPE_EDGE_EFFECT, mod.DISPATCH_BLIND_REACHABILITY}


def test_population_gets_three_specific_candidates():
    tags, _ = mod.tag_column("pop_total", "population", "population", allowed_for_bias=True)
    assert set(tags) == {mod.POPULATION_EXPOSURE_DISPARITY, mod.COMPONENT_DOMINANCE, mod.DISPATCH_BLIND_REACHABILITY}


# --- tag_column: identity_metadata explicit per-column rules ------------------------------------


def test_aiannh_columns_get_tribal_edge_effect_and_population_exposure():
    for column in ["aiannh_geoid", "aiannh_name"]:
        tags, _ = mod.tag_column(column, "identity_metadata", "tribal", allowed_for_bias=True)
        assert set(tags) == {mod.TRIBAL_SUBTYPE_EDGE_EFFECT, mod.POPULATION_EXPOSURE_DISPARITY}


def test_uhe_city_columns_get_only_source_provenance():
    for column in ["uhe_city_name", "uhe_city_country"]:
        tags, _ = mod.tag_column(column, "identity_metadata", "heat", allowed_for_bias=True)
        assert tags == [mod.SOURCE_PROVENANCE_X_VULNERABILITY]


def test_unrecognized_identity_metadata_column_falls_through_without_crashing():
    """A future identity_metadata column not in IDENTITY_METADATA_TAGS should not raise — it just
    gets no per-column override tags. (It would still need its own rule added to be genuinely
    useful, but this must not be a hard failure.)"""
    tags, reason = mod.tag_column("some_new_identity_column", "identity_metadata", "heat", allowed_for_bias=True)
    assert tags == []


# --- tag_column: measurement role, domain defaults + column-specific overrides -------------------


@pytest.mark.parametrize("domain", ["svi", "cvi", "wildfire", "heat", "drought"])
def test_generic_hazard_vulnerability_domains_get_the_three_generic_covariate_tags(domain):
    tags, _ = mod.tag_column("some_measurement_column", "measurement", domain, allowed_for_bias=True)
    assert set(tags) == {mod.MEASUREMENT_ELIGIBILITY_BIAS, mod.SOURCE_PROVENANCE_X_VULNERABILITY, mod.COMPONENT_DOMINANCE}


def test_rurality_measurement_gets_the_generic_tags_plus_dispatch_blind():
    tags, _ = mod.tag_column("ruca_pop_density", "measurement", "rurality", allowed_for_bias=True)
    assert set(tags) == {
        mod.MEASUREMENT_ELIGIBILITY_BIAS,
        mod.SOURCE_PROVENANCE_X_VULNERABILITY,
        mod.COMPONENT_DOMINANCE,
        mod.DISPATCH_BLIND_REACHABILITY,
    }


def test_tribal_measurement_gets_the_generic_tags_plus_three_more():
    tags, _ = mod.tag_column("tribal_pct", "measurement", "tribal", allowed_for_bias=True)
    assert set(tags) == {
        mod.MEASUREMENT_ELIGIBILITY_BIAS,
        mod.SOURCE_PROVENANCE_X_VULNERABILITY,
        mod.COMPONENT_DOMINANCE,
        mod.DISPATCH_BLIND_REACHABILITY,
        mod.TRIBAL_SUBTYPE_EDGE_EFFECT,
        mod.POPULATION_EXPOSURE_DISPARITY,
    }


def test_cvi_pillar_columns_get_cvi_pillar_decomposition_on_top_of_the_domain_default():
    for column in mod.CVI_PILLAR_COLUMNS:
        tags, _ = mod.tag_column(column, "measurement", "cvi", allowed_for_bias=True)
        assert mod.CVI_PILLAR_DECOMPOSITION in tags
        assert mod.MEASUREMENT_ELIGIBILITY_BIAS in tags  # generic domain default still applies


def test_cvi_overall_and_xwalk_coverage_do_not_get_pillar_decomposition():
    for column in ["cvi_overall", "cvi_xwalk_coverage"]:
        tags, _ = mod.tag_column(column, "measurement", "cvi", allowed_for_bias=True)
        assert mod.CVI_PILLAR_DECOMPOSITION not in tags


def test_rurality_disagreement_columns_get_the_disagreement_tag_on_top_of_the_domain_default():
    for column in mod.RURALITY_DISAGREEMENT_COLUMNS:
        tags, _ = mod.tag_column(column, "measurement", "rurality", allowed_for_bias=True)
        assert mod.RUCA_RUCC_NCHS_DISAGREEMENT in tags
        assert mod.DISPATCH_BLIND_REACHABILITY in tags  # domain default still applies


def test_ruca_pop_density_does_not_get_the_disagreement_tag():
    tags, _ = mod.tag_column("ruca_pop_density", "measurement", "rurality", allowed_for_bias=True)
    assert mod.RUCA_RUCC_NCHS_DISAGREEMENT not in tags


def test_measurement_role_in_an_unmapped_domain_raises_loudly_instead_of_silently_under_tagging():
    """A measurement-role, allowed_for_bias=True column in a domain not in MEASUREMENT_DOMAIN_TAGS
    (e.g. a hypothetical future domain from a Step 2 refresh) must fail loudly rather than silently
    getting candidate_hypotheses="" — indistinguishable from a deliberately untagged column. This
    was originally a silent empty-list fallback; changed after this review found that an unmapped
    domain would otherwise be invisible."""
    with pytest.raises(AssertionError):
        mod.tag_column("some_column", "measurement", "some_future_domain", allowed_for_bias=True)


# --- tag_column: the identifier/vintage_metadata unreachable-branch guard ------------------------


def test_identifier_role_with_allowed_for_bias_true_raises_loudly_rather_than_silently_mistagging():
    """This combination should never occur in real data (Step 5 always forces identifier to
    allowed_for_bias=False) — if it ever did, this must fail loudly, not silently return []."""
    with pytest.raises(AssertionError):
        mod.tag_column("GEOID", "identifier", "geography", allowed_for_bias=True)


def test_vintage_metadata_role_with_allowed_for_bias_true_raises_loudly():
    with pytest.raises(AssertionError):
        mod.tag_column("some_vintage_col", "vintage_metadata", "heat", allowed_for_bias=True)


# --- Dropped candidates must never be assignable --------------------------------------------------


def test_dropped_candidates_are_never_in_the_taggable_vocabulary():
    for dropped in mod.DROPPED_CANDIDATES:
        assert dropped not in mod.ALL_CANDIDATES


def test_no_rule_anywhere_in_the_module_can_produce_a_dropped_candidate_string():
    """Exercises every role/domain combination the tagging function actually branches on and checks
    none of them can ever produce a dropped-candidate string — a static text search over the source
    would miss a rule that builds a dropped name dynamically, so this drives the real function."""
    dropped_names = set(mod.DROPPED_CANDIDATES)
    domain_independent_roles = ["coverage_flag", "derived_ever_flag", "geometry_measure", "population"]
    produced = set()
    for role in domain_independent_roles:
        # domain is irrelevant to these roles' rules, but pass a real one anyway rather than a
        # placeholder, so this test exercises the actual production code path.
        tags, _ = mod.tag_column("probe_column", role, "wildfire", allowed_for_bias=True)
        produced.update(tags)
    for domain in mod.MEASUREMENT_DOMAIN_TAGS:  # every domain measurement-role columns can legally have
        tags, _ = mod.tag_column("probe_column", "measurement", domain, allowed_for_bias=True)
        produced.update(tags)
    for column in list(mod.IDENTITY_METADATA_TAGS) + list(mod.CVI_PILLAR_COLUMNS) + list(mod.RURALITY_DISAGREEMENT_COLUMNS):
        tags, _ = mod.tag_column(column, "identity_metadata", "tribal", allowed_for_bias=True)
        produced.update(tags)
        tags, _ = mod.tag_column(column, "measurement", "cvi", allowed_for_bias=True)
        produced.update(tags)
    assert not (produced & dropped_names)


# --- build_classification / build_tagging ---------------------------------------------------------


def _make_domain_map(rows):
    return pd.DataFrame.from_records(rows)


def _make_classification(rows):
    return pd.DataFrame.from_records(rows)


def test_build_tagging_produces_one_row_per_domain_map_row_with_expected_columns():
    domain_map = _make_domain_map(
        [
            {"column_name": "GEOID", "source_table": "t", "domain": "geography", "dtype": "string"},
            {"column_name": "svi_covered", "source_table": "t2", "domain": "svi", "dtype": "bool"},
        ]
    )
    classification = _make_classification(
        [
            {"column_name": "GEOID", "role": "identifier", "allowed_for_bias": False},
            {"column_name": "svi_covered", "role": "coverage_flag", "allowed_for_bias": True},
        ]
    )
    result = mod.build_tagging(domain_map, classification)
    assert len(result) == 2
    assert list(result.columns) == [
        "column_name",
        "source_table",
        "domain",
        "role",
        "allowed_for_bias",
        "candidate_hypotheses",
        "candidate_hypotheses_reason",
    ]
    by_column = result.set_index("column_name")
    assert by_column.loc["GEOID", "candidate_hypotheses"] == ""
    assert by_column.loc["svi_covered", "candidate_hypotheses"] == mod.MEASUREMENT_ELIGIBILITY_BIAS


def test_build_tagging_joins_multiple_tags_with_the_declared_separator():
    domain_map = _make_domain_map([{"column_name": "pop_total", "source_table": "t", "domain": "population", "dtype": "int64"}])
    classification = _make_classification([{"column_name": "pop_total", "role": "population", "allowed_for_bias": True}])
    result = mod.build_tagging(domain_map, classification)
    value = result.iloc[0]["candidate_hypotheses"]
    assert mod.TAG_SEPARATOR in value
    assert set(value.split(mod.TAG_SEPARATOR)) == {mod.POPULATION_EXPOSURE_DISPARITY, mod.COMPONENT_DOMINANCE, mod.DISPATCH_BLIND_REACHABILITY}


# --- main() error handling -------------------------------------------------------------------------


def test_main_returns_a_clean_error_when_domain_map_is_missing(tmp_path, capsys):
    rc = mod.main(["--domain-map", str(tmp_path / "nope.csv")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_returns_a_clean_error_when_classification_is_missing(tmp_path, capsys):
    domain_map_path = tmp_path / "domain_map.csv"
    pd.DataFrame([{"column_name": "GEOID", "source_table": "t", "domain": "geography", "dtype": "string"}]).to_csv(domain_map_path, index=False)
    rc = mod.main(["--domain-map", str(domain_map_path), "--classification", str(tmp_path / "nope.csv")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_returns_a_clean_error_when_a_domain_map_column_has_no_classification_row(tmp_path, capsys):
    domain_map_path = tmp_path / "domain_map.csv"
    classification_path = tmp_path / "classification.csv"
    pd.DataFrame(
        [
            {"column_name": "GEOID", "source_table": "t", "domain": "geography", "dtype": "string"},
            {"column_name": "mystery_column", "source_table": "t", "domain": "geography", "dtype": "string"},
        ]
    ).to_csv(domain_map_path, index=False)
    pd.DataFrame([{"column_name": "GEOID", "role": "identifier", "allowed_for_bias": False}]).to_csv(classification_path, index=False)
    rc = mod.main(["--domain-map", str(domain_map_path), "--classification", str(classification_path)])
    assert rc == 2
    assert "mystery_column" in capsys.readouterr().err


def test_main_writes_the_tagging_csv_and_returns_zero(tmp_path):
    domain_map_path = tmp_path / "domain_map.csv"
    classification_path = tmp_path / "classification.csv"
    output_path = tmp_path / "out.csv"
    pd.DataFrame([{"column_name": "svi_covered", "source_table": "t", "domain": "svi", "dtype": "bool"}]).to_csv(domain_map_path, index=False)
    pd.DataFrame([{"column_name": "svi_covered", "role": "coverage_flag", "allowed_for_bias": True}]).to_csv(classification_path, index=False)
    rc = mod.main(
        [
            "--domain-map", str(domain_map_path),
            "--classification", str(classification_path),
            "--output", str(output_path),
        ]
    )
    assert rc == 0
    assert output_path.exists()
    result = pd.read_csv(output_path, keep_default_na=False)
    assert len(result) == 1


# --- Real-data regression tests --------------------------------------------------------------------


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_produces_exactly_232_rows_with_189_tagged_and_43_blank():
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    result = mod.build_tagging(domain_map, classification)
    assert len(result) == 232
    n_tagged = (result["candidate_hypotheses"] != "").sum()
    assert n_tagged == 189
    assert (result["candidate_hypotheses"] == "").sum() == 43


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_blank_tag_set_exactly_matches_the_known_allowed_for_bias_false_columns():
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    result = mod.build_tagging(domain_map, classification)
    blank_columns = set(result.loc[result["candidate_hypotheses"] == "", "column_name"])
    false_columns = set(classification.loc[~classification["allowed_for_bias"], "column_name"])
    assert blank_columns == false_columns


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_confirms_the_two_zero_match_candidates_stay_at_zero():
    """Locks in, against the real data, the module docstring's claim that Confidence Reporting-Rate
    and Colonias in South-Central TX get zero strata columns — this is meant to be true, and this
    test is what keeps it from silently becoming false if the tagging rules are ever edited."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    result = mod.build_tagging(domain_map, classification)
    for candidate in mod.CANDIDATES_WITH_NO_STRATA_COLUMNS:
        count = mod.columns_feeding(result, candidate)
        assert count == 0, f"{candidate} was expected to have zero feeding columns but has {count}"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_every_candidate_that_is_not_supposed_to_be_zero_actually_has_columns():
    """The flip side of the previous test — every candidate NOT in CANDIDATES_WITH_NO_STRATA_COLUMNS
    must have at least one real column feeding it, or the tagging rules have a dead candidate that
    was not supposed to be dead."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    result = mod.build_tagging(domain_map, classification)
    for candidate in mod.ALL_CANDIDATES:
        if candidate in mod.CANDIDATES_WITH_NO_STRATA_COLUMNS:
            continue
        count = mod.columns_feeding(result, candidate)
        assert count > 0, f"{candidate} unexpectedly has zero feeding columns"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_no_column_is_ever_tagged_with_a_dropped_candidate():
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    result = mod.build_tagging(domain_map, classification)
    for dropped in mod.DROPPED_CANDIDATES:
        count = mod.columns_feeding(result, dropped)
        assert count == 0, f"dropped candidate {dropped!r} appears in {count} real column tags"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_every_hand_typed_override_column_actually_exists_in_the_real_domain_map():
    """Same class of regression guard added during Step 5's review pass: CVI_PILLAR_COLUMNS,
    RURALITY_DISAGREEMENT_COLUMNS, and IDENTITY_METADATA_TAGS' keys are all hand-typed; a typo in
    any of them would silently never match a real column rather than raising."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    real_columns = set(domain_map["column_name"])
    hand_typed_sets = {
        "CVI_PILLAR_COLUMNS": mod.CVI_PILLAR_COLUMNS,
        "RURALITY_DISAGREEMENT_COLUMNS": mod.RURALITY_DISAGREEMENT_COLUMNS,
        "IDENTITY_METADATA_TAGS keys": set(mod.IDENTITY_METADATA_TAGS),
    }
    for set_name, column_set in hand_typed_sets.items():
        missing = column_set - real_columns
        assert not missing, f"{set_name} contains column(s) not present in the real domain map (typo?): {sorted(missing)}"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_cvi_pillar_and_rurality_disagreement_columns_are_a_strict_subset_of_measurement_role():
    """A typo that accidentally names a coverage_flag or identifier column in one of these override
    sets would silently do nothing (tag_column only applies the override inside the measurement
    branch) — this test makes that loud instead."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    role_by_column = dict(zip(classification["column_name"], classification["role"]))
    for column in mod.CVI_PILLAR_COLUMNS | mod.RURALITY_DISAGREEMENT_COLUMNS:
        assert role_by_column[column] == "measurement", f"{column} has role={role_by_column[column]!r}, expected measurement"


# --- Review-pass additions: parse_tags / columns_feeding, substring-collision guard, and the
# unmapped-measurement-domain hard failure -------------------------------------------------------


def test_measurement_domain_tags_never_produces_an_alias_bug_across_domains():
    """MEASUREMENT_DOMAIN_TAGS builds each domain's list from _GENERIC_COVARIATE_TAGS via `list(...)`
    or `+`, both of which copy rather than alias — mutating one domain's tag list (as tag_column
    does internally when it appends pillar/disagreement overrides) must never leak into another
    domain's list or into _GENERIC_COVARIATE_TAGS itself."""
    tags_before = list(mod.MEASUREMENT_DOMAIN_TAGS["cvi"])
    probe_tags, _ = mod.tag_column("cvi_baseline_health", "measurement", "cvi", allowed_for_bias=True)
    probe_tags.append("SOMETHING_THAT_SHOULD_NOT_LEAK")
    assert mod.MEASUREMENT_DOMAIN_TAGS["cvi"] == tags_before
    assert mod.MEASUREMENT_DOMAIN_TAGS["svi"] == list(mod._GENERIC_COVARIATE_TAGS)
    assert "SOMETHING_THAT_SHOULD_NOT_LEAK" not in mod._GENERIC_COVARIATE_TAGS


def test_no_candidate_name_is_a_substring_of_another_candidate_or_dropped_name():
    """Guards the assumption columns_feeding's exact-match parsing was added to make irrelevant, but
    checked directly anyway: if this ever became false via a rename, any code still doing substring
    search (present or future) would silently miscount."""
    names = list(mod.ALL_CANDIDATES) + list(mod.DROPPED_CANDIDATES)
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i != j:
                assert a not in b, f"{a!r} is a substring of {b!r} — would break any substring-based counting"


def test_parse_tags_treats_blank_nan_and_none_as_no_tags():
    assert mod.parse_tags("") == []
    assert mod.parse_tags(None) == []
    assert mod.parse_tags(float("nan")) == []


def test_parse_tags_splits_multiple_tags_exactly():
    joined = mod.TAG_SEPARATOR.join([mod.MEASUREMENT_ELIGIBILITY_BIAS, mod.COMPONENT_DOMINANCE])
    assert mod.parse_tags(joined) == [mod.MEASUREMENT_ELIGIBILITY_BIAS, mod.COMPONENT_DOMINANCE]


def test_columns_feeding_counts_exact_tags_not_substrings():
    tagging = pd.DataFrame(
        {
            "candidate_hypotheses": [
                mod.TAG_SEPARATOR.join([mod.MEASUREMENT_ELIGIBILITY_BIAS]),
                mod.TAG_SEPARATOR.join([mod.MEASUREMENT_ELIGIBILITY_BIAS, mod.COMPONENT_DOMINANCE]),
                "",
            ]
        }
    )
    assert mod.columns_feeding(tagging, mod.MEASUREMENT_ELIGIBILITY_BIAS) == 2
    assert mod.columns_feeding(tagging, mod.COMPONENT_DOMINANCE) == 1


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_columns_feeding_matches_between_a_freshly_built_dataframe_and_the_real_csv_read_back_without_keep_default_na():
    """Proves the NaN-tolerance fix actually matters, not just in theory: reads the real, already-
    committed docs/column_candidate_hypotheses.csv with plain pd.read_csv (no keep_default_na=False,
    which is what a downstream script would do by default), and checks columns_feeding gives the
    same answer as computing straight from build_tagging's in-memory output."""
    output_csv = Path(__file__).resolve().parent.parent / "docs" / "column_candidate_hypotheses.csv"
    if not output_csv.exists():
        pytest.skip("docs/column_candidate_hypotheses.csv not present")

    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    fresh = mod.build_tagging(domain_map, classification)

    from_disk = pd.read_csv(output_csv)  # deliberately NOT passing keep_default_na=False
    assert from_disk["candidate_hypotheses"].isna().any(), "expected at least one blank cell to round-trip as NaN for this test to be meaningful"

    for candidate in mod.ALL_CANDIDATES:
        assert mod.columns_feeding(from_disk, candidate) == mod.columns_feeding(fresh, candidate), f"mismatch for {candidate}"


@pytest.mark.skipif(not REAL_INPUTS_PRESENT, reason="real committed inputs not present")
def test_real_run_every_measurement_domain_present_in_the_data_is_mapped():
    """Locks in, against the real data, that every domain a measurement-role column actually
    belongs to has a MEASUREMENT_DOMAIN_TAGS entry — the condition the new AssertionError in
    tag_column guards. If Step 2 is ever re-run against a refreshed schema with a new domain, this
    is the test that should fail first, pointing directly at the fix needed."""
    domain_map = pd.read_csv(REAL_DOMAIN_MAP_CSV)
    classification = pd.read_csv(REAL_CLASSIFICATION_CSV)
    merged = domain_map.merge(classification[["column_name", "role", "allowed_for_bias"]], on="column_name")
    measurement_domains = set(merged.loc[merged["role"] == "measurement", "domain"])
    unmapped = measurement_domains - set(mod.MEASUREMENT_DOMAIN_TAGS)
    assert not unmapped, f"measurement-role domain(s) with no MEASUREMENT_DOMAIN_TAGS entry: {unmapped}"
