# Best Bias Discovery — Write-up

**Author:** Henry Otsyula

> Status: skeleton — to be filled in once EDA on the strata tables is complete.

Per the challenge's Best Bias Discovery criteria, this write-up must:

1. **Identify a disparity pattern the automated scorecard does not surface** — outside the five
   fixed metrics (Coverage Disparity Ratio, POI Desert Index, Emergency Access Gap, Road Network
   Equity Ratio, Climate-Justice Composite) across the predefined strata (urban/rural, SVI, CVI,
   tribal, heat/wildfire/drought exposure).
2. **Show the evidence** — name the tracts/areas, the data and comparisons, in enough detail for
   judges to reproduce the finding from the challenge data (and any documented additional public
   sources).
3. **Explain who is affected and why it matters** — connect the pattern to concrete consequences
   for emergency dispatch, evacuation routing, or disaster relief.

Judged on: Impact 30%, Novelty 25%, Evidence 25%, Reproducibility 20%.

Additional public datasets are permitted for this prize only (not for the scored submission
itself), and must be documented here with URLs and retrieval dates.

## Candidate angles (to investigate)

- **Overture buildings `subtype`/`class` null-rate gradient (surfaced early, Stage 2 Step 5 audit —
  see `docs/data_manifest.md` Section 4.8).** A building footprint existing in Overture is not the
  same as it carrying any category information: the null rate for `subtype` (and near-identically
  for `class`) climbs sharply and monotonically with exactly the regions this challenge is asking
  about — 62.1% in Maricopa (urban), 80.3% in South-Central Texas, 88.3% in Northern California (the
  wildfire corridor), 94.2% in Eastern Oklahoma (tribal statistical areas). This is a data-source
  behavior pattern the automated scorecard cannot see at all: the scorecard's building-gap component
  only compares footprint *counts* against Microsoft's reference, so a tract can score a clean
  building gap while the footprints it "has" are functionally anonymous — no way to tell a home from
  a shed from a clinic from the geometry and attributes alone. That gap between "counted" and
  "usefully categorized" is invisible to every one of the five official metrics, and it gets worse in
  precisely the tribal and wildfire-corridor regions this challenge frames as highest-stakes for
  emergency response. Candidate framing to test in Stage 8/9: does this null-rate gradient predict
  anything once SVI, tribal status, and rurality are already controlled for (i.e. is it doing
  independent work, or just restating "rural areas are less mapped" in a different column)? Worth
  cross-checking against the Source provenance × vulnerability candidate below, since the two may
  share a root cause (which upstream provider contributed the footprint) or may be genuinely
  separate mechanisms (a footprint can come from a well-attributed source and still lack subtype).
- Overture `sources` provenance (which upstream dataset feeds each feature — OSM vs. ML-derived
  footprints vs. Google Open Buildings) correlated with coverage gap size.
- Patterns within a stratum rather than across it (e.g. gaps concentrated in a sub-population of
  rural tracts rather than rural tracts generally).
- The South-Central Texas region's colonias.
- The Maricopa package's single New Mexico tract (35023970000) as a boundary-effect case study.
- Tribal statistical areas vs. tribal subdivisions distinction in Eastern Oklahoma.

## Finding(s)

<!-- To be completed. -->

## Evidence

<!-- To be completed. -->

## Impact

<!-- To be completed. -->

## Additional data sources used (if any)

<!-- URL, retrieval date, license, for each additional source used in this section only. -->
</content>
