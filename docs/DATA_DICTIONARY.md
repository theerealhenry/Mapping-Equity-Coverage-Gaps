# Data dictionary — national-strata-tract-table

Stage 3 Step 8 of the data-audit plan (see `docs/data_manifest.md` Section 4). Every field below is drawn from an already-committed, independently-run Stage 3 step, not re-derived here: `dtype`/`national_position` from Step 1, `domain`/`source_table` from Step 2, the numeric profile columns from Step 3 (national scope), `role`/`allowed_for_scoring`/`allowed_for_bias` from Step 5, `candidate_hypotheses` from Step 6, `present_in_regions`/`missing_from_regions` from Step 7, and `vintage_status`/`vintage_note` from Step 4's external research (`docs/data_vintage_confirmation.md`), transcribed once per source table since vintage is a property of the underlying dataset, not of any individual column.

**allowed_for_scoring is False for every single row in this dictionary, including the region-only addition below, without exception** — this table lives entirely under `strata/`, never `reference/`, and no column here may influence the submitted coverage-gap number regardless of role or domain (Step 5).

## Columns absent from every region's own joined table

Confirmed live (Step 7): these columns exist in the national schema but are absent from all four regions' `<region>-strata-tract-table`. See `docs/data_manifest.md` Section 4.17 for the full triage of which of these are harmless (already `allowed_for_bias=False`) versus materially impactful.

- `state_usps` (role=identifier, allowed_for_bias=False)
- `state_name` (role=identifier, allowed_for_bias=False)
- `AWATER` (role=geometry_measure, allowed_for_bias=True)
- `INTPTLAT` (role=geometry_measure, allowed_for_bias=True)
- `INTPTLON` (role=geometry_measure, allowed_for_bias=True)
- `tract_vintage` (role=vintage_metadata, allowed_for_bias=False)

## Region-only addition

Found only in Step 7's live region-schema read — present in all four regions' own joined tables, absent from the national schema, so it was never seen by Steps 2/5/6. Classified directly in this step; see the row below and `scripts/build_data_dictionary.py`'s module docstring for the full reasoning.

