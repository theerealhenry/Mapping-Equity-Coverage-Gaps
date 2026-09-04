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
├── PROJECT_BLUEPRINT.md       full stage-by-stage build reference (single source of truth)
├── requirements.txt           pinned dependencies (see docs/reproducibility.md for why each pin)
├── pyproject.toml             pytest configuration
├── Makefile                   thin convenience wrapper around src/cli.py (macOS/Linux)
├── .gitignore
├── src/                       reusable pipeline code
│   ├── cli.py                  canonical command-line interface — python -m src.cli --help
│   ├── config.py                region/layer constants, bucket paths, SEED
│   └── ...                      (schemas.py, io.py, gaps.py, features.py etc. added stage by stage)
├── scripts/                   one-off and governance scripts (bucket audit, data manifest)
├── notebooks/                  EDA and exploration notebooks
├── tests/                      pytest suite
├── docs/                       methodology, bias discovery write-up, data manifest, reproducibility
├── data/                       local cache of downloaded parquet (gitignored)
└── submissions/                generated submission CSVs (gitignored except final selections)
```

## Getting started

```powershell
conda create -n bias-bounty python=3.11
conda activate bias-bounty
pip install -r requirements.txt
python -m src.cli --help
pytest
```

See `docs/reproducibility.md` for the full environment setup record and the dependency
compatibility investigation behind `requirements.txt`'s exact pins.

## Data access

All challenge data is read directly from the public Source Cooperative bucket
(`s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/`),
cloud-native GeoParquet, no credentials required. See `src/config.py` for the exact paths used,
`docs/data_manifest.md` for the confirmed facts about the data package (object inventory, schemas,
what is and isn't shipped), and `docs/methodology.md` for the full data-access and processing
pipeline.

Overture Maps layers are pinned to release `2026-08-19.0`; all computation in this repository uses
that release only.

## Environment

- Local machine, VS Code, Miniconda (Python 3.11) — see `requirements.txt` for exact pinned
  versions and `docs/reproducibility.md` for the full setup record.
- Reproducibility: a single `SEED` constant (`src/config.py`) is imported wherever randomness is
  used; see `docs/reproducibility.md` for the full reproducibility notes.

## Status

Work in progress — see `PROJECT_BLUEPRINT.md` for the full stage-by-stage plan and current stage,
and `docs/methodology.md` for the write-up of results as they're produced.
</content>
