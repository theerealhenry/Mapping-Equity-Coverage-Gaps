"""
Stage 3 Step 6 — candidate_hypotheses tagging for every column of `national-strata-tract-table`.

This is the fourth and final per-column governance field the data dictionary needs (`role` and the
two `allowed_for_*` flags came from Step 5): for every column that IS allowed in bias-discovery
analysis (`allowed_for_bias=True`), which of this project's own pre-registered Bias Discovery
candidate hypotheses — the exact ten-candidate pool defined in `PROJECT_BLUEPRINT.md`'s Stage 9
table — does that column actually feed? A column with no candidate tag is not a mistake; it means
this project's current hypothesis pool has no use for it yet (see the two zero-match candidates
documented below), which is itself useful, checkable information for Stage 8's hypothesis funnel.

**This is a governance/traceability field, not a promise that a tagged column will appear in the
eventual writeup.** Stage 8 mines and funnels; Stage 9 confirms two or three of these ten candidates
rigorously and drops the rest (Gate D: "does not introduce new candidates" at that stage). Tagging a
column here only means "this column is part of the raw material this candidate would draw on if it
survives the funnel" — it is deliberately generous (a column can and often does feed several
candidates) rather than trying to pre-guess which candidate wins.

**Why this needs no live bucket access.** Every fact this step uses is already committed, real data
from earlier steps: `docs/column_domain_map.csv` (Step 2's domain assignment), `docs/
column_classification.csv` (Step 5's role/allowed_for_bias classification), and the fixed, already-
written candidate-hypothesis pool from `PROJECT_BLUEPRINT.md` itself (Stage 9 — not re-derived here,
only encoded and applied). Nothing about which columns feed which hypothesis requires re-touching
the live data a second time.

**The tagging rule, in full, matched line-for-line against PROJECT_BLUEPRINT.md's Stage 9 table:**

- `allowed_for_bias=False` (43 columns: identifiers, all vintage/edition/methodology metadata, and
  the three zero-variance flags) → no candidate tags, full stop, regardless of role or domain. A
  column that carries no discriminative signal, or is a bare join key, cannot be raw material for
  any hypothesis about tract-level disparity. This mirrors Step 5's own `allowed_for_bias` override
  exactly, deliberately — a column that step already ruled out of bias analysis cannot un-rule
  itself back in here.

- `role=coverage_flag` (the `<source>_covered` flags) → **Measurement Eligibility Bias** only. This
  is not a new judgment call — it is exactly the reasoning Step 5 already wrote into this role's own
  `bias_reason` ("central to Measurement Eligibility Bias analysis"). Kept single-tagged rather than
  broadened, because a flag's only real analytical content is "is this source present for this
  tract," which is precisely MEB's question, extended from the challenge's own gap-component
  definedness rule to this project's own strata-source definedness (see the note below on this
  extension).

- `role=derived_ever_flag` (the four wildfire-history flags) → **Measurement Eligibility Bias**
  (jointly with its own `_covered` flag, per Step 5's mandatory-pairing caveat) and **Component
  Dominance** (a tract's wildfire history is part of the "vulnerability" side of that candidate's
  crosstab).

- `role=geometry_measure` (ALAND/AWATER/INTPTLAT/INTPTLON) → **Tribal Sub-type + Edge Effect** (the
  blueprint names this candidate's "distance-to-boundary" geometry work directly, and centroid/area
  are exactly what that computation needs) and **Dispatch-Blind Reachability** (tract land/water
  area is a plausible isolation proxy for how hard a tract is to physically reach).

- `role=population` → **Population Exposure vs. Disparity** (the primary fit — this candidate is
  explicitly about weighting disparity statistics by real population), **Component Dominance**
  (population-weighted vulnerability crosstabs), and **Dispatch-Blind Reachability** (population
  density as a reachability covariate).

- `role=identity_metadata`:
    - `aiannh_geoid`/`aiannh_name` → **Tribal Sub-type + Edge Effect** (identifies which named AIANNH
      area a tract belongs to or overlaps, the raw material for a named-instance edge-effect story)
      and **Population Exposure vs. Disparity** (named-tract anchoring needs a real place name, not
      just a boolean).
    - `uhe_city_name`/`uhe_city_country` → **Source Provenance x Vulnerability** only, as the closest
      existing fit (these columns are themselves evidence that the NASA urban-heat-exposure source's
      composition/coverage varies by geography — exactly SPV's question, just for a different source
      than the one SPV was originally scoped around). This is NOT a promise that the already-
      documented Tijuana/cross-border finding (`docs/data_manifest.md` Section 4.14) IS the SPV
      finding that ships — it is flagged here only as the best-fit existing candidate for these two
      columns; whether this finding stands on its own merits as an eleventh candidate is a Stage 8
      funnel decision, explicitly out of scope for this step.

- `role=measurement` → tagged by the column's **domain** (Step 2), since every measurement column in
  a hazard/vulnerability/rurality domain is, at minimum, part of the generic "vulnerability/hazard
  covariate" raw material three candidates all draw on:
    - `svi`, `cvi`, `wildfire`, `heat`, `drought` measurement columns → **Measurement Eligibility
      Bias**, **Source Provenance x Vulnerability**, **Component Dominance** (the three candidates
      that all cross hazard/vulnerability measurements against a gap-related or provenance-related
      response).
    - `rurality` measurement columns → the same three, plus **Dispatch-Blind Reachability** (rural
      classification is a direct reachability covariate).
    - `tribal` measurement columns (`tribal_any`, `tribal_pct`, `tribal_legal`, `tribal_legal_pct`,
      `tribal_statistical`, `tribal_stat_pct`) → the same three, plus **Dispatch-Blind
      Reachability**, **Tribal Sub-type + Edge Effect**, and **Population Exposure vs. Disparity**
      (tribal status is this project's most cross-cutting single covariate — Eastern Oklahoma, one
      of only four study regions, is defined specifically around tribal statistical areas).
  Two column-specific additions on top of the domain default:
    - The six CVI **pillar** columns specifically (`cvi_baseline`, `cvi_climate`,
      `cvi_baseline_health`, `cvi_baseline_socioeconomic`, `cvi_baseline_infrastructure`,
      `cvi_baseline_environment`, `cvi_climate_health`, `cvi_climate_socioeconomic`,
      `cvi_climate_extreme_events` — nine, not six; see `CVI_PILLAR_COLUMNS`) also get **CVI Pillar
      Decomposition**. `cvi_overall` and `cvi_xwalk_coverage` do NOT get this tag — decomposing PAST
      the composite is exactly what this candidate is about, so the composite score itself and its
      crosswalk-match-rate metadata are not decomposition raw material.
    - The rurality **classification** columns specifically (`ruca_primary`, `ruca_primary_desc`,
      `ruca_secondary`, `rucc_2023`, `rucc_desc`, `rucc_metro`, `nchs_2013`, `nchs_2013_label` — see
      `RURALITY_DISAGREEMENT_COLUMNS`) also get **RUCA/RUCC/NCHS Disagreement**. `ruca_pop_density`
      does NOT get this tag — it is a rurality-domain covariate, not part of the three-system
      classification comparison itself.

- **Two of the ten candidates get zero column tags from this table, by design, and this is
  independently verified rather than just asserted:**
    - **Confidence Reporting-Rate vs. Reported-Confidence-Value** — checked directly against the
      real domain map for any column name suggesting a per-feature confidence/reliability score
      (`conf`, `confidence`, `reliab`, `quality`, `moe`, `margin`); the only match anywhere in the
      232 columns is `ghcn_anchor_unreliable`, a station-anchoring data-quality flag for the GHCN
      weather-station dataset, not a reported-confidence VALUE in the sense this candidate means.
      This candidate's actual subject — Overture's own per-feature confidence score on buildings,
      roads, and places — lives in `reference/`, not `strata/`, and is entirely outside this table's
      232 columns. Zero tags here is the correct, confirmed answer, not a gap.
    - **Colonias in South-Central TX** — this candidate explicitly needs an external colonias
      registry (the blueprint names it as "permitted for this prize only" precisely because it is
      not part of the provided data at all). No column in `national-strata-tract-table` can feed it;
      the closest thing (a Texas-scoping join key like `state_usps`) is already `allowed_for_
      bias=False` as a bare identifier. Zero tags here is correct and expected.
  Both are locked in by permanent regression tests rather than left as unstated assumptions.

- **Explicitly excluded from this step's vocabulary: the two DROPPED candidates** (Wildfire-Rebuilt
  Areas; Heat-Island x SVI). Neither is a valid tag value — attempting to encode either would
  contradict the blueprint's own documented drop decision. A wildfire or heat measurement column
  still legitimately feeds the three generic covariate candidates (MEB/SPV/Component Dominance)
  above; that is a different, broader claim than the narrow, specific, already-rejected "wildfire
  rebuild timing" or "heat-island restates the Climate-Justice Composite" claims, and this step is
  careful to keep the two apart rather than let the generic tags accidentally re-legitimize a
  dropped candidate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

DEFAULT_DOMAIN_MAP_PATH = Path("docs/column_domain_map.csv")
DEFAULT_CLASSIFICATION_PATH = Path("docs/column_classification.csv")
DEFAULT_OUTPUT_PATH = Path("docs/column_candidate_hypotheses.csv")

TAG_SEPARATOR = "; "

# --- The canonical ten-candidate pool, transcribed directly from PROJECT_BLUEPRINT.md's Stage 9
# table (not re-derived or re-worded here) -----------------------------------------------------

MEASUREMENT_ELIGIBILITY_BIAS = "Measurement Eligibility Bias"
DISPATCH_BLIND_REACHABILITY = "Dispatch-Blind Reachability"
SOURCE_PROVENANCE_X_VULNERABILITY = "Source Provenance x Vulnerability"
CONFIDENCE_REPORTING_RATE = "Confidence Reporting-Rate vs. Reported-Confidence-Value"
COMPONENT_DOMINANCE = "Component Dominance"
TRIBAL_SUBTYPE_EDGE_EFFECT = "Tribal Sub-type + Edge Effect"
POPULATION_EXPOSURE_DISPARITY = "Population Exposure vs. Disparity"
COLONIAS_SOUTH_CENTRAL_TX = "Colonias in South-Central TX"
CVI_PILLAR_DECOMPOSITION = "CVI Pillar Decomposition"
RUCA_RUCC_NCHS_DISAGREEMENT = "RUCA/RUCC/NCHS Disagreement"

ALL_CANDIDATES = {
    MEASUREMENT_ELIGIBILITY_BIAS: "A",
    DISPATCH_BLIND_REACHABILITY: "A",
    SOURCE_PROVENANCE_X_VULNERABILITY: "A",
    CONFIDENCE_REPORTING_RATE: "B",
    COMPONENT_DOMINANCE: "B",
    TRIBAL_SUBTYPE_EDGE_EFFECT: "B",
    POPULATION_EXPOSURE_DISPARITY: "B",
    COLONIAS_SOUTH_CENTRAL_TX: "C",
    CVI_PILLAR_DECOMPOSITION: "C",
    RUCA_RUCC_NCHS_DISAGREEMENT: "C",
}

# Documented for completeness and to guard against ever accidentally tagging a column with one of
# these — these two are explicitly DROPPED in PROJECT_BLUEPRINT.md's Stage 9 table and must never
# appear as a tag value.
DROPPED_CANDIDATES = {
    "Wildfire-Rebuilt Areas": "no time-series building data exists to distinguish rebuilt from always-looked-like-this",
    "Heat-Island x SVI": "too close to what the Climate-Justice Composite metric already computes",
}

# Candidates independently confirmed to have zero feeding columns in this table (see module
# docstring) — their subject matter lives in reference/ or an external registry, not strata/.
CANDIDATES_WITH_NO_STRATA_COLUMNS = {CONFIDENCE_REPORTING_RATE, COLONIAS_SOUTH_CENTRAL_TX}

# --- Column-specific overrides on top of the domain/role defaults -------------------------------

CVI_PILLAR_COLUMNS = {
    "cvi_baseline",
    "cvi_climate",
    "cvi_baseline_health",
    "cvi_baseline_socioeconomic",
    "cvi_baseline_infrastructure",
    "cvi_baseline_environment",
    "cvi_climate_health",
    "cvi_climate_socioeconomic",
    "cvi_climate_extreme_events",
}

RURALITY_DISAGREEMENT_COLUMNS = {
    "ruca_primary",
    "ruca_primary_desc",
    "ruca_secondary",
    "rucc_2023",
    "rucc_desc",
    "rucc_metro",
    "nchs_2013",
    "nchs_2013_label",
}

IDENTITY_METADATA_TAGS = {
    "aiannh_geoid": [TRIBAL_SUBTYPE_EDGE_EFFECT, POPULATION_EXPOSURE_DISPARITY],
    "aiannh_name": [TRIBAL_SUBTYPE_EDGE_EFFECT, POPULATION_EXPOSURE_DISPARITY],
    "uhe_city_name": [SOURCE_PROVENANCE_X_VULNERABILITY],
    "uhe_city_country": [SOURCE_PROVENANCE_X_VULNERABILITY],
}

# Generic vulnerability/hazard-covariate tag set every measurement-role domain gets by default.
_GENERIC_COVARIATE_TAGS = [
    MEASUREMENT_ELIGIBILITY_BIAS,
    SOURCE_PROVENANCE_X_VULNERABILITY,
    COMPONENT_DOMINANCE,
]

MEASUREMENT_DOMAIN_TAGS = {
    "svi": list(_GENERIC_COVARIATE_TAGS),
    "cvi": list(_GENERIC_COVARIATE_TAGS),
    "wildfire": list(_GENERIC_COVARIATE_TAGS),
    "heat": list(_GENERIC_COVARIATE_TAGS),
    "drought": list(_GENERIC_COVARIATE_TAGS),
    "rurality": _GENERIC_COVARIATE_TAGS + [DISPATCH_BLIND_REACHABILITY],
    "tribal": _GENERIC_COVARIATE_TAGS
    + [DISPATCH_BLIND_REACHABILITY, TRIBAL_SUBTYPE_EDGE_EFFECT, POPULATION_EXPOSURE_DISPARITY],
}


# --- Pure functions (fully testable with no network) --------------------------------------------


def tag_column(column_name: str, role: str, domain: str, allowed_for_bias: bool) -> tuple[list[str], str]:
    """Returns (candidate_tags, reason) for one column. `allowed_for_bias=False` always wins,
    regardless of role or domain — see module docstring."""
    if not allowed_for_bias:
        return [], "allowed_for_bias=False (Step 5) — not usable for any bias-discovery hypothesis, regardless of role or domain"

    if role == "identity_metadata":
        if column_name in IDENTITY_METADATA_TAGS:
            tags = IDENTITY_METADATA_TAGS[column_name]
            return tags, "identity-metadata column matched by an explicit, named per-column rule (see module docstring)"
        # A future identity_metadata column with no per-column rule yet: no tags rather than a
        # crash. This is a real gap to fill in (an untagged identity-metadata column is silently
        # invisible to the candidate pool), not a case that should ever raise — unlike the
        # identifier/vintage_metadata fallback below, which guards an invariant that should never
        # break at all.
        return [], "identity_metadata column with no per-column candidate rule yet defined — add one to IDENTITY_METADATA_TAGS"

    if role == "coverage_flag":
        return [MEASUREMENT_ELIGIBILITY_BIAS], "a <source>_covered flag — whether this strata source has data for a tract at all is exactly what Measurement Eligibility Bias asks"
    if role == "derived_ever_flag":
        return (
            [MEASUREMENT_ELIGIBILITY_BIAS, COMPONENT_DOMINANCE],
            "real per-tract hazard-history signal (paired with its own _covered flag) that feeds both the measurement-eligibility question and the component-dominance vulnerability crosstab",
        )
    if role == "geometry_measure":
        return (
            [TRIBAL_SUBTYPE_EDGE_EFFECT, DISPATCH_BLIND_REACHABILITY],
            "tract area/centroid — the raw material for distance-to-boundary edge-effect analysis and a plausible isolation proxy for reachability",
        )
    if role == "population":
        return (
            [POPULATION_EXPOSURE_DISPARITY, COMPONENT_DOMINANCE, DISPATCH_BLIND_REACHABILITY],
            "base population figures — directly needed for population-weighted disparity, weighted vulnerability crosstabs, and reachability covariates",
        )

    if role == "measurement":
        if domain not in MEASUREMENT_DOMAIN_TAGS:
            # A measurement-role, allowed_for_bias=True column in a domain this function doesn't
            # know about would otherwise silently get candidate_hypotheses="" — indistinguishable
            # from a deliberately untagged column, but actually just a missed domain. Every domain
            # that measurement-role columns currently fall into (svi/cvi/wildfire/heat/drought/
            # rurality/tribal) is covered; if a future data refresh in Step 2 ever introduces an
            # eighth, this must fail loudly here rather than silently under-tagging real columns.
            raise AssertionError(
                f"column {column_name!r} is role=measurement, allowed_for_bias=True, in domain "
                f"{domain!r}, but MEASUREMENT_DOMAIN_TAGS has no entry for that domain — add one "
                "rather than letting this column silently get no candidate tags"
            )
        tags = list(MEASUREMENT_DOMAIN_TAGS[domain])
        reason_parts = [f"{domain}-domain measurement — generic vulnerability/hazard covariate raw material"]
        if column_name in CVI_PILLAR_COLUMNS:
            tags.append(CVI_PILLAR_DECOMPOSITION)
            reason_parts.append("also a specific CVI pillar/sub-score column, feeding CVI Pillar Decomposition directly")
        if column_name in RURALITY_DISAGREEMENT_COLUMNS:
            tags.append(RUCA_RUCC_NCHS_DISAGREEMENT)
            reason_parts.append("also one of the three rurality classification systems being compared, feeding RUCA/RUCC/NCHS Disagreement directly")
        return tags, "; ".join(reason_parts)

    # identifier, vintage_metadata: should be unreachable here since both are always
    # allowed_for_bias=False (see Step 5) and are caught by the guard above — kept as an explicit,
    # loud fallback rather than a silent pass-through, in case that invariant is ever broken.
    raise AssertionError(
        f"column {column_name!r} has role={role!r}, allowed_for_bias=True, but no tagging rule "
        "handles this role — Step 5's invariant that identifier/vintage_metadata are always "
        "allowed_for_bias=False must have changed; update this function's rules accordingly"
    )


def parse_tags(candidate_hypotheses_cell) -> list[str]:
    """Splits a `candidate_hypotheses` CSV cell back into its exact candidate names. Used instead of
    substring search (e.g. `series.str.contains(candidate)`) everywhere a caller needs to know which
    columns feed a given candidate: a substring search would silently over-count if any candidate
    name were ever a substring of another (there is a permanent regression test guarding that this
    is not currently true, but the exact-match split here means it could never matter even if it
    became true in a future edit).

    Deliberately tolerant of a real pandas gotcha this project has hit before in other CSVs: a blank
    `candidate_hypotheses` cell (the 43 allowed_for_bias=False columns) round-trips through
    `to_csv`/`read_csv` as an empty string only if the reader passes `keep_default_na=False` —
    plain `pd.read_csv` (the default any future downstream script, e.g. Step 8's data dictionary
    build, is likely to reach for first) reads it back as float `NaN` instead. Rather than relying
    on every future caller of this CSV to remember that flag, this function accepts either shape:
    `NaN` (via `pd.isna`), `None`, or an empty string all mean "no tags."""
    if candidate_hypotheses_cell is None or (isinstance(candidate_hypotheses_cell, float) and pd.isna(candidate_hypotheses_cell)):
        return []
    if not candidate_hypotheses_cell:
        return []
    return candidate_hypotheses_cell.split(TAG_SEPARATOR)