- `frac_inside_aoi`: role=geometry_measure, allowed_for_bias=False, candidate_hypotheses=''
  - constant across all 9,386 tracts profiled live (n_distinct=1, value=1.0) — carries no discriminative signal for any bias analysis, regardless of role. The same hard, data-driven override Step 5 already established (scripts/classify_columns.py's compute_allowed_for_bias) for every other constant column in this project fires here too.

## Columns by domain

### cvi (13 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `cvi_covered` | `national-cvi-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed_with_clarification |
| `cvi_xwalk_coverage` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed_with_clarification |
| `cvi_overall` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.5% | confirmed_with_clarification |
| `cvi_baseline` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_climate` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_baseline_health` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_baseline_socioeconomic` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_baseline_infrastructure` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_baseline_environment` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_climate_health` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_climate_socioeconomic` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_climate_extreme_events` | `national-cvi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; CVI Pillar Decomposition | 1.5% | confirmed_with_clarification |
| `cvi_source_vintage` | `national-cvi-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |

### drought (28 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `usdm_covered` | `national-usdm-drought-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `usdm_summer_dsci` | `national-usdm-drought-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `usdm_summer_pct_d0plus` | `national-usdm-drought-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `usdm_summer_pct_d2plus` | `national-usdm-drought-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `usdm_winter_dsci` | `national-usdm-drought-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `usdm_winter_pct_d0plus` | `national-usdm-drought-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `usdm_winter_pct_d2plus` | `national-usdm-drought-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `usdm_year_min` | `national-usdm-drought-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `usdm_year_max` | `national-usdm-drought-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `pmdi_covered` | `national-drought-gov-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | unresolved |
| `pmdi_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.1% | unresolved |
| `pmdi_summer_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.1% | unresolved |
| `pmdi_winter_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.1% | unresolved |
| `pmdi_pct_months_severe` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.1% | unresolved |
| `pmdi_recent_percentile` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.1% | unresolved |
| `pmdi_mean_1895_2025` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.1% | unresolved |
| `spi_covered` | `national-drought-gov-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | unresolved |
| `spi_calibration` | `national-drought-gov-tract-table` | double | vintage_metadata | False | False |  | 100.0% | unresolved |
| `spi03_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `spi03_summer_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `spi03_winter_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `spi03_pct_months_d2` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `spi12_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `spi12_summer_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `spi12_winter_mean` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `spi12_pct_months_d2` | `national-drought-gov-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.5% | unresolved |
| `drought_gov_window_start` | `national-drought-gov-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | unresolved |
| `drought_gov_window_end` | `national-drought-gov-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | unresolved |

### geography (10 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `GEOID` | `national-census-tract-table` | string | identifier | False | False |  | 0.0% | confirmed |
| `STATEFP` | `national-census-tract-table` | string | identifier | False | False |  | 0.0% | confirmed |
| `COUNTYFP` | `national-census-tract-table` | string | identifier | False | False |  | 0.0% | confirmed |
| `state_usps` | `national-census-tract-table` | string | identifier | False | False |  | 0.0% | confirmed |
| `state_name` | `national-census-tract-table` | string | identifier | False | False |  | 0.0% | confirmed |
| `ALAND` | `national-census-tract-table` | int64 | geometry_measure | False | True | Tribal Sub-type + Edge Effect; Dispatch-Blind Reachability | 0.0% | confirmed |
| `AWATER` | `national-census-tract-table` | int64 | geometry_measure | False | True | Tribal Sub-type + Edge Effect; Dispatch-Blind Reachability | 0.0% | confirmed |
| `INTPTLAT` | `national-census-tract-table` | string | geometry_measure | False | True | Tribal Sub-type + Edge Effect; Dispatch-Blind Reachability | 0.0% | confirmed |
| `INTPTLON` | `national-census-tract-table` | string | geometry_measure | False | True | Tribal Sub-type + Edge Effect; Dispatch-Blind Reachability | 0.0% | confirmed |
| `tract_vintage` | `national-census-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |

### heat (58 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `epht_covered` | `national-epht-heat-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed_with_clarification |
| `epht_heat_days_summer` | `national-epht-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.3% | confirmed_with_clarification |
| `epht_heat_days_annual` | `national-epht-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.3% | confirmed_with_clarification |
| `epht_heat_events_summer` | `national-epht-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.3% | confirmed_with_clarification |
| `epht_threshold` | `national-epht-heat-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `epht_metric` | `national-epht-heat-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `epht_year_min` | `national-epht-heat-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `epht_year_max` | `national-epht-heat-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `ghcn_covered` | `national-noaa-ghcn-tract-table` | bool | coverage_flag | False | False |  | 0.0% | unresolved |
| `ghcn_stations_in_tract` | `national-noaa-ghcn-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_temp_stations_in_tract` | `national-noaa-ghcn-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_any_nearest_km` | `national-noaa-ghcn-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_temp_nearest_km` | `national-noaa-ghcn-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_prcp_nearest_km` | `national-noaa-ghcn-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_any_within_25km` | `national-noaa-ghcn-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_temp_within_25km` | `national-noaa-ghcn-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_anchor_unreliable` | `national-noaa-ghcn-tract-table` | bool | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | unresolved |
| `ghcn_year_min` | `national-noaa-ghcn-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | unresolved |
| `ghcn_year_max` | `national-noaa-ghcn-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | unresolved |
| `cdcw_covered` | `national-cdc-wonder-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed_with_clarification |
| `cdcw_grain` | `national-cdc-wonder-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `hwd_maxtemp_mean` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_maxtemp_change` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_maxtemp_trend_days_per_decade` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_maxtemp_trend_p` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_maxtemp_never_defined` | `national-cdc-wonder-tract-table` | bool | measurement | False | False |  | 0.0% | confirmed_with_clarification |
| `hwd_heatindex_mean` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_heatindex_change` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_heatindex_trend_days_per_decade` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_heatindex_trend_p` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed_with_clarification |
| `hwd_heatindex_never_defined` | `national-cdc-wonder-tract-table` | bool | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `hwd_heatstress_mean` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_heatstress_change` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_heatstress_trend_days_per_decade` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed_with_clarification |
| `hwd_heatstress_trend_p` | `national-cdc-wonder-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.9% | confirmed_with_clarification |
| `hwd_heatstress_never_defined` | `national-cdc-wonder-tract-table` | bool | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `cdcw_window_start` | `national-cdc-wonder-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `cdcw_window_end` | `national-cdc-wonder-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `gehe_covered` | `national-nasa-heat-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed_with_clarification |
| `gehe_coverage_frac` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt28_days_mean` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt28_days_change` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt28_trend_days_per_yr` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt30_days_mean` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt30_days_change` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt30_trend_days_per_yr` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt32_days_mean` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt32_days_change` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_wbgt32_trend_days_per_yr` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `gehe_record_start` | `national-nasa-heat-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `gehe_record_end` | `national-nasa-heat-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `uhe_covered` | `national-nasa-heat-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed_with_clarification |
| `uhe_city_name` | `national-nasa-heat-tract-table` | string | identity_metadata | False | True | Source Provenance x Vulnerability | 47.7% | confirmed_with_clarification |
| `uhe_city_country` | `national-nasa-heat-tract-table` | string | identity_metadata | False | True | Source Provenance x Vulnerability | 47.7% | confirmed_with_clarification |
| `uhe_overlap_frac` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 47.7% | confirmed_with_clarification |
| `uhe_wbgtmax28_days_per_yr` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 47.7% | confirmed_with_clarification |
| `uhe_wbgtmax30_days_per_yr` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 47.7% | confirmed_with_clarification |
| `uhe_himax461_days_per_yr` | `national-nasa-heat-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 47.7% | confirmed_with_clarification |

### population (5 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `pop_total` | `national-census-tract-table` | int64 | population | False | True | Population Exposure vs. Disparity; Component Dominance; Dispatch-Blind Reachability | 0.0% | confirmed |
| `pop_urban` | `national-census-tract-table` | int64 | population | False | True | Population Exposure vs. Disparity; Component Dominance; Dispatch-Blind Reachability | 0.0% | confirmed |
| `pop_rural` | `national-census-tract-table` | int64 | population | False | True | Population Exposure vs. Disparity; Component Dominance; Dispatch-Blind Reachability | 0.0% | confirmed |
| `pct_urban` | `national-census-tract-table` | double | population | False | True | Population Exposure vs. Disparity; Component Dominance; Dispatch-Blind Reachability | 0.7% | confirmed |
| `ur_class` | `national-census-tract-table` | string | population | False | True | Population Exposure vs. Disparity; Component Dominance; Dispatch-Blind Reachability | 0.7% | confirmed |

### rurality (15 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `ruca_covered` | `national-ruca-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `ruca_primary` | `national-ruca-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 0.0% | confirmed |
| `ruca_primary_desc` | `national-ruca-tract-table` | string | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 0.0% | confirmed |
| `ruca_secondary` | `national-ruca-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 0.0% | confirmed |
| `ruca_pop_density` | `national-ruca-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability | 0.0% | confirmed |
| `ruca_year` | `national-ruca-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `rucc_covered` | `national-rucc-tract-table` | bool | coverage_flag | False | False |  | 0.0% | confirmed |
| `rucc_2023` | `national-rucc-tract-table` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 0.0% | confirmed |
| `rucc_desc` | `national-rucc-tract-table` | string | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 0.0% | confirmed |
| `rucc_metro` | `national-rucc-tract-table` | bool | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 0.0% | confirmed |
| `rucc_year` | `national-rucc-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `nchs_covered` | `national-nchs-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed_but_flagged |
| `nchs_2013` | `national-nchs-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 1.1% | confirmed_but_flagged |
| `nchs_2013_label` | `national-nchs-tract-table` | string | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; RUCA/RUCC/NCHS Disagreement | 1.1% | confirmed_but_flagged |
| `nchs_year` | `national-nchs-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_but_flagged |

### svi (9 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `svi_covered` | `national-svi-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `svi_rank_universe` | `national-svi-tract-table` | string | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `svi_overall` | `national-svi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.3% | confirmed |
| `svi_socioeconomic` | `national-svi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.3% | confirmed |
| `svi_household` | `national-svi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.3% | confirmed |
| `svi_minority` | `national-svi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.0% | confirmed |
| `svi_housing_transport` | `national-svi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.3% | confirmed |
| `svi_pop` | `national-svi-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `svi_year` | `national-svi-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |

### tribal (9 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `tribal_any` | `national-tribal-tract-table` | bool | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 0.0% | ambiguous_no_marker |
| `tribal_pct` | `national-tribal-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 0.0% | ambiguous_no_marker |
| `tribal_legal` | `national-tribal-tract-table` | bool | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 0.0% | ambiguous_no_marker |
| `tribal_legal_pct` | `national-tribal-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 0.0% | ambiguous_no_marker |
| `tribal_statistical` | `national-tribal-tract-table` | bool | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 0.0% | ambiguous_no_marker |
| `tribal_stat_pct` | `national-tribal-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 0.0% | ambiguous_no_marker |
| `aiannh_geoid` | `national-tribal-tract-table` | string | identity_metadata | False | True | Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 97.0% | ambiguous_no_marker |
| `aiannh_name` | `national-tribal-tract-table` | string | identity_metadata | False | True | Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 97.0% | ambiguous_no_marker |
| `aiannh_kind` | `national-tribal-tract-table` | string | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance; Dispatch-Blind Reachability; Tribal Sub-type + Edge Effect; Population Exposure vs. Disparity | 97.0% | ambiguous_no_marker |

### wildfire (85 columns)

| Column | Source table | dtype | Role | Scoring | Bias | Candidate hypotheses | % null (national) | Vintage |
|---|---|---|---|---|---|---|---|---|
| `usfs_covered` | `national-usfs-wildfire-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `usfs_BP_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_CFL_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_CRPS_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_RPS_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_WHP_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_Exposure_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_FLEP4_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_FLEP8_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_CWiRRZ_majority_label` | `national-usfs-wildfire-tract-table` | string | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_CWiRRZ_majority_zone4_label` | `national-usfs-wildfire-tract-table` | string | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 5.8% | confirmed |
| `usfs_BuildingCount_sum` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_BuildingCover_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_BuildingDensity_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_HUCount_sum` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_HUDen_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_HUExposure_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `usfs_HUImpact_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `usfs_HURisk_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `usfs_PopCount_sum` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_PopDen_mean` | `national-usfs-wildfire-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 1.9% | confirmed |
| `usfs_edition` | `national-usfs-wildfire-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed |
| `usfs_extent` | `national-usfs-wildfire-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed |
| `carbonplan_covered` | `national-carbonplan-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `carbonplan_buildings` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_bp_2011_mean` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_bp_2011_median` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_bp_2047_mean` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_crps_mean` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_rps_2011_mean` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_rps_2011_median` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_rps_2047_mean` | `national-carbonplan-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 2.2% | confirmed |
| `carbonplan_version` | `national-carbonplan-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed |
| `usgs_covered` | `national-usgs-combined-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `usgs_wildland_fire_burned_pct_area` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `usgs_wildfire_burned_pct_area` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `usgs_wildfire_pct_area_2plus` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `usgs_prescribed_burned_pct_area` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.9% | confirmed |
| `usgs_wildfire_return_interval_years` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 90.8% | confirmed |
| `usgs_wildfire_fires_per_burned_pixel` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 90.8% | confirmed |
| `usgs_first_year_burned` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 90.8% | confirmed |
| `usgs_last_year_burned` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 90.8% | confirmed |
| `usgs_years_since_last_fire` | `national-usgs-combined-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 90.8% | confirmed |
| `usgs_wildfire_ever` | `national-usgs-combined-tract-table` | bool | derived_ever_flag | False | True | Measurement Eligibility Bias; Component Dominance | 0.0% | confirmed |
| `usgs_record_start` | `national-usgs-combined-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `usgs_record_end` | `national-usgs-combined-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `mtbs_covered` | `national-mtbs-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed_with_clarification |
| `mtbs_wildfire_burned_pct_land` | `national-mtbs-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed_with_clarification |
| `mtbs_wildfire_burned_km2` | `national-mtbs-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `mtbs_wildfire_fires` | `national-mtbs-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed_with_clarification |
| `mtbs_wildfire_last_year` | `national-mtbs-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 94.3% | confirmed_with_clarification |
| `mtbs_wildfire_ever` | `national-mtbs-tract-table` | bool | derived_ever_flag | False | True | Measurement Eligibility Bias; Component Dominance | 0.0% | confirmed_with_clarification |
| `mtbs_years_since_wildfire` | `national-mtbs-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 94.3% | confirmed_with_clarification |
| `mtbs_prescribed_burned_pct_land` | `national-mtbs-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed_with_clarification |
| `mtbs_year_min` | `national-mtbs-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `mtbs_year_max` | `national-mtbs-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `mtbs_size_threshold` | `national-mtbs-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed_with_clarification |
| `nifc_covered` | `national-nifc-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `nifc_wildfire_burned_pct_land` | `national-nifc-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `nifc_wildfire_burned_km2` | `national-nifc-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `nifc_wildfire_fires` | `national-nifc-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `nifc_wildfire_last_year` | `national-nifc-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 90.9% | confirmed |
| `nifc_wildfire_ever` | `national-nifc-tract-table` | bool | derived_ever_flag | False | True | Measurement Eligibility Bias; Component Dominance | 0.0% | confirmed |
| `nifc_years_since_wildfire` | `national-nifc-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 90.9% | confirmed |
| `nifc_prescribed_burned_pct_land` | `national-nifc-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `nifc_wildfire_fires_history` | `national-nifc-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `nifc_wildfire_fires_wfigs` | `national-nifc-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `nifc_year_min` | `national-nifc-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `nifc_year_max` | `national-nifc-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `fod_covered` | `national-fpa-fod-tract-table` | bool | coverage_flag | False | True | Measurement Eligibility Bias | 0.0% | confirmed |
| `fod_fires` | `national-fpa-fod-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `fod_acres_ignited` | `national-fpa-fod-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `fod_ignition_density` | `national-fpa-fod-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.4% | confirmed |
| `fod_human_fires` | `national-fpa-fod-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `fod_natural_fires` | `national-fpa-fod-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `fod_large_fires` | `national-fpa-fod-tract-table` | int32 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 0.0% | confirmed |
| `fod_human_share` | `national-fpa-fod-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 41.4% | confirmed |
| `fod_human_share_classified` | `national-fpa-fod-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 44.1% | confirmed |
| `fod_cause_unknown_share` | `national-fpa-fod-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 41.4% | confirmed |
| `fod_last_fire_year` | `national-fpa-fod-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 41.4% | confirmed |
| `fod_largest_fire_acres` | `national-fpa-fod-tract-table` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | 41.4% | confirmed |
| `fod_ever` | `national-fpa-fod-tract-table` | bool | derived_ever_flag | False | True | Measurement Eligibility Bias; Component Dominance | 0.0% | confirmed |
| `fod_year_min` | `national-fpa-fod-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `fod_year_max` | `national-fpa-fod-tract-table` | int64 | vintage_metadata | False | False |  | 0.0% | confirmed |
| `fod_edition` | `national-fpa-fod-tract-table` | string | vintage_metadata | False | False |  | 0.0% | confirmed |

## Stage 6, Step 8 — data/processed/<region>-tract-features.parquet (Steps 3-5 new columns)

New columns Steps 3-5 computed on top of the national strata table above — never a re-derivation
of it. The ~63 `STRATA_FEATURE_COLUMNS` joined into this table by Step 4 (`src/features.py:
join_strata_features`) are NOT re-listed here: they are the exact same national-strata columns
already documented above, just joined by GEOID into a second table, with no change to their
domain/role/scoring/bias classification.

**allowed_for_scoring is False for every row below too, but for a DIFFERENT reason than the
strata columns above**: these aren't excluded because they live under `strata/` (they don't — some
are raw ingredients built directly from `reference/` layers) — they're excluded because
`COMPETITION_ALLOWED_COLUMNS` (`src/schemas.py`) is still empty. Step 0 Ambiguity 2 defers freezing
the winning gap-value variant into the actual score until Stage 7's calibration; until that happens
none of these columns — not even single-variant `transport_gap` — has earned `feature_role=
competition`. `src/features.py:assert_competition_only()` enforces this as a runtime allowlist
check, not just a documentation note.

**% null / vintage columns intentionally omitted below** (unlike the table above): those numbers
come from Stage 3's live national-scope profiling pass (Steps 3/5) and Stage 3 Step 4's external
agency-vintage research — neither has been run for this table. A live per-region null-rate/
distinct-value profiling pass for `tract-features.parquet` is a reasonable Stage 8/9 follow-up, not
fabricated here.

### Region control (1 columns)

| Column | Source | dtype | Role | Scoring | Bias | Candidate hypotheses | Description |
|---|---|---|---|---|---|---|---|
| `region` | `src/features.py:attach_region` | string | identity_metadata | False | True |  | Which of the four study regions this tract belongs to (maricopa-az/northern-ca/eastern-ok/south-central-tx) — carried through every join/groupby undropped per Stage 5's finding that transport_gap is not cross-region comparable. |

### Transport (4 columns)

| Column | Source | dtype | Role | Scoring | Bias | Candidate hypotheses | Description |
|---|---|---|---|---|---|---|---|
| `overture_transport_length_m` | `scripts/build_stage6_step3_ingredients.py:build_transport` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Clipped length (meters, geodesic) of Overture named-highway segments (motorway/trunk/primary/secondary) assigned to this tract. |
| `tiger_transport_length_m` | `scripts/build_stage6_step3_ingredients.py:build_transport` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Clipped length (meters, geodesic) of TIGER named-highway segments (MTFCC S1100/S1200) assigned to this tract. |
| `transport_gap` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Candidate capped-ratio gap value: 1 - min(1, overture_transport_length_m / tiger_transport_length_m), clipped to [0, 1]. NOT the frozen score — Stage 7's calibration selects the winning formula/variant. |
| `transport_defined` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | bool | coverage_flag | False | True | Measurement Eligibility Bias | Whether transport_gap is defined (tiger_transport_length_m > 0) — an undefined tract is excluded from the composite mean, never zeroed (R-005). |

### Buildings (8 columns)

| Column | Source | dtype | Role | Scoring | Bias | Candidate hypotheses | Description |
|---|---|---|---|---|---|---|---|
| `overture_building_count_centroid` | `scripts/build_stage6_step3_ingredients.py:build_buildings` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of Overture buildings whose centroid falls within this tract (one of two candidate spatial-assignment variants — Step 0 Ambiguity 2). |
| `overture_building_count_intersection` | `scripts/build_stage6_step3_ingredients.py:build_buildings` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of Overture buildings intersecting this tract (the other candidate spatial-assignment variant). |
| `microsoft_building_count_centroid` | `scripts/build_stage6_step3_ingredients.py:build_buildings` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of Microsoft buildings whose centroid falls within this tract. |
| `microsoft_building_count_intersection` | `scripts/build_stage6_step3_ingredients.py:build_buildings` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of Microsoft buildings intersecting this tract. |
| `building_gap_centroid` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Candidate capped-ratio gap value under the centroid variant: 1 - min(1, overture_building_count_centroid / microsoft_building_count_centroid), clipped to [0, 1]. |
| `building_gap_centroid_defined` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | bool | coverage_flag | False | True | Measurement Eligibility Bias | Whether building_gap_centroid is defined (microsoft_building_count_centroid > 0). |
| `building_gap_intersection` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Candidate capped-ratio gap value under the intersection variant. |
| `building_gap_intersection_defined` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | bool | coverage_flag | False | True | Measurement Eligibility Bias | Whether building_gap_intersection is defined (microsoft_building_count_intersection > 0). |

### POI facilities (12 columns)

| Column | Source | dtype | Role | Scoring | Bias | Candidate hypotheses | Description |
|---|---|---|---|---|---|---|---|
| `overture_poi_count_fire` | `scripts/build_stage6_step3_ingredients.py:build_poi` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of Overture POIs matched to categories.primary='fire_department' in this tract. |
| `hifld_count_fire` | `scripts/build_stage6_step3_ingredients.py:build_poi` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of HIFLD fire stations in this tract (reference ground truth for the fire term). |
| `poi_gap_fire` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Candidate capped-ratio gap value: 1 - min(1, overture_poi_count_fire / hifld_count_fire), clipped to [0, 1]. |
| `poi_gap_fire_defined` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | bool | coverage_flag | False | True | Measurement Eligibility Bias | Whether poi_gap_fire is defined (hifld_count_fire > 0). |
| `overture_poi_count_ems` | `scripts/build_stage6_step3_ingredients.py:build_poi` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of Overture POIs matched to categories.primary='ambulance_and_ems_services' in this tract. |
| `hifld_count_ems` | `scripts/build_stage6_step3_ingredients.py:build_poi` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of HIFLD EMS stations in this tract. |
| `poi_gap_ems` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Candidate capped-ratio gap value for EMS stations, clipped to [0, 1]. |
| `poi_gap_ems_defined` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | bool | coverage_flag | False | True | Measurement Eligibility Bias | Whether poi_gap_ems is defined (hifld_count_ems > 0) — the sparsest defined-flag in the table (EMS stations are rarer than fire/school facilities in every region, confirmed by the real Step 6 run). |
| `overture_poi_count_schools` | `scripts/build_stage6_step3_ingredients.py:build_poi` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of Overture POIs matched to any school-category value (elementary/middle/high/private/public/school) in this tract. |
| `hifld_count_schools` | `scripts/build_stage6_step3_ingredients.py:build_poi` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of HIFLD schools in this tract. |
| `poi_gap_schools` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Candidate capped-ratio gap value for schools, clipped to [0, 1]. |
| `poi_gap_schools_defined` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | bool | coverage_flag | False | True | Measurement Eligibility Bias | Whether poi_gap_schools is defined (hifld_count_schools > 0). |

### Establishments (4 columns)

| Column | Source | dtype | Role | Scoring | Bias | Candidate hypotheses | Description |
|---|---|---|---|---|---|---|---|
| `overture_places_count` | `scripts/build_stage6_step3_ingredients.py:build_poi` | int64 | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Count of ALL Overture POIs in this tract, unfiltered (no hospital exclusion — that applies only to the facilities terms above). |
| `cbp_estab_bus` | `reference/<region>/<region>-census-cbp.parquet` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Census County Business Patterns business-address establishment count for this tract (CBP_ESTAB_COLUMN_DEFAULT) — the reference denominator for the establishments term. The one raw column with a genuine null (CBP non-disclosure suppression). |
| `poi_gap_establishments` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | double | measurement | False | True | Measurement Eligibility Bias; Source Provenance x Vulnerability; Component Dominance | Candidate capped-ratio gap value: 1 - min(1, overture_places_count / cbp_estab_bus), clipped to [0, 1]. |
| `poi_gap_establishments_defined` | `scripts/build_stage6_step3_ingredients.py:build_candidate_gaps` | bool | coverage_flag | False | True | Measurement Eligibility Bias | Whether poi_gap_establishments is defined (cbp_estab_bus > 0). |

### Dispatch-blind reachability (4 columns)

| Column | Source | dtype | Role | Scoring | Bias | Candidate hypotheses | Description |
|---|---|---|---|---|---|---|---|
| `dispatch_blind_threshold_and` | `src/features.py:dispatch_blind_reachability` | double | measurement | False | True | Dispatch-Blind Reachability | 1.0 if transport_gap > 0.5 AND mean(poi_gap_fire, poi_gap_ems) > 0.5, else 0.0 — the threshold-AND candidate combination. |
| `dispatch_blind_normalized_euclidean` | `src/features.py:dispatch_blind_reachability` | double | measurement | False | True | Dispatch-Blind Reachability | sqrt(transport_gap^2 + poi_gap_dispatch^2) / sqrt(2), in [0, 1] — the normalized-Euclidean candidate combination. |
| `dispatch_blind_product` | `src/features.py:dispatch_blind_reachability` | double | measurement | False | True | Dispatch-Blind Reachability | transport_gap * poi_gap_dispatch — the product candidate combination ('both components bad simultaneously'). |
| `dispatch_blind_dari` | `src/features.py:dispatch_blind_reachability` | double | measurement | False | True | Dispatch-Blind Reachability | 1 - (1 - transport_gap)(1 - poi_gap_dispatch) — continuous DARI, 'at least one component is bad enough to block dispatch.' |

### Component dominance/definedness (3 columns)

| Column | Source | dtype | Role | Scoring | Bias | Candidate hypotheses | Description |
|---|---|---|---|---|---|---|---|
| `dominant_component` | `src/features.py:component_dominance_and_definedness` | string | measurement | False | True | Component Dominance; Measurement Eligibility Bias | argmax(transport_gap, building_gap_centroid, building_gap_intersection, poi_gap_fire, poi_gap_ems, poi_gap_schools, poi_gap_establishments) per tract — the single largest gap component, or null if none are defined. |
| `n_components_defined` | `src/features.py:component_dominance_and_definedness` | int64 | measurement | False | True | Component Dominance; Measurement Eligibility Bias | Count of the 7 gap columns that are defined for this tract (0-7). |
| `undefined_components` | `src/features.py:component_dominance_and_definedness` | string | measurement | False | True | Component Dominance; Measurement Eligibility Bias | Comma-joined names of the gap components that are NOT defined for this tract (empty string if all 7 are defined) — direct raw material for the Measurement Eligibility Bias candidate. |
