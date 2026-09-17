"""
src/features.py — Stage 6 (Feature Engineering).

Owned by Stage 6. Responsible for assembling the project's tidy, tract-indexed feature table per
region (`data/processed/<region>-tract-features.parquet`) — the project's lightweight "feature
store." This is where the derived features described in the Stage 6 blueprint entry get built:
`confidence_reporting_rate`/`mean_reported_confidence` (kept as two distinct questions, never
conflated), `dominant_component` (`argmax(transport_gap, building_gap, poi_gap)`),
definedness-pattern features (`n_components_defined` and which component(s) are undefined),
distance-to-tract-boundary for tribal edge-effect analysis, population-weighted gap statistics, and
region carried as an explicit control feature. Every derived column must carry a `feature_role`
(`competition` / `research` / `diagnostic`) as metadata, mirrored from `docs/schema_catalog.csv`'s
`allowed_for_scoring`/`allowed_for_bias` flags — the scoring engine (Stage 7) is only ever permitted
to read `competition`-tagged columns.

Step 3's raw ingredients and candidate gap values (`data/processed/<region>-step3-ingredients.
parquet`) are this module's primary input for the gap-derived features below. Steps 4-5 populate
this file; Step 6 (not yet done) assembles everything into the final schema-validated table and
calls `assert_competition_only` before anything reaches Stage 7.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# -------------------------------------------------------------------------------------------
# Step 4 — strata join features (SVI, tribal, rurality, heat, wildfire, drought, CVI, population)
# -------------------------------------------------------------------------------------------
#
# A curated, flagship subset of `national-strata-tract-table`'s real 232 columns — not the full
# table (Stage 9 can always pull more directly from it). Every name below, and its `feature_role`,
# is verified against `docs/schema_catalog.csv`'s real, confirmed rows (source-driven-development)
# rather than invented: a `coverage_flag` column says whether the row is trustworthy, not a
# vulnerability signal itself, so it gets `"diagnostic"`; every other selected column gets
# `"research"` — never `"competition"`, per Step 0's boundary (nothing from strata/ may influence
# the scored coverage-gap number, whatever its role).
STRATA_FEATURE_COLUMNS: dict[str, str] = {
    # SVI (national-svi-tract-table)
    "svi_overall": "research",
    "svi_socioeconomic": "research",
    "svi_household": "research",
    "svi_minority": "research",
    "svi_housing_transport": "research",
    "svi_covered": "diagnostic",
    # Tribal status/sub-type (national-tribal-tract-table)
    "tribal_any": "research",
    "tribal_legal": "research",
    "tribal_statistical": "research",
    "tribal_pct": "research",
    "tribal_legal_pct": "research",
    "tribal_stat_pct": "research",
    "aiannh_kind": "research",
    "aiannh_name": "research",
    # Rurality: RUCA / RUCC / NCHS
    "ruca_primary": "research",
    "ruca_primary_desc": "research",
    "ruca_pop_density": "research",
    "ruca_covered": "diagnostic",
    "rucc_2023": "research",
    "rucc_desc": "research",
    "rucc_metro": "research",
    "rucc_covered": "diagnostic",
    "nchs_2013": "research",
    "nchs_2013_label": "research",
    "nchs_covered": "diagnostic",
    # Heat
    "epht_heat_days_annual": "research",
    "epht_heat_days_summer": "research",
    "epht_covered": "diagnostic",
    "gehe_wbgt30_days_mean": "research",
    "uhe_himax461_days_per_yr": "research",
    "uhe_covered": "diagnostic",
    "hwd_heatindex_mean": "research",
    # Wildfire
    "usfs_WHP_mean": "research",
    "usfs_covered": "diagnostic",
    "mtbs_wildfire_burned_pct_land": "research",
    "mtbs_wildfire_ever": "research",
    "mtbs_covered": "diagnostic",
    "nifc_wildfire_ever": "research",
    "fod_ignition_density": "research",
    "carbonplan_bp_2011_mean": "research",
    # Drought
    "pmdi_mean": "research",
    "pmdi_covered": "diagnostic",
    "spi12_mean": "research",
    "spi_covered": "diagnostic",
    "usdm_summer_pct_d2plus": "research",
    "usdm_winter_pct_d2plus": "research",
    "usdm_covered": "diagnostic",
    # CVI pillars
    "cvi_overall": "research",
    "cvi_baseline": "research",
    "cvi_baseline_socioeconomic": "research",
    "cvi_baseline_health": "research",
    "cvi_baseline_environment": "research",
    "cvi_baseline_infrastructure": "research",
    "cvi_climate": "research",
    "cvi_climate_extreme_events": "research",
    "cvi_climate_health": "research",
    "cvi_climate_socioeconomic": "research",
    "cvi_covered": "diagnostic",
    # Population / rurality signal (Stage 5 EDA Finding 2/6 — a ready-made rurality signal)
    "pop_total": "research",
    "pop_urban": "research",
    "pop_rural": "research",
    "pct_urban": "research",
    "ur_class": "research",
}


def join_strata_features(national_strata: pd.DataFrame, tract_geoids: pd.Index) -> pd.DataFrame:
    """Step 4: attaches every `STRATA_FEATURE_COLUMNS` column to `tract_geoids`, from
    `national_strata` (`load_national_strata_attribute_table(STRATA_NATIONAL_JOINED_TABLE)` — the
    real, already-joined 232-column `national-strata-tract-table`, 85,396 tracts; pass its GEOID
    column as the index or a plain column, either works via the merge below).

    This is a single GEOID merge against the pre-joined table, not 25 separate per-domain joins —
    every curated column was confirmed present in it directly against `docs/schema_catalog.csv`
    (source-driven-development), so no fallback is exercised today. If a future addition to
    `STRATA_FEATURE_COLUMNS` needs a column NOT in this table (e.g. `AWATER`, which lives only on
    the separate, geometry-bearing `national-census-tracts`), apply
    `docs/data_manifest.md` Section 4.26's branch-detection pattern by hand at that point — check
    the real columns before assuming a source, exactly as that section did — rather than building
    unused fallback machinery here for a case that does not exist yet.
    """
    missing = [c for c in STRATA_FEATURE_COLUMNS if c not in national_strata.columns]
    if missing:
        raise KeyError(
            f"join_strata_features: {missing!r} not found in national_strata. Every column in "
            "STRATA_FEATURE_COLUMNS was confirmed present in national-strata-tract-table against "
            "docs/schema_catalog.csv — a real miss here means either a stale column list or a "
            "genuinely new column needing Section 4.26's branch-detection pattern applied by hand."
        )
    cols = ["GEOID"] + list(STRATA_FEATURE_COLUMNS)
    joined = (
        pd.DataFrame({"GEOID": tract_geoids})
        .merge(national_strata[cols], on="GEOID", how="left")
        .set_index("GEOID")
    )
    return joined


# -------------------------------------------------------------------------------------------
# Step 5 — derived interaction features for Bias Discovery
# -------------------------------------------------------------------------------------------


def dispatch_blind_reachability(transport_gap: pd.Series, poi_gap_dispatch: pd.Series) -> pd.DataFrame:
    """Four candidate "dispatch-blind reachability" definitions, combining the transport gap with
    the dispatch-relevant facility gap (`poi_gap_dispatch` — callers pass the fire/EMS combination,
    e.g. `poi_gap[["poi_gap_fire", "poi_gap_ems"]].mean(axis=1, skipna=True)`; NOT schools, since
    "dispatch" here means emergency response reaching a tract, not education access). All four are
    computed and kept; Stage 9 selects among them by interpretability/stability/sensitivity, not
    here.

    Both inputs are assumed already capped-ratio values in [0, 1] (Step 3's guarantee). Every
    candidate below is verified, by the doubt-driven-development self-check in this module's
    `__main__` block, to also land in [0, 1] given that precondition — this docstring is not a
    substitute for that check, it just states the claim being checked."""
    threshold_and = ((transport_gap > 0.5) & (poi_gap_dispatch > 0.5)).astype(float)
    # Euclidean distance from (0, 0) in [0,1] x [0,1] space ranges over [0, sqrt(2)], NOT [0, 1] —
    # dividing by sqrt(2) is what makes this NORMALIZED; omitting the division (a real mistake this
    # function's doubt-driven-development check exists to catch) would let the result reach ~1.414.
    normalized_euclidean = np.sqrt(transport_gap**2 + poi_gap_dispatch**2) / np.sqrt(2)
    product = transport_gap * poi_gap_dispatch
    # Continuous DARI: 1 - P(neither component fails) = 1 - (1-transport_gap)(1-poi_gap) — "at
    # least one of the two gaps is bad enough to block dispatch," a genuinely different combination
    # from the raw product ("both are bad simultaneously") and from normalized-Euclidean (a
    # geometric distance, not a probability).
    dari = 1 - (1 - transport_gap) * (1 - poi_gap_dispatch)
    return pd.DataFrame(
        {
            "dispatch_blind_threshold_and": threshold_and,
            "dispatch_blind_normalized_euclidean": normalized_euclidean,
            "dispatch_blind_product": product,
            "dispatch_blind_dari": dari,
        }
    )


def confidence_features(confidence_by_tract: pd.Series) -> pd.DataFrame:
    """`confidence_by_tract`: one list of raw per-record confidence values per tract (Overture's
    flat `confidence` column on `overture-pois`, or the per-source `confidence` inside the
    `sources` struct on `overture-buildings`/`overture-roads` — flattened to a plain list by the
    caller's spatial-join aggregation before this function ever sees it; this function is the pure
    reduction step, kept separate from whatever DuckDB query gathers the raw per-tract lists).

    Two columns, DELIBERATELY kept separate (the blueprint's own explicit warning against
    conflating them):
    - `confidence_reporting_rate`: share of records with a non-missing confidence value.
    - `mean_reported_confidence`: mean confidence, computed ONLY among records that report one.

    The doubt-driven-development question this function exists to answer: does
    `mean_reported_confidence` accidentally treat a missing value as 0 instead of excluding it
    (which would silently pull every tract's mean toward 0 in proportion to how much of its data
    just doesn't report confidence, conflating "low confidence" with "no confidence reported")? No
    — missing values are filtered out of BOTH the numerator and the denominator of the mean before
    averaging. See this module's `__main__` self-check for a hand-verified fixture."""

    def _reported(values) -> list[float]:
        return [v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]

    def _reporting_rate(values) -> float:
        if len(values) == 0:
            return np.nan
        return len(_reported(values)) / len(values)

    def _mean_reported(values) -> float:
        reported = _reported(values)
        return float(np.mean(reported)) if reported else np.nan

    return pd.DataFrame(
        {
            "confidence_reporting_rate": confidence_by_tract.apply(_reporting_rate),
            "mean_reported_confidence": confidence_by_tract.apply(_mean_reported),
        }
    )


def source_provenance_vector(sources_by_tract: pd.Series) -> pd.DataFrame:
    """`sources_by_tract`: one list of `sources[].dataset` string values per tract, flattened
    across every record assigned to it by the caller's spatial join — the real dataset value set
    and struct shape are already confirmed live in all four regions
    (`docs/data_manifest.md` Section 4.5), not re-inspected here."""

    def _row(datasets) -> pd.Series:
        empty = pd.Series(
            {
                "osm_share": np.nan,
                "microsoft_share": np.nan,
                "google_share": np.nan,
                "other_share": np.nan,
                "n_sources": 0,
                "dominant_source": None,
                "source_entropy": np.nan,
            }
        )
        if not datasets:
            return empty
        counts = pd.Series(datasets).value_counts()
        total = int(counts.sum())
        osm = counts.get("OpenStreetMap", 0) / total
        msft = sum(c for name, c in counts.items() if "Microsoft" in name) / total
        google = sum(c for name, c in counts.items() if "Google" in name) / total
        other = max(0.0, 1 - osm - msft - google)
        probs = (counts / total).to_numpy()
        entropy = float(-(probs * np.log(probs)).sum())
        return pd.Series(
            {
                "osm_share": osm,
                "microsoft_share": msft,
                "google_share": google,
                "other_share": other,
                "n_sources": total,
                "dominant_source": counts.idxmax(),
                "source_entropy": entropy,
            }
        )

    return sources_by_tract.apply(_row)


def component_dominance_and_definedness(
    gap_values: pd.DataFrame, defined_flags: pd.DataFrame
) -> pd.DataFrame:
    """`dominant_component`: `argmax(transport_gap, building_gap, poi_gap, ...)` per tract, over
    whichever gap columns `gap_values` carries — NaN-safe: a tract with zero non-null gap values
    gets `dominant_component` = null (NaN when read back from the assembled DataFrame — pandas
    coerces the object column's None on assembly), never a spurious argmax over all-NaN (which
    `DataFrame.idxmax(axis=1)` raises `ValueError` on directly, even with `skipna=True` — a real
    pandas quirk this function works around by only running idxmax on rows with ≥1 defined value).
    `n_components_defined`:
    count of True flags across `defined_flags`' columns. `undefined_components`: comma-joined names
    of the False ones (column name with its `_defined` suffix stripped) — the direct raw material
    for the Measurement Eligibility Bias Bias Discovery candidate."""
    has_any = gap_values.notna().any(axis=1)
    # DataFrame.idxmax(axis=1) raises ValueError on an all-NaN row even with skipna=True (a real
    # pandas quirk, unlike Series.idxmax which returns NaN) — so idxmax only runs on the subset of
    # rows that have at least one non-null value, and all-NaN rows get None via reindex instead.
    dominant = pd.Series(None, index=gap_values.index, dtype=object)
    if has_any.any():
        dominant.loc[has_any] = gap_values.loc[has_any].idxmax(axis=1, skipna=True)
    n_defined = defined_flags.sum(axis=1)
    undefined_names = defined_flags.apply(
        lambda row: ",".join(c[: -len("_defined")] for c, v in row.items() if not v), axis=1
    )
    return pd.DataFrame(
        {
            "dominant_component": dominant,
            "n_components_defined": n_defined,
            "undefined_components": undefined_names,
        }
    )


def population_weighted_gap_stats(gap: pd.Series, population: pd.Series) -> dict:
    """Population-weighted mean of a gap column, weighting by `pop_total` so a coverage gap in a
    dense tract counts more than the same gap in a near-empty one — a region-level diagnostic
    STATISTIC (not a per-tract feature column, unlike everything else in this module; kept as its
    own small function rather than forced into the tidy per-tract table it doesn't belong in).

    NaN-safe: tracts with an undefined gap or missing/zero population are excluded from both the
    numerator and the denominator, never treated as zero-weight (which would silently count them as
    a 0 contribution) or left to reach a zero-population divide."""
    valid = gap.notna() & population.notna() & (population > 0)
    if not valid.any():
        return {"pop_weighted_mean": np.nan, "n_tracts_used": 0}
    return {
        "pop_weighted_mean": float(np.average(gap[valid], weights=population[valid])),
        "n_tracts_used": int(valid.sum()),
    }


def distance_to_tract_boundary_m(points_ea, tracts_ea) -> pd.Series:
    """Distance from each point to its own tract's boundary, in METERS, given geometry ALREADY
    reprojected to `EQUAL_AREA_CRS` by the caller (via `src.geometry.to_equal_area`) — never raw
    CRS84 distance, the same discipline `docs/data_manifest.md` Section 4.26 established for
    centroids (a degree of longitude is not a fixed distance). `points_ea`/`tracts_ea` are aligned
    GeoSeries (same index, one tract-boundary geometry per point) — the caller does the GEOID merge
    before calling this, since that join is caller-specific (a facility layer vs. a tract's own
    representative point use different point sources) and this function stays a pure distance
    primitive."""
    return points_ea.distance(tracts_ea.boundary)


def attach_region(df: pd.DataFrame, region: str) -> pd.DataFrame:
    """Carries `region` through as an explicit control feature — trivial, but every prior Stage 5
    finding that showed `transport_gap` is not cross-region comparable (Section 4.6/4.22) depends
    on this column surviving every later join/groupby undropped, so it gets its own named function
    rather than an easy-to-silently-drop inline `.assign()` scattered at each call site."""
    return df.assign(region=region)


# -------------------------------------------------------------------------------------------
# Step 7 — the competition-only enforcement gate
# -------------------------------------------------------------------------------------------


def assert_competition_only(columns_used: set[str]) -> None:
    """Security-and-hardening framing, not a formality: an ALLOWLIST check, FAIL-CLOSED, least-
    privilege by default.

    `src.schemas.COMPETITION_ALLOWED_COLUMNS` is the single frozen source of truth for which
    column names a caller (Stage 7's `build_submission.py`, once it wires this in) may read with
    `feature_role=competition`. This function does not itself decide which columns are allowed —
    it only enforces the frozen set — so a call site can never widen its own permissions by
    passing a bigger set; the set lives in one place, reviewed as a real code change, not as a
    parameter any caller controls.

    ALLOWLIST, not a blocklist: `columns_used` is checked against what IS permitted, not against a
    list of what's forbidden — a brand-new strata column added to `STRATA_FEATURE_COLUMNS` next
    week is rejected by default (safe) rather than silently passing because nobody thought to
    blocklist it yet (unsafe). FAIL-CLOSED: `COMPETITION_ALLOWED_COLUMNS` is empty today (Step 0
    Ambiguity 2 — the winning gap-value variant isn't frozen until Stage 7's calibration), so this
    currently raises on ANY non-empty `columns_used`, by design — a caller that trips this before
    Stage 7 widens the set has found a real bug (something is reading a not-yet-frozen or
    strata-sourced column into the score), not a false alarm to silence.

    Raises `ValueError` naming every disallowed column, rather than returning a bool a caller could
    forget to check — a permission gate that can be silently ignored is not a permission gate."""
    # Imported here, not at module level: src.schemas imports STRATA_FEATURE_COLUMNS from this
    # module (Step 6), so a top-level `from src.schemas import ...` here would be a circular
    # import. This function is the only thing in this module that needs schemas.py.
    from src.schemas import COMPETITION_ALLOWED_COLUMNS

    disallowed = set(columns_used) - COMPETITION_ALLOWED_COLUMNS
    if disallowed:
        raise ValueError(
            f"assert_competition_only: {sorted(disallowed)!r} not in COMPETITION_ALLOWED_COLUMNS "
            f"(src/schemas.py) — these columns are not permitted to influence the scored "
            "coverage-gap number. If this is a genuine, reviewed addition to the competition-"
            "scored column set (e.g. Stage 7 freezing a winning gap-value variant), widen "
            "COMPETITION_ALLOWED_COLUMNS itself; do not work around this check at the call site."
        )


if __name__ == "__main__":
    # ---------------------------------------------------------------------------------------
    # Doubt-driven-development self-checks, hand-verified — not a substitute for Stage 7's
    # golden-case suite, just proof each formula does what its docstring claims in isolation.
    # ---------------------------------------------------------------------------------------

    # Check 1 — mean_reported_confidence's denominator logic.
    # Tract A: [0.9, 0.8, None] -> reporting_rate = 2/3; mean_reported = (0.9+0.8)/2 = 0.85
    #          (NOT (0.9+0.8+0)/3 = 0.5667 — that wrong value is exactly what a "missing=0" bug
    #          would produce, so asserting 0.85 specifically catches that bug.)
    # Tract B: [None, None]     -> reporting_rate = 0.0; mean_reported = NaN (no reported values
    #          at all — must not be silently coerced to 0.0, which would look like "perfect
    #          coverage, zero confidence" instead of "no confidence data").
    # Tract C: [0.5]            -> reporting_rate = 1.0; mean_reported = 0.5
    fixture = pd.Series([[0.9, 0.8, None], [None, None], [0.5]], index=["A", "B", "C"])
    result = confidence_features(fixture)
    assert result.loc["A", "confidence_reporting_rate"] == 2 / 3
    assert abs(result.loc["A", "mean_reported_confidence"] - 0.85) < 1e-9, result.loc["A"]
    assert result.loc["B", "confidence_reporting_rate"] == 0.0
    assert np.isnan(result.loc["B", "mean_reported_confidence"]), (
        "tract B has zero reported values — mean_reported_confidence must be NaN, not 0.0"
    )
    assert result.loc["C", "confidence_reporting_rate"] == 1.0
    assert abs(result.loc["C", "mean_reported_confidence"] - 0.5) < 1e-9
    print("confidence_features: PASS (denominator excludes missing values, confirmed by hand)")

    # Check 2 — normalized-Euclidean actually normalizes to [0, 1] given both inputs already [0,1].
    # (1.0, 1.0) -> sqrt(1^2+1^2)/sqrt(2) = sqrt(2)/sqrt(2) = 1.0  (the worst case must hit exactly
    #               1.0, not ~1.414 — the un-normalized value a missing /sqrt(2) would produce)
    # (0.6, 0.8) -> sqrt(0.36+0.64)/sqrt(2) = sqrt(1.0)/sqrt(2) = 1/sqrt(2) = 0.70710678...
    # (0.0, 0.0) -> 0.0
    transport = pd.Series([1.0, 0.6, 0.0])
    poi = pd.Series([1.0, 0.8, 0.0])
    reach = dispatch_blind_reachability(transport, poi)
    ne = reach["dispatch_blind_normalized_euclidean"]
    assert abs(ne.iloc[0] - 1.0) < 1e-9, f"worst case must be exactly 1.0, got {ne.iloc[0]}"
    assert abs(ne.iloc[1] - (1 / np.sqrt(2))) < 1e-9, ne.iloc[1]
    assert abs(ne.iloc[2] - 0.0) < 1e-9
    assert ne.between(0, 1).all(), f"normalized_euclidean left [0,1]: {ne.tolist()}"
    # Sanity on the other three candidates over the same fixture, same worst/best-case bounds.
    assert reach["dispatch_blind_product"].between(0, 1).all()
    assert reach["dispatch_blind_dari"].between(0, 1).all()
    assert reach["dispatch_blind_threshold_and"].isin([0.0, 1.0]).all()
    print("dispatch_blind_reachability: PASS (normalized-Euclidean confirmed in [0,1] by hand)")

    # Check 3 — component_dominance_and_definedness on a small hand-built fixture.
    gaps = pd.DataFrame({"transport_gap": [0.8, np.nan], "building_gap": [0.3, np.nan], "poi_gap": [0.5, np.nan]})
    flags = pd.DataFrame(
        {"transport_gap_defined": [True, False], "building_gap_defined": [True, False], "poi_gap_defined": [True, False]}
    )
    dom = component_dominance_and_definedness(gaps, flags)
    assert dom.loc[0, "dominant_component"] == "transport_gap"
    assert dom.loc[0, "n_components_defined"] == 3
    assert dom.loc[0, "undefined_components"] == ""
    # pandas coerces the object column's None to NaN when assembled into the final DataFrame
    # (a real, confirmed pandas quirk, not a bug in this function) — pd.isna is the correct check.
    assert pd.isna(dom.loc[1, "dominant_component"])
    assert dom.loc[1, "n_components_defined"] == 0
    assert dom.loc[1, "undefined_components"] == "transport_gap,building_gap,poi_gap"
    print("component_dominance_and_definedness: PASS")

    # Check 4 — Step 7's assert_competition_only, TDD fixture: a research-tagged column
    # ("svi_overall" — never feature_role=competition, per STRATA_FEATURE_COLUMNS above) must be
    # REJECTED. COMPETITION_ALLOWED_COLUMNS is empty today (Step 0 Ambiguity 2 — nothing is frozen
    # into the score yet), so this also proves the fail-closed default actually raises rather than
    # silently allowing everything through.
    try:
        assert_competition_only({"svi_overall"})
        raise AssertionError("assert_competition_only should have raised on a research-tagged column")
    except ValueError as e:
        assert "svi_overall" in str(e)
        print("assert_competition_only: PASS (research-tagged column correctly rejected)")

    print("All Stage 6 Step 4/5 self-checks passed.")