def columns_feeding(tagging: pd.DataFrame, candidate: str) -> int:
    """Count of columns whose candidate_hypotheses set contains exactly `candidate` (exact tag
    match via parse_tags, not substring search)."""
    return int(tagging["candidate_hypotheses"].apply(lambda cell: candidate in parse_tags(cell)).sum())


def build_tagging(domain_map: pd.DataFrame, classification: pd.DataFrame) -> pd.DataFrame:
    """One row per column: its candidate_hypotheses (semicolon-joined free text, per PROJECT_
    BLUEPRINT.md's data-dictionary field spec) and a reason. Assumes every domain_map column has a
    matching classification row — the caller (main()) is responsible for checking that."""
    role_by_column = dict(zip(classification["column_name"], classification["role"]))
    allowed_for_bias_by_column = dict(zip(classification["column_name"], classification["allowed_for_bias"]))

    records = []
    for _, row in domain_map.iterrows():
        column = row["column_name"]
        role = role_by_column[column]
        allowed_for_bias = bool(allowed_for_bias_by_column[column])
        tags, reason = tag_column(column, role, row["domain"], allowed_for_bias)
        records.append(
            {
                "column_name": column,
                "source_table": row["source_table"],
                "domain": row["domain"],
                "role": role,
                "allowed_for_bias": allowed_for_bias,
                "candidate_hypotheses": TAG_SEPARATOR.join(tags),
                "candidate_hypotheses_reason": reason,
            }
        )
    return pd.DataFrame.from_records(records)


