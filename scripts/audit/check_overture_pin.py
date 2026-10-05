"""
Verify that the Overture layers in the challenge's reference bucket carry release/version
metadata consistent with src.config.OVERTURE_RELEASE, and look for any bucket-level manifest
documenting the pin.

Run from the repo root:
    python scripts/audit/check_overture_pin.py

Reads via the SAME transport src/io.py's load_reference_layer uses in production -- anonymous
S3 (pyarrow.fs.S3FileSystem), not HTTPS -- since this bucket's HTTPS front end rejects
plain-urllib clients (see src/io.py's module docstring, "Update, Stage 2 Step 7").

Checks, for one region (maricopa-az) across the three Overture layers actually used by the
pipeline (buildings, roads, pois):
  1. Parquet file-level key-value metadata
  2. Parquet schema-level metadata
  3. The GeoParquet "geo" metadata blob (commonly carries source/provenance info)
  4. Any column whose name hints at version/release/theme/update/source
Then looks for a manifest/README/CHANGELOG at the bucket root or under reference/<region>/,
read the same way pandas.read_csv reads the sample-submission CSV in production (spoofed
User-Agent), since the bucket's HTTPS front end blocks the default urllib identity.

Read-only -- does not change any pipeline behavior.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pyarrow.parquet as pq
from pyarrow.fs import S3FileSystem

from src.config import HTTPS_BASE, OVERTURE_RELEASE, S3_REGION, reference_s3_path

REGION = "maricopa-az"
LAYERS = ["overture-buildings", "overture-roads", "overture-pois"]
USER_AGENT = "bias-bounty-mapping-equity/1.0 (+https://data.source.coop)"


def check_layer(fs: S3FileSystem, region: str, layer: str) -> None:
    path = reference_s3_path(region, layer)
    print(f"\n--- {region}/{layer} ---")
    print(f"s3://{path}")
    try:
        pf = pq.ParquetFile(path, filesystem=fs)
        meta = pf.metadata
        kv = meta.metadata or {}
        print("File-level key-value metadata keys:", list(kv.keys()))
        for k, v in kv.items():
            vs = v if isinstance(v, bytes) else str(v).encode()
            print(f"  {k}: {vs[:500]}")
            if b"geo" in k.lower():
                try:
                    geo = json.loads(vs)
                    print("    parsed geo metadata:", json.dumps(geo, indent=2)[:1500])
                except Exception as e:
                    print("    (could not parse as JSON)", e)
        schema_meta = pf.schema_arrow.metadata or {}
        print("Schema-level metadata keys:", list(schema_meta.keys()) if schema_meta else None)
        cols = pf.schema_arrow.names
        print("All columns:", cols)
        interesting = [c for c in cols if any(t in c.lower() for t in ("version", "release", "theme", "update", "source"))]
        print("Columns hinting at version/theme/source:", interesting)
        if interesting:
            tbl = pf.read(columns=interesting[:5])
            for c in interesting[:5]:
                print(f"  sample {c}:", tbl.column(c).to_pylist()[:3])
    except Exception as e:
        print("ERROR:", repr(e))


def check_manifests() -> None:
    print("\n--- Looking for a manifest/README documenting the release pin (HTTPS, spoofed UA) ---")
    candidates = [
        "README.md", "MANIFEST.md", "CHANGELOG.md", "manifest.json", "PROVENANCE.md",
        f"reference/{REGION}/README.md", f"reference/{REGION}/MANIFEST.md",
        "docs/data_manifest.csv",
    ]
    for candidate in candidates:
        url = f"{HTTPS_BASE}/{candidate}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()  # full body, not just a preview -- needed to grep it below
                print(f"FOUND {url} ({resp.status}, {len(body)} bytes)")
                if candidate == "README.md":
                    text = body.decode("utf-8", errors="replace")
                    print("\n--- grep for '2026-08-19' and 'release' (case-insensitive) ---")
                    for i, line in enumerate(text.splitlines(), 1):
                        if "2026-08-19" in line or "release" in line.lower():
                            print(f"  L{i}: {line.strip()}")
                    out = Path("/tmp/bucket_readme.md") if Path("/tmp").exists() else Path("./_bucket_readme.md")
                    out.write_text(text, encoding="utf-8")
                    print(f"\nFull README saved to {out} ({len(text)} chars) for manual inspection.")
        except Exception as e:
            print(f"  not found: {candidate} ({e})")


if __name__ == "__main__":
    print(f"Config pin: OVERTURE_RELEASE = {OVERTURE_RELEASE!r}")
    fs = S3FileSystem(anonymous=True, region=S3_REGION)
    for layer in LAYERS:
        check_layer(fs, REGION, layer)
    check_manifests()
