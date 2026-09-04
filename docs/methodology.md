# Methodology

**Author:** Henry Otsyula
**Challenge:** Bias Bounty Mapping Equity Challenge (Zindi)

> Status: skeleton — filled in as the pipeline is built. Section headers follow the challenge's
> documentation guidance and the Best Documentation judging criteria.

## 1. Overview and objectives

<!-- High-level description of the solution, the problem it addresses, expected outcomes. -->

## 2. Architecture

<!-- Diagram + description of the end-to-end data flow: extract -> transform -> score -> submit. -->

## 3. ETL process

### 3.1 Extract

<!-- Data sources, formats, extraction method (direct cloud-native GeoParquet reads via bbox
     pushdown vs. bulk download), volume, and Overture release pinning. -->

### 3.2 Transform

<!-- Per-component transformation logic: road length aggregation, building count aggregation,
     POI category matching, CBP join. Cleansing/preprocessing steps. -->

### 3.3 Load

<!-- How transformed, tract-level results are stored and assembled into the submission file. -->

## 4. Coverage gap computation

<!-- Full definition of each component (road gap, building gap, POI gap), the formula used,
     and how the mean-of-defined-components composite is computed. -->

### 4.1 Road network gap

### 4.2 Building footprint gap

### 4.3 POI gap

## 5. Edge case handling

<!-- Explicit treatment of: zero-population tracts, water-dominated (99xx) tracts, tracts with
     no Overture data at all, tracts with no reference data for a given component (undefined
     handling), and the Maricopa New Mexico tract. -->

## 6. Alternative weightings considered

<!-- Any alternative component weightings or formulas tried, and why the final choice was made. -->

## 7. Validation and performance

<!-- Runtime per script/notebook, public and private leaderboard RMSE, sanity checks against
     published region statistics (tract counts, undefined-component percentages). -->

## 8. Error handling and logging

## 9. Reproducibility

<!-- Random seeds, environment (local machine specs, Python/library versions), requirements.txt. -->

## 10. Maintenance and scaling notes

## 11. Bias Discovery findings

<!-- See docs/bias_discovery.md for the full write-up submitted for the Best Bias Discovery prize. -->
</content>