# --- Real-path orchestration (no network needed — every input is already committed) --------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain-map", type=Path, default=DEFAULT_DOMAIN_MAP_PATH)
    parser.add_argument("--classification", type=Path, default=DEFAULT_CLASSIFICATION_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    try:
        domain_map = pd.read_csv(args.domain_map)
    except FileNotFoundError:
        print(f"ERROR: {args.domain_map} not found. Run scripts/map_column_domains.py first (Stage 3 Step 2).", file=sys.stderr)
        return 2

    try:
        classification = pd.read_csv(args.classification)
    except FileNotFoundError:
        print(
            f"ERROR: {args.classification} not found. Run scripts/classify_columns.py first "
            "(Stage 3 Step 5) — this step needs its role/allowed_for_bias columns.",
            file=sys.stderr,
        )
        return 2

    missing_columns = set(domain_map["column_name"]) - set(classification["column_name"])
    if missing_columns:
        print(
            f"ERROR: {len(missing_columns)} column(s) in {args.domain_map} have no row in "
            f"{args.classification}: {sorted(missing_columns)}. Re-run Step 5 before this step.",
            file=sys.stderr,
        )
        return 2

    tagging = build_tagging(domain_map, classification)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tagging.to_csv(args.output, index=False)
    print(f"Wrote {len(tagging)} column tags to {args.output}\n")

    n_tagged = int((tagging["candidate_hypotheses"] != "").sum())
    print(f"Columns with at least one candidate tag: {n_tagged} of {len(tagging)}")
    print(f"Columns with no tag (allowed_for_bias=False): {len(tagging) - n_tagged}")

    print("\nColumns feeding each candidate:")
    for candidate in ALL_CANDIDATES:
        print(f"  {columns_feeding(tagging, candidate):>4}  {candidate}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
