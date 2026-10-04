"""Roll catchment flows up to neighborhoods (derived estimates).

Method `catchment_flow_to_neighborhood_v1`:
  1. Each flow row says how many students living in a school's catchment attend a given school.
  2. Those students are spread over neighborhoods in proportion to where the catchment's 2020
     population lives (geo_xwalk, census-block weights). Boundaries for a school year come from
     that year's catchment map, or the latest one published (2024-25) for later years.
  3. The flow file does not say which of a school's catchments (ES, MS, HS) a student belongs
     to. Schools with two levels are weighted by grade span: K-8 as 6/9 elementary and 3/9
     middle; 6-12 as 4/7 high and 3/7 middle. Where the two areas coincide this changes nothing.
  4. Students whose address could not be placed, or whose catchment school has no boundary
     that year, are reported citywide as `unplaced`, never dropped.

Published values follow the small-cell rule: any estimate under 20 students is suppressed
(value blank, status `suppressed`), and so is any percentage whose numerator is suppressed.
Complementary suppression (recovering a cell from totals) is not handled yet.
"""

import pandas as pd

from . import CORE, ROOT

DERIVED = ROOT / "derived"
METHOD = "catchment_flow_to_neighborhood_v1"
SMALL_CELL = 20
LEVEL_WEIGHTS = {
    ("ES",): {"ES": 1.0},
    ("MS",): {"MS": 1.0},
    ("HS",): {"HS": 1.0},
    ("ES", "MS"): {"ES": 6 / 9, "MS": 3 / 9},
    ("HS", "MS"): {"HS": 4 / 7, "MS": 3 / 7},
}


def catchment_to_neighborhood_shares() -> pd.DataFrame:
    """Share of each catchment's 2020 population living in each neighborhood."""
    xw = pd.read_parquet(CORE / "geo_xwalk.parquet")
    xw = xw[(xw["from_type"] == "neighborhood") & xw["to_type"].str.startswith("catchment_")]
    catch = pd.read_parquet(CORE / "catchment.parquet")[
        ["catchment_id", "school_id", "level", "sy"]
    ]
    s = xw.drop(columns="sy").merge(catch, left_on="to_unit", right_on="catchment_id")
    s = s[["school_id", "level", "sy", "from_unit", "pop_share_of_to"]].rename(
        columns={"sy": "vintage", "from_unit": "neighborhood_id", "pop_share_of_to": "share"}
    )
    # Neighborhood polygons overlap slightly, so raw shares can sum a little over 1 (max 1.07);
    # rescale so each catchment's students are allocated exactly once.
    total = s.groupby(["school_id", "level", "vintage"])["share"].transform("sum")
    s["share"] = s["share"] / total
    return s


def enrolled_sector(sy_attr: pd.DataFrame, placeholders: pd.DataFrame) -> pd.DataFrame:
    """Sector of every enrolled school by year: District, Charter, Contracted, or placeholder kind."""
    a = sy_attr[["school_id", "sy", "governance"]].rename(columns={"governance": "sector"})
    p = placeholders[["school_id", "kind"]].rename(columns={"kind": "sector"})
    return a, p.set_index("school_id")["sector"]


def allocate(flows: pd.DataFrame, shares: pd.DataFrame, latest_vintage: int) -> tuple:
    f = flows.copy()
    f["vintage"] = f["sy"].clip(upper=latest_vintage)
    levels = (
        shares.groupby(["vintage", "school_id"])["level"]
        .apply(lambda s: tuple(sorted(set(s))))
        .rename("levels")
        .reset_index()
    )
    f = f.merge(
        levels.rename(columns={"school_id": "catchment_school_id"}),
        on=["vintage", "catchment_school_id"],
        how="left",
    )
    placed = f[(f["catchment_status"] == "reported") & f["levels"].notna() & f["count"].notna()]
    unplaced = f.drop(placed.index)

    weights = []
    for lv, w in LEVEL_WEIGHTS.items():
        for level, weight in w.items():
            weights.append({"levels": lv, "level": level, "level_weight": weight})
    weights = pd.DataFrame(weights)
    p = placed.merge(weights, on="levels")
    p = p.merge(
        shares.rename(columns={"school_id": "catchment_school_id"}),
        on=["vintage", "catchment_school_id", "level"],
    )
    p["students_est"] = p["count"] * p["level_weight"] * p["share"]
    return p, unplaced


