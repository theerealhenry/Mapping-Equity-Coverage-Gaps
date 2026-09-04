# Bias Bounty Mapping Equity Challenge

**Author:** Henry Otsyula

Solution repository for the *Bias Bounties @ Scale: Mapping Equity Challenge* (Zindi, hosted by
Humane Intelligence / Reliabl, in partnership with Radiant Earth and supported by the
Heising-Simons Foundation).

## Problem

Open map data (Overture Maps) underpins emergency dispatch, evacuation routing, and disaster
relief. This project measures how completely Overture covers four US regions — Maricopa County AZ
(heat/drought), the Northern California fire corridor (wildfire), Eastern Oklahoma tribal
statistical areas (drought/heat), and South-Central Texas along I-35/I-37 (heat/drought) — against
four authoritative reference sources, at the Census-tract level:

- Census TIGER/Line Roads (road network coverage)
- Microsoft US Building Footprints (building coverage)
- USGS National Map critical facilities (fire stations, EMS, schools)
- Census County Business Patterns (business establishment coverage)

Each tract receives a **coverage gap score** in `[0, 1]` (0 = full coverage, 1 = no coverage),
scored against an organiser-held reference by RMSE. Every submission is additionally evaluated by
an automated **Bias Score** that measures whether coverage gaps fall disproportionately on rural,
tribal, high-social-vulnerability, or climate-exposed communities.

## Repository structure

```
bias-bounty-mapping-equity/
├── README.md                  this file
├── requirements.txt           pinned dependencies
├── .gitignore
├── src/                       reusable pipeline code
│   ├── config.py               region/layer constants, bucket paths
│   ├── ...
├── notebooks/                  EDA and exploration notebooks
├── docs/                       methodology write-up, bias discovery write-up, diagrams
├── data/                       local cache of downloaded parquet (gitignored)
└── submissions/                generated submission CSVs (gitignored except final selections)
```

## Data access

All challenge data is read directly from the public Source Cooperative bucket
(`s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/`),
cloud-native GeoParquet, no credentials required. See `src/config.py` for the exact paths used and
`docs/methodology.md` for the full data-access and processing pipeline.

Overture Maps layers are pinned to release `2026-08-19.0`; all computation in this repository uses
that release only.

## Environment

- Local machine, VS Code, Python (see `requirements.txt` for exact pinned versions).
- Reproducibility: random seeds are set wherever randomness is used; see `docs/methodology.md`
  for the full reproducibility notes.

## Status

Work in progress — see `docs/methodology.md` for the current state of the pipeline and results.
</content>
