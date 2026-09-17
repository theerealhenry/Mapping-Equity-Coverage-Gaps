"""One-off diagnostic for Stage 6 Step 9's Check 2 failure — localizes WHY transport_defined is
near-100% True when Section 4.22 says roughly half of maricopa-az's tracts should be undefined.
Reads only what's already on disk (data/processed/<region>-step3-ingredients.parquet and
-tract-features.parquet) — no network, no re-computation. Delete after use; not a permanent script.
"""
import pandas as pd

for region in ["maricopa-az", "eastern-ok"]:
    print(f"\n=== {region} ===")
    ing = pd.read_parquet(f"data/processed/{region}-step3-ingredients.parquet")
    feat = pd.read_parquet(f"data/processed/{region}-tract-features.parquet")

    print("step3-ingredients.parquet:")
    print("  transport_defined value_counts:", ing["transport_defined"].value_counts(dropna=False).to_dict())
    print("  tiger_transport_length_m describe:\n", ing["tiger_transport_length_m"].describe())
    print("  tiger_transport_length_m == 0 count:", (ing["tiger_transport_length_m"] == 0).sum())
    print("  tiger_transport_length_m isna count:", ing["tiger_transport_length_m"].isna().sum())
    print("  dtype:", ing["transport_defined"].dtype, ing["tiger_transport_length_m"].dtype)

    print("tract-features.parquet:")
    print("  transport_defined value_counts:", feat["transport_defined"].value_counts(dropna=False).to_dict())
    print("  dtype:", feat["transport_defined"].dtype)

    # Do the two files even agree with each other?
    merged = ing[["GEOID", "transport_defined"]].merge(
        feat[["GEOID", "transport_defined"]], on="GEOID", suffixes=("_ingredients", "_features")
    )
    mismatch = merged["transport_defined_ingredients"] != merged["transport_defined_features"]
    print("  ingredients vs. tract-features mismatch count:", mismatch.sum())
