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
