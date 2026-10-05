"""ACS 5-year neighborhood context, by tract and rolled up to every geo unit.

Two periods:
  2020-2024  table-based Summary File (2020 tracts), keyless bulk download
  2015-2019  sequence-based Summary File (2010 tracts), keyless; crosswalked through 2020
             census blocks by 2020 population (an approximation for that period)

Table `area_context`, grain: geo unit x ACS period x measure. Tract values come straight from
the Census Bureau (status `reported`, with margin of error); catchments, assignment zones, and
neighborhoods are rolled up through the population-weighted crosswalk (status `derived`):
counts are allocated by each tract's share of 2020 population in the unit, and shares are
recomputed from the allocated counts. Median household income cannot be combined exactly; the
rollup is the household-weighted average of tract medians (`median_household_income_approx`),
in each period's own dollars. Margins of error are not computed for rollups yet.
"""

import zipfile

import pandas as pd

from . import CORE, RAW

ACS_DIR = RAW / "census_acs5"
ACS2019_DIR = RAW / "census_acs5_2019"
PHILLY_TRACT = "1400000US42101"
CHILD_BELOW = [f"B17001_E{n:03d}" for n in list(range(4, 10)) + list(range(18, 24))]
CHILD_ABOVE = [f"B17001_E{n:03d}" for n in list(range(33, 39)) + list(range(47, 53))]
BA_PLUS = [f"B15003_E{n:03d}" for n in range(22, 26)]
# 2015-2019 sequence-based file: table -> (sequence, 1-based start column, cells)
SEQ_2019 = {
    "B15003": ("0042", 125, 25),
    "B17001": ("0047", 7, 59),
    "B19013": ("0058", 177, 1),
    "B25003": ("0111", 11, 3),
}

# measure -> (numerator columns, denominator columns)
RATIOS = {
    "acs_pct_people_in_poverty": (["B17001_E002"], ["B17001_E001"]),
    "acs_pct_children_in_poverty": (CHILD_BELOW, CHILD_BELOW + CHILD_ABOVE),
    "acs_pct_adults_ba_or_higher": (BA_PLUS, ["B15003_E001"]),
    "acs_pct_owner_occupied": (["B25003_E002"], ["B25003_E001"]),
}


def _read_table_2024(table: str) -> pd.DataFrame:
    path = ACS_DIR / f"acsdt5y2024-{table}.dat"
    keep = []
    for chunk in pd.read_csv(path, sep="|", dtype=str, chunksize=200_000):
        keep.append(chunk[chunk["GEO_ID"].str.startswith(PHILLY_TRACT)])
    d = pd.concat(keep, ignore_index=True)
    d["unit_id"] = "tract_" + d["GEO_ID"].str[-11:]
    return d.set_index("unit_id").drop(columns="GEO_ID")


def tract_counts() -> pd.DataFrame:
    """2020-2024 ACS for Philadelphia's 2020 tracts."""
    t = pd.concat([_read_table_2024(x) for x in ["b17001", "b19013", "b15003", "b25003"]], axis=1)
    return t.apply(pd.to_numeric, errors="coerce")


def tract_counts_2019() -> pd.DataFrame:
    """2015-2019 ACS for Philadelphia's 2010 tracts, with the same column names."""
    geo = pd.read_csv(ACS2019_DIR / "g20195pa.csv", header=None, dtype=str, encoding="latin-1")
    geoid = geo.apply(
        lambda r: next((v for v in r if isinstance(v, str) and "US" in v), None), axis=1
    )
    geo = pd.DataFrame({"sumlev": geo[2], "logrecno": geo[4], "geoid": geoid})
    tr = geo[(geo["sumlev"] == "140") & geo["geoid"].fillna("").str.startswith("14000US42101")]
    tr = tr.set_index("logrecno")
    out = pd.DataFrame(index=tr.index)
    for table, (seq, start, cells) in SEQ_2019.items():
        z = zipfile.ZipFile(ACS2019_DIR / f"20195pa{seq}000.zip")
        for kind, letter in (("e", "E"), ("m", "M")):
            d = pd.read_csv(z.open(f"{kind}20195pa{seq}000.txt"), header=None, dtype=str)
            d = d.set_index(5)  # LOGRECNO
            cols = list(range(start - 1, start - 1 + cells))
            block = d.loc[d.index.intersection(out.index), cols]
            block.columns = [f"{table}_{letter}{i:03d}" for i in range(1, cells + 1)]
            out = out.join(block)
    out.index = "tract2010_" + tr.loc[out.index, "geoid"].str[-11:]
    return out.apply(pd.to_numeric, errors="coerce")


