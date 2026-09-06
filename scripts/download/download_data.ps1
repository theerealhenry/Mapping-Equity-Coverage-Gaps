# scripts/download/download_data.ps1 — placeholder, no functional stage owner yet.
#
# Per PROJECT_BLUEPRINT.md Section 1 (Stage 1 — Data acquisition & governance): "No bulk local
# download by default — the pipeline reads directly from the bucket (bbox/column pushdown via
# DuckDB) except where a stage genuinely needs a local cache (Stage 6 onward); intermediate results
# are cached to data/interim/ as parquet, gitignored." This project's data-acquisition design
# deliberately avoids bulk download as the normal path.
#
# This script's purpose is narrow: a manual escape hatch for the rare case an actual local bulk
# download of the bucket is genuinely needed (e.g. working fully offline, or a bucket-access
# interruption). It would wrap the same anonymous-S3 read pattern src/io.py already uses for
# individual objects, generalized into a full-bucket sync — not a different access method, just a
# different scale of the same one.
#
# Intentionally empty — not yet needed by any stage's normal workflow, and only built out if and
# when a genuine local-bulk-download need actually arises.
