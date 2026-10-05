"""One-off smoke test for the svi_overall fix in scripts/build_gold_standard_validation.py --
does NOT touch docs/validation/, does not re-render anything. Confirms _load_region_strata now
returns real True/False SVI splits (not all-NaN) for all four regions, and prints the exact
svi_high value for the 10 tracts already selected in Step 9, so their note.md files can be
patched with the corrected value directly rather than by re-running the full pipeline.

Run with:
    python -m scripts.smoke_test_svi_fix
"""
from scripts.build_gold_standard_validation import _load_region_strata

TEN_TRACTS = [
    ("maricopa-az", "04019940800"),
    ("maricopa-az", "04027980004"),
    ("maricopa-az", "04027980003"),
    ("northern-ca", "06033000502"),
    ("northern-ca", "06097154100"),
    ("eastern-ok", "40109108508"),
    ("eastern-ok", "40141070300"),
    ("south-central-tx", "48007950102"),
    ("south-central-tx", "48323950206"),
    ("south-central-tx", "48427950701"),
]

cache = {}
for region in ["maricopa-az", "northern-ca", "eastern-ok", "south-central-tx"]:
    strata = cache[region] = _load_region_strata(region)
    counts = strata["svi_high"].value_counts(dropna=False).to_dict()
    print(f"[{region}] svi_high value counts (True=high, False=low, NaN=svi_covered False): {counts}")

print("\nPer-tract svi_high for the 10 already-selected Step 9 tracts:")
for region, geoid in TEN_TRACTS:
    strata = cache[region]
    if geoid not in strata.index:
        print(f"  {region}/{geoid}: NOT FOUND in strata table -- investigate")
        continue
    print(f"  {region}/{geoid}: svi_high={strata.loc[geoid, 'svi_high']}")
