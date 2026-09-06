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

Intentionally empty — populated in Stage 6.
"""
