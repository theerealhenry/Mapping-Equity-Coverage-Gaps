"""
Stage 3 Step 4 follow-up (pulled forward from Stage 8/9) — does the NCHS Urban-Rural Classification
vintage lag actually change any study-region county's classification?

`docs/data_vintage_confirmation.md`'s review pass found that this project's rurality domain uses the
2013 NCHS Urban-Rural Classification Scheme for Counties (`nchs_year=2013`), while CDC has since
published a 2023 scheme — but CDC's own page states "there were minimal differences in county
assignments between the 2023 and 2013 schemes." Presenting the raw vintage gap alone as a Best Bias
Discovery finding would be an overclaim CDC's own documentation directly undercuts. The only honest
way to know whether this project's four actual study regions are affected at all is to check.

CDC publishes a single combined crosswalk file with all four scheme vintages (1990/2006/2013/2023)
side by side per county: https://www.cdc.gov/nchs/data/data-analysis/NCHSurb-rural-codes.csv
(documented column layout, per CDC's own 2023-File-Documentation-final.pdf: STFIPS, CTYFIPS,
ST_ABBREV, CTYNAME, CODE1990, CODE2006, CODE2013, CODE2023 — codes 1-4 are metro tiers, from 1 =
large central metro down to 4 = small metro; 5 = micropolitan; 6 = noncore/nonmetro).

This script downloads that crosswalk, loads each of the four study regions' REAL scored-tract GEOID
lists (`src.io.load_sample_submission` — the same Section 4.8/4.9 rule every other step in this
project uses: never a hardcoded county list, always derived from the real sample-submission), derives
each tract's county FIPS from its own GEOID (first 5 digits — no assumption about which counties a
region covers is baked in anywhere), and reports every county in every region whose 2013 code differs
from its 2023 code.

**If the result is zero reclassified counties across all four regions, the vintage-lag claim in
`docs/data_vintage_confirmation.md` should be DROPPED entirely, not kept as a softened or hedged
finding.** A null result here is itself the answer to the question this script exists to ask, and
stretching it into a "finding anyway" would be exactly the kind of overclaim the review pass that
produced this script was trying to avoid a second time.

Like Steps 3 and 4, only `load_nchs_crosswalk` and `main()` touch the network; every other function
is pure and tested against small, hand-built fixtures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config import REGIONS, STRATA_KEY_COLUMN
from src.io import load_sample_submission

NCHS_CROSSWALK_URL = "https://www.cdc.gov/nchs/data/data-analysis/NCHSurb-rural-codes.csv"
DEFAULT_OUTPUT_PATH = Path("docs/nchs_reclassification_check.csv")

_NCHS_CROSSWALK_USER_AGENT = "bias-bounty-mapping-equity/1.0 (+https://www.cdc.gov)"
"""Sent as the User-Agent header on a real HTTP(S) `load_nchs_crosswalk` read only — see that
function's docstring. Any descriptive, non-default value is sufficient; this one only needs to not
look like the default `Python-urllib/x.y` a front end might be blocking, mirroring `src.io._SAMPLE_
SUBMISSION_USER_AGENT`."""

REQUIRED_CROSSWALK_COLUMNS = ("STFIPS", "CTYFIPS", "CODE2013", "CODE2023")

NCHS_CODE_MEANINGS: dict[int, str] = {
    1: "Large central metro",
    2: "Large fringe metro",
    3: "Medium metro",
    4: "Small metro",
    5: "Micropolitan",
    6: "Noncore (nonmetro)",
}


# --- Pure functions (fully testable with no network) --------------------------------------------


def derive_county_fips(geoid: str) -> str:
    """A Census tract GEOID's first 5 digits are its county FIPS code (2-digit state + 3-digit
    county). Raises ValueError on a GEOID shorter than 5 characters rather than silently returning
    a truncated/wrong value."""
    if len(geoid) < 5:
        raise ValueError(f"GEOID {geoid!r} is shorter than 5 characters, cannot derive county FIPS")
    return geoid[:5]


def normalize_state_county_fips(stfips, ctyfips) -> str:
    """Builds a 5-character county FIPS string from separate state/county FIPS fields, whatever
    their source dtype (int, float-with-.0, or already-zero-padded string) — CDC's crosswalk file's
    exact on-disk representation of these two fields was not independently confirmed before writing
    this script (network access to fetch and inspect it directly was not available), so this
    normalizes defensively rather than assuming either is already correctly zero-padded."""
    state_str = str(int(float(stfips))).zfill(2)
    county_str = str(int(float(ctyfips))).zfill(3)
    return state_str + county_str


def find_reclassified_counties(
    crosswalk: pd.DataFrame, county_fips: set[str], *, region: str
) -> pd.DataFrame:
    """One row per county FIPS in `county_fips` (a region's real, derived-from-GEOID county set):
    whether it was found in the crosswalk at all, its 2013 and 2023 codes and meanings, and whether
    those two codes differ. A county not found in the crosswalk (should not happen for any real US
    county, but not assumed) gets `found_in_crosswalk=False` and null codes rather than being
    silently dropped — a silent drop here would be indistinguishable from "this county was checked
    and found unchanged," which is exactly the distinction this check exists to get right.
    """
    by_fips = crosswalk.set_index("county_fips")
    records = []
    for fips in sorted(county_fips):
        if fips not in by_fips.index:
            records.append(
                {
                    "region": region,
                    "county_fips": fips,
                    "found_in_crosswalk": False,
                    "code_2013": None,
                    "code_2023": None,
                    "meaning_2013": None,
                    "meaning_2023": None,
                    "reclassified": None,
                }
            )
            continue
        row = by_fips.loc[fips]
        # A county FIPS is unique in a correctly-formed crosswalk; if the file ever has a duplicate,
        # take the first row rather than crashing on an ambiguous .loc lookup.
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        code_2013 = row["CODE2013"]
        code_2023 = row["CODE2023"]
        records.append(
            {
                "region": region,
                "county_fips": fips,
                "found_in_crosswalk": True,
                "code_2013": code_2013,
                "code_2023": code_2023,
                "meaning_2013": NCHS_CODE_MEANINGS.get(code_2013),
                "meaning_2023": NCHS_CODE_MEANINGS.get(code_2023),
                "reclassified": code_2013 != code_2023,
            }
        )
    return pd.DataFrame.from_records(records)


# --- Real-path orchestration (network required) --------------------------------------------------


def load_nchs_crosswalk(source: str = NCHS_CROSSWALK_URL) -> pd.DataFrame:
    """Downloads (or, for testing, reads a local path) CDC's all-vintage NCHS crosswalk and adds a
    normalized `county_fips` column. Fails loudly and specifically if the file's columns don't match
    what CDC's own 2023-File-Documentation-final.pdf says they should be — that documentation was
    read, but the raw file itself could not be independently fetched and inspected from the sandbox
    that built this script (network access to cdc.gov was not available there), so this is the one
    real assumption in this whole step that has NOT been directly, empirically verified before
    shipping. If this fails, paste the actual header row back so the column-name assumption can be
    corrected.

    A real HTTP(S) read sends a custom `User-Agent` header (see `src.io._SAMPLE_SUBMISSION_USER_
    AGENT`'s docstring for the confirmed failure mode this defends against — a different bucket, but
    the exact same front-end/CDN behavior: `pandas.read_csv`'s default plain-`urllib` User-Agent
    getting rejected with `HTTP Error 403: Forbidden`, fixed by sending an ordinary, non-default
    client identity). This project has already hit this exact failure mode once for real (the
    source.coop sample-submission bucket); applying the same defensive header here for cdc.gov is
    cheap and could not be empirically confirmed necessary or unnecessary from the sandbox that
    wrote this script (network access to cdc.gov was unavailable there — see above), so it is
    applied preemptively rather than waited on. The header is applied only when `source` is an
    actual http(s) URL, matching `load_sample_submission`'s guard exactly: `storage_options` passed
    for a local file path raises `ValueError: storage_options passed with file object or non-fsspec
    file path` in this project's pinned pandas version, which would otherwise break this function's
    own local-fixture-path tests.
    """
    read_kwargs: dict = {}
    if source.startswith(("http://", "https://")):
        read_kwargs["storage_options"] = {"User-Agent": _NCHS_CROSSWALK_USER_AGENT}
    raw = pd.read_csv(source, **read_kwargs)

    missing = [c for c in REQUIRED_CROSSWALK_COLUMNS if c not in raw.columns]
    if missing:
        raise RuntimeError(
            f"NCHS crosswalk at {source!r} is missing expected column(s) {missing}. Actual columns "
            f"found: {list(raw.columns)}. This script's column-name assumption (STFIPS, CTYFIPS, "
            "CODE2013, CODE2023, per CDC's 2023-File-Documentation-final.pdf) was not independently "
            "verified against the raw file before shipping — please paste this actual header row "
            "back so it can be corrected."
        )

    raw["county_fips"] = [
        normalize_state_county_fips(s, c) for s, c in zip(raw["STFIPS"], raw["CTYFIPS"])
    ]
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk-source", default=NCHS_CROSSWALK_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    print(f"Downloading NCHS all-vintage crosswalk from {args.crosswalk_source}...")
    try:
        crosswalk = load_nchs_crosswalk(args.crosswalk_source)
    except Exception as exc:
        print(f"ERROR: could not load the NCHS crosswalk: {exc}", file=sys.stderr)
        return 2
    print(f"Loaded {len(crosswalk)} counties from the crosswalk.")

    all_results = []
    for region in REGIONS:
        print(f"\nLoading {region}'s real sample-submission GEOID list...")
        sample_submission = load_sample_submission(region)
        geoids = sample_submission[STRATA_KEY_COLUMN].astype(str)
        county_fips = {derive_county_fips(g) for g in geoids}
        print(f"  {region}: {len(geoids)} scored tracts across {len(county_fips)} distinct counties.")

        region_results = find_reclassified_counties(crosswalk, county_fips, region=region)
        all_results.append(region_results)

        not_found = region_results.loc[~region_results["found_in_crosswalk"]]
        if len(not_found) > 0:
            print(
                f"  WARNING: {len(not_found)} county FIPS not found in the NCHS crosswalk: "
                f"{sorted(not_found['county_fips'])}. These cannot be checked.",
                file=sys.stderr,
            )

        reclassified = region_results.loc[region_results["reclassified"] == True]  # noqa: E712
        print(f"  {len(reclassified)} of {len(county_fips)} counties reclassified between 2013 and 2023.")
        if len(reclassified) > 0:
            print(reclassified[["county_fips", "code_2013", "meaning_2013", "code_2023", "meaning_2023"]].to_string(index=False))

    results_df = pd.concat(all_results, ignore_index=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(args.output, index=False)
    print(f"\nWrote {len(results_df)} region/county rows to {args.output}")

    total_reclassified = results_df.loc[results_df["reclassified"] == True]  # noqa: E712
    if len(total_reclassified) == 0:
        print(
            "\nZERO counties reclassified between the 2013 and 2023 NCHS schemes across all four "
            "study regions. Per this script's own module docstring: the NCHS vintage-lag claim in "
            "docs/data_vintage_confirmation.md should now be DROPPED, not kept as a hedged finding — "
            "this null result is itself the answer."
        )
    else:
        print(
            f"\n{len(total_reclassified)} region/county combination(s) DID change classification — "
            "this is a genuine, quantifiable, county-specific vintage-bias finding. Update "
            "docs/data_vintage_confirmation.md with the specific counties and codes above."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
