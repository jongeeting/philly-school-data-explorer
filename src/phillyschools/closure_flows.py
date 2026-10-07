"""Observed enrollment change around the 2013 school closures.

For each school that closed after 2012-13, this finds the 2013-14 catchments that cover its 2012-13
catchment (population-weighted overlap, same school level) and records how each of those schools'
enrollment changed, against the change at district schools with no overlap. It describes what
happened, not who went where: enrollment totals cannot show individual students' moves, and
enrollment by residence is not available before 2016-17 (GAP-031). Nothing here is lineage.
"""

import geopandas as gpd
import pandas as pd

from . import CORE, ROOT
from .geography import CRS_WORK, allocate_blocks, blocks, crosswalk

CLOSED_CSV = ROOT / "registry" / "closures_2013_final.csv"
CLOSED_LAST_SY = 2013
AFTER_SY = 2014
MIN_OVERLAP = 0.05  # share of the closed catchment's population inside a later catchment


def school_totals() -> pd.Series:
    e = pd.read_parquet(CORE / "enrollment.parquet")
    e = e[(e["student_group"] == "all") & (e["grade"] == "ALL")]
    return e.groupby(["school_id", "sy"])["count"].sum()


def build_closure_flows() -> tuple[pd.DataFrame, pd.DataFrame]:
    closed = set(pd.read_csv(CLOSED_CSV, dtype=str)["school_id"])
    catch = gpd.read_parquet(CORE / "catchment.parquet").to_crs(CRS_WORK)
    before = catch[(catch["sy"] == CLOSED_LAST_SY) & catch["school_id"].isin(closed)]
    after = catch[(catch["sy"] == AFTER_SY) & ~catch["school_id"].isin(closed)]
    b = blocks()
    from_alloc = allocate_blocks(b, before.rename(columns={"catchment_id": "unit_id"}))
    to_alloc = allocate_blocks(b, after.rename(columns={"catchment_id": "unit_id"}))
    pairs = crosswalk(from_alloc, to_alloc)
    lvl = catch.set_index("catchment_id")["level"]
    sch = catch.set_index("catchment_id")["school_id"]
    pairs["level"] = pairs["from_unit"].map(lvl)
    pairs = pairs[pairs["level"] == pairs["to_unit"].map(lvl)]
    pairs["closed_school_id"] = pairs["from_unit"].map(sch)
    pairs["receiving_school_id"] = pairs["to_unit"].map(sch)
    pairs = pairs.rename(columns={"pop_share_of_from": "closed_catchment_pop_share"})
    pairs = pairs[pairs["closed_catchment_pop_share"] >= MIN_OVERLAP]
    # a school with elementary and middle catchments can reach the same receiver twice
    pairs = (
        pairs.sort_values("closed_catchment_pop_share", ascending=False)
        .drop_duplicates(["closed_school_id", "receiving_school_id"])
        .reset_index(drop=True)
    )

    tot = school_totals()
    pairs["closed_enrollment_2013"] = pairs["closed_school_id"].map(
        lambda s: tot.get((s, CLOSED_LAST_SY))
    )
    pairs["enrollment_2013"] = pairs["receiving_school_id"].map(
        lambda s: tot.get((s, CLOSED_LAST_SY))
    )
    pairs["enrollment_2014"] = pairs["receiving_school_id"].map(lambda s: tot.get((s, AFTER_SY)))
    pairs["change"] = pairs["enrollment_2014"] - pairs["enrollment_2013"]
    pairs["enrollment_known"] = pairs["change"].notna()

    # baseline: change at district schools that overlap no closed catchment
    district = pd.read_parquet(CORE / "enrollment.parquet")
    district = set(district[district["sector"] == "District"]["school_id"])
    touched = set(pairs["receiving_school_id"]) | closed
    ids = [s for s in tot.index.get_level_values(0).unique() if s in district and s not in touched]
    base = pd.DataFrame(
        {
            "a": [tot.get((s, CLOSED_LAST_SY)) for s in ids],
            "b": [tot.get((s, AFTER_SY)) for s in ids],
        }
    ).dropna()
    base_pct = float((base["b"] - base["a"]).sum() / base["a"].sum())
    pairs["baseline_pct_change"] = round(base_pct, 4)
    pairs["change_beyond_baseline"] = (
        pairs["change"] - pairs["baseline_pct_change"] * pairs["enrollment_2013"]
    ).round(0)
    # a receiving school's gain is split across the closed catchments it overlaps, by the
    # population each shares with it, so it is never counted twice
    weight = pairs["pop_2020"]
    pairs["gain_allocated"] = (
        pairs["change_beyond_baseline"].clip(lower=0)
        * weight
        / weight.groupby(pairs["receiving_school_id"]).transform("sum")
    ).round(0)

    plan = pd.read_parquet(CORE / "school_closure_plan.parquet")
    named = set(zip(plan["closing_school_id"], plan["receiving_school_id"], strict=True))
    pairs["named_in_2012_proposal"] = [
        (c, r) in named
        for c, r in zip(pairs["closed_school_id"], pairs["receiving_school_id"], strict=True)
    ]
    school = pd.read_parquet(CORE / "school.parquet").set_index("school_id")["current_name"]
    pairs["closed_school_name"] = pairs["closed_school_id"].map(school)
    pairs["receiving_school_name"] = pairs["receiving_school_id"].map(school)
    out = pairs[
        [
            "closed_school_id",
            "closed_school_name",
            "level",
            "receiving_school_id",
            "receiving_school_name",
            "closed_catchment_pop_share",
            "named_in_2012_proposal",
            "closed_enrollment_2013",
            "enrollment_2013",
            "enrollment_2014",
            "enrollment_known",
            "change",
            "baseline_pct_change",
            "change_beyond_baseline",
            "gain_allocated",
        ]
    ].copy()
    out["closed_catchment_pop_share"] = out["closed_catchment_pop_share"].round(4)
    out = out.sort_values(
        ["closed_school_id", "closed_catchment_pop_share"], ascending=[True, False]
    )
    out["status"] = "derived"
    out["method"] = "catchment_overlap_2013_to_2014_v1"
    out["source_id"] = "sdp_catchments+sdp_enrollment"
    known = out[out["enrollment_known"]]
    summary = (
        out.groupby(["closed_school_id", "closed_school_name"])
        .agg(
            closed_enrollment_2013=("closed_enrollment_2013", "first"),
            overlapping_schools=("receiving_school_id", "nunique"),
        )
        .join(
            known.groupby(["closed_school_id", "closed_school_name"]).agg(
                schools_with_enrollment=("receiving_school_id", "nunique"),
                net_change=("change", "sum"),
                gain_beyond_baseline=("gain_allocated", "sum"),
            )
        )
        .reset_index()
    )
    summary["gain_share_of_closed_enrollment"] = (
        summary["gain_beyond_baseline"] / summary["closed_enrollment_2013"]
    ).round(2)
    return out.reset_index(drop=True), summary


def write_closure_flows() -> tuple[pd.DataFrame, pd.DataFrame]:
    flows, summary = build_closure_flows()
    for name, df in (("school_closure_flow", flows), ("school_closure_flow_summary", summary)):
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    return flows, summary
