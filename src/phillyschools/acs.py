"""ACS 5-year neighborhood context (2020-2024), by tract and rolled up to every geo unit.

Table `area_context`, grain: geo unit x ACS period x measure. Tract values come straight
from the Census Bureau's table-based Summary File (status `reported`, with margin of error);
catchments, assignment zones, and neighborhoods are rolled up through the population-weighted
crosswalk (status `derived`): counts are allocated by each tract's share of 2020 population
in the unit, and shares are recomputed from the allocated counts. Median household income
cannot be combined exactly; the rollup is the household-weighted average of tract medians
(`median_household_income_approx`). Margins of error are not computed for rollups yet.
"""

import pandas as pd

from . import CORE, RAW

ACS_DIR = RAW / "census_acs5"
PERIOD = "2020-2024"
PHILLY_TRACT = "1400000US42101"
CHILD_BELOW = [f"B17001_E{n:03d}" for n in list(range(4, 10)) + list(range(18, 24))]
CHILD_ABOVE = [f"B17001_E{n:03d}" for n in list(range(33, 39)) + list(range(47, 53))]
BA_PLUS = [f"B15003_E{n:03d}" for n in range(22, 26)]

# measure -> (numerator columns, denominator columns)
RATIOS = {
    "acs_pct_people_in_poverty": (["B17001_E002"], ["B17001_E001"]),
    "acs_pct_children_in_poverty": (CHILD_BELOW, CHILD_BELOW + CHILD_ABOVE),
    "acs_pct_adults_ba_or_higher": (BA_PLUS, ["B15003_E001"]),
    "acs_pct_owner_occupied": (["B25003_E002"], ["B25003_E001"]),
}


def read_table(table: str) -> pd.DataFrame:
    path = ACS_DIR / f"acsdt5y2024-{table}.dat"
    keep = []
    for chunk in pd.read_csv(path, sep="|", dtype=str, chunksize=200_000):
        keep.append(chunk[chunk["GEO_ID"].str.startswith(PHILLY_TRACT)])
    d = pd.concat(keep, ignore_index=True)
    d["unit_id"] = "tract_" + d["GEO_ID"].str[-11:]
    return d.set_index("unit_id").drop(columns="GEO_ID")


def tract_counts() -> pd.DataFrame:
    t = pd.concat([read_table(x) for x in ["b17001", "b19013", "b15003", "b25003"]], axis=1)
    return t.apply(pd.to_numeric, errors="coerce")


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
    out["unit_type"], out["sy"] = "tract", pd.NA
    return out


def rollup(t: pd.DataFrame) -> pd.DataFrame:
    xw = pd.read_parquet(CORE / "geo_xwalk.parquet")
    xw = xw[xw["from_type"] == "tract"][
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
    hh = pd.DataFrame({"inc": t["B19013_E001"].where(t["B19013_E001"] > 0), "hh": t["B25003_E001"]})
    j = xw.merge(hh, left_on="from_unit", right_index=True).dropna(subset=["inc"])
    j["w"] = j["hh"] * j["pop_share_of_from"]
    g = (
        j.groupby(["to_unit", "to_type", "sy"], dropna=False)
        .apply(
            lambda x: (x["inc"] * x["w"]).sum() / x["w"].sum() if x["w"].sum() > 0 else None,
            include_groups=False,
        )
        .rename("value")
        .reset_index()
    )
    g["measure_id"] = "acs_median_household_income_approx"
    rows.append(g)
    out = pd.concat(rows, ignore_index=True).rename(
        columns={"to_unit": "unit_id", "to_type": "unit_type"}
    )
    out["moe"] = None
    out["status"] = out["value"].notna().map({True: "derived", False: "not_applicable"})
    return out


def build_area_context() -> pd.DataFrame:
    t = tract_counts()
    out = pd.concat([tract_rows(t), rollup(t)], ignore_index=True)
    out["acs_period"] = PERIOD
    out["source_id"] = "census_acs5:" + PERIOD
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