def build_neighborhood_flows() -> dict:
    flows = pd.read_parquet(CORE / "catchment_flow.parquet")
    shares = catchment_to_neighborhood_shares()
    latest = int(shares["vintage"].max())
    p, unplaced = allocate(flows, shares, latest)

    attr = pd.read_parquet(CORE / "school_year_attr.parquet")
    placeholders = pd.read_parquet(CORE / "school_placeholder.parquet")
    by_year, ph_sector = enrolled_sector(attr, placeholders)
    p = p.merge(
        by_year.rename(columns={"school_id": "enrolled_school_id"}),
        on=["enrolled_school_id", "sy"],
        how="left",
    )
    # Schools missing from a year's list (alternative schools were left off 2020-2025 lists)
    # take their sector from their most recent listed year.
    latest_gov = attr.sort_values("sy").groupby("school_id")["governance"].last()
    p["sector"] = (
        p["sector"]
        .fillna(p["enrolled_school_id"].map(latest_gov))
        .fillna(p["enrolled_school_id"].map(ph_sector))
        .fillna("unknown")
    )
    p["own_catchment_school"] = p["enrolled_school_id"] == p["catchment_school_id"]

    flow = p.groupby(["sy", "neighborhood_id", "enrolled_school_id"], as_index=False)[
        "students_est"
    ].sum()

    resident = (
        p.groupby(["sy", "neighborhood_id"])["students_est"].sum().rename("resident_students_est")
    )
    own = (
        p[p["own_catchment_school"]]
        .groupby(["sy", "neighborhood_id"])["students_est"]
        .sum()
        .rename("attending_catchment_school_est")
    )
    sector = p.pivot_table(
        index=["sy", "neighborhood_id"],
        columns="sector",
        values="students_est",
        aggfunc="sum",
        fill_value=0,
    )
    sector.columns = [
        f"enrolled_{c.lower().replace(' ', '_').replace('-', '_')}_est" for c in sector.columns
    ]
    summary = pd.concat([resident, own, sector], axis=1).fillna(0).reset_index()
    summary["pct_attending_catchment_school"] = (
        summary["attending_catchment_school_est"] / summary["resident_students_est"] * 100
    )

    unplaced_by_year = (
        unplaced.groupby("sy")["count"].sum().rename("unplaced_students").reset_index()
    )
    checks = flows.groupby("sy")["count"].sum().rename("flow_total").reset_index()
    checks = (
        checks.merge(
            p.groupby("sy")["students_est"].sum().rename("allocated").reset_index(), on="sy"
        )
        .merge(unplaced_by_year, on="sy", how="left")
        .fillna({"unplaced_students": 0})
    )
    checks["difference"] = checks["flow_total"] - checks["allocated"] - checks["unplaced_students"]

    return {"flow": flow, "summary": summary, "unplaced": unplaced_by_year, "checks": checks}


def publishable(t: dict) -> dict:
    """Long tables with status, small cells suppressed, method tagged."""
    names = pd.read_parquet(CORE / "geo_unit.parquet")
    names = names[names["unit_type"] == "neighborhood"].set_index("unit_id")["name"]

    flow = t["flow"].copy()
    flow["status"] = (flow["students_est"] < SMALL_CELL).map({True: "suppressed", False: "derived"})
    flow["students_est"] = flow["students_est"].round().where(flow["status"] == "derived")
    flow["neighborhood"] = flow["neighborhood_id"].map(names)

    s = t["summary"]
    long = s.melt(id_vars=["sy", "neighborhood_id"], var_name="measure_id", value_name="value")
    counts = long["measure_id"] != "pct_attending_catchment_school"
    small = counts & (long["value"] < SMALL_CELL)
    own_small = (
        s.set_index(["sy", "neighborhood_id"])["attending_catchment_school_est"] < SMALL_CELL
    )
    pct_small = ~counts & long.set_index(["sy", "neighborhood_id"]).index.map(own_small).to_numpy(
        bool
    )
    long["status"] = "derived"
    long.loc[small | pct_small, "status"] = "suppressed"
    long["value"] = long["value"].where(long["status"] == "derived")
    long.loc[counts, "value"] = long.loc[counts, "value"].round()
    long.loc[~counts, "value"] = long.loc[~counts, "value"].round(1)
    long["neighborhood"] = long["neighborhood_id"].map(names)

    for df in (flow, long):
        df["method"] = METHOD
        df["source_id"] = "sdp_catchment_retention + geo_xwalk"
    return {"neighborhood_flow": flow, "neighborhood_metric": long}


def write_neighborhood_flows(t: dict, pub: dict) -> None:
    DERIVED.mkdir(exist_ok=True)
    for name, df in pub.items():
        df.to_parquet(DERIVED / f"{name}.parquet", index=False)
        df.to_csv(DERIVED / f"{name}.csv", index=False)
    t["checks"].to_csv(DERIVED / "neighborhood_flow_checks.csv", index=False)