def tract_rows(t: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for measure, (num, den) in RATIOS.items():
        n, d = t[num].sum(axis=1), t[den].sum(axis=1)
        for unit, nv, dv in zip(t.index, n, d, strict=True):
            rows.append(
                {
                    "unit_id": unit,
                    "measure_id": measure,
                    "numerator": nv,
                    "denominator": dv,
                    "value": None if dv == 0 else round(nv / dv * 100, 1),
                    "moe": None,
                    "status": "reported" if dv > 0 else "not_applicable",
                }
            )
    for unit, v, m in zip(t.index, t["B19013_E001"], t["B19013_M001"], strict=True):
        ok = pd.notna(v) and v > 0
        rows.append(
            {
                "unit_id": unit,
                "measure_id": "acs_median_household_income",
                "numerator": None,
                "denominator": None,
                "value": v if ok else None,
                "moe": m if ok else None,
                "status": "reported" if ok else "suppressed",
            }
        )
    out = pd.DataFrame(rows)
    out["unit_type"] = out["unit_id"].map(
        lambda u: "tract_2010" if u.startswith("tract2010_") else "tract"
    )
    out["sy"] = pd.NA
    return out


def rollup(t: pd.DataFrame, from_type: str) -> pd.DataFrame:
    xw = pd.read_parquet(CORE / "geo_xwalk.parquet")
    xw = xw[xw["from_type"] == from_type][
        ["from_unit", "to_unit", "to_type", "sy", "pop_share_of_from"]
    ]
    rows = []
    for measure, (num, den) in RATIOS.items():
        base = pd.DataFrame({"n": t[num].sum(axis=1), "d": t[den].sum(axis=1)})
        j = xw.merge(base, left_on="from_unit", right_index=True)
        j["n"] *= j["pop_share_of_from"]
        j["d"] *= j["pop_share_of_from"]
        g = j.groupby(["to_unit", "to_type", "sy"], dropna=False)[["n", "d"]].sum().reset_index()
        g["measure_id"] = measure
        g["value"] = (g["n"] / g["d"] * 100).round(1).where(g["d"] > 0)
        rows.append(g.rename(columns={"n": "numerator", "d": "denominator"}))
    hh = pd.DataFrame(
        {
            "inc": t["B19013_E001"].where(t["B19013_E001"] > 0),
            "hh": t["B25003_E001"],
        }
    )
    j = xw.merge(hh, left_on="from_unit", right_index=True).dropna(subset=["inc"])
    j["w"] = j["hh"] * j["pop_share_of_from"]
    j["iw"] = j["inc"] * j["w"]
    g = j.groupby(["to_unit", "to_type", "sy"], dropna=False)[["iw", "w"]].sum().reset_index()
    g["value"] = (g["iw"] / g["w"]).where(g["w"] > 0).round(0)
    g["measure_id"] = "acs_median_household_income_approx"
    rows.append(g.drop(columns=["iw", "w"]))
    out = pd.concat(rows, ignore_index=True).rename(
        columns={"to_unit": "unit_id", "to_type": "unit_type"}
    )
    out["moe"] = None
    out["status"] = out["value"].notna().map({True: "derived", False: "not_applicable"})
    return out


PERIODS = {
    # period: (loader, crosswalk from_type, source key)
    "2020-2024": (tract_counts, "tract", "census_acs5"),
    "2015-2019": (tract_counts_2019, "tract_2010", "census_acs5_2019"),
}


def period_for_sy(sy: int) -> str:
    """ACS period used for a school year: 2015-2019 through 2019-20, 2020-2024 after."""
    return "2015-2019" if sy <= 2020 else "2020-2024"


def build_area_context() -> pd.DataFrame:
    parts = []
    for period, (load, from_type, key) in PERIODS.items():
        t = load()
        p = pd.concat([tract_rows(t), rollup(t, from_type)], ignore_index=True)
        p["acs_period"] = period
        p["source_id"] = f"{key}:{period}"
        parts.append(p)
    out = pd.concat(parts, ignore_index=True)
    out["sy"] = out["sy"].astype("Int64")
    cols = [
        "unit_id",
        "unit_type",
        "sy",
        "acs_period",
        "measure_id",
        "value",
        "moe",
        "numerator",
        "denominator",
        "status",
        "source_id",
    ]
    return out[cols]


def write_area_context(df: pd.DataFrame) -> None:
    df.to_parquet(CORE / "area_context.parquet", index=False)
    df.to_csv(CORE / "area_context.csv", index=False)
