"""Peer comparison: each school against the schools most similar in student poverty.

Method `poverty_peers_k15_v1` (derived; no ranks, no composite score):
  - For each year, window, and measure, a school's peers are the 15 other schools in the same
    grade band whose poverty share is closest to its own.
  - The comparison reports the school's value, the peers' median and middle half (25th to
    75th percentile), the difference from the peer median, and a plain position: above the
    peer range, within it, or below it.
  - Poverty basis (`basis`), three versions side by side:
      school_econ_disadvantaged             PDE's economically disadvantaged share of the
                                            school's own students (same year and agency)
      catchment_child_poverty               ACS 2020-2024 child poverty of the school's own
                                            catchment (neighborhood schools only)
      student_neighborhoods_child_poverty   enrollment-weighted ACS child poverty of the
                                            catchments where the school's students live
                                            (catchment flows; covers charter and citywide
                                            schools; 2016-17 on)
    Census bases use ACS 2015-2019 for school years through 2019-20 and ACS 2020-2024 after.
    They carry the poverty figure's margin of error (`basis_moe`) and `position_robust`: true
    when the school's position is the same with its poverty at both edges of that margin.
    K-8 census-based positions are robust only about half the time for proficiency (peer
    groups span a few points; catchment child poverty is +/- 8 to 10 points), so show a
    census-based position only where it is robust.
  - Selective-admission schools (criteria-based, citywide with criteria, special admit) are
    neither compared nor used as peers: their results reflect who is admitted. Alternative,
    virtual, and transition programs are left out for the same reason.
  - Grade bands: K-8 (elementary, middle, elementary-middle), high, and mixed (6-12 and
    K-12), because Future Ready proficiency mixes PSSA and Keystone results by grade span.
    A band with fewer than 16 eligible schools in a year produces no comparison
    (status not_applicable, "fewer than 15 comparable schools").
  - Two windows (`window`): one year, and a three-year average (value and poverty averaged
    over the window, at least two years with data).
  - Stability (checked on non-overlapping periods, 2021-23 vs 2023-25 school years): a
    school's difference from its peers repeats at r = 0.60 for ELA proficiency but only
    0.34 (ELA) and 0.45 (math) for growth. Describe positions cautiously, prefer the
    averaged window, and never use them to label a school.
"""

import numpy as np
import pandas as pd

from . import CORE, ROOT

DERIVED = ROOT / "derived"
K = 15
METHOD = f"poverty_peers_k{K}_v1"
MEASURES = ["pct_proficient_ela", "pct_proficient_math", "growth_score_ela", "growth_score_math"]
SELECTIVE = {"citywide with criteria", "criteria-based", "special admit"}
NOT_COMPARABLE = {"alternative", "virtual"}
BANDS = {
    "Elementary": "k8",
    "Middle": "k8",
    "Elementary-Middle": "k8",
    "High": "high",
    "Middle-High": "mixed",
    "Elementary-Middle-High": "mixed",
    "Elementary-High": "mixed",
}


def school_context() -> pd.DataFrame:
    a = pd.read_parquet(CORE / "school_year_attr.parquet")
    a = a[["school_id", "sy", "level", "admission_type", "governance"]].copy()
    adm = a["admission_type"].fillna("").str.lower()
    a["band"] = a["level"].map(BANDS)
    a["eligible"] = a["band"].notna() & ~adm.isin(SELECTIVE | NOT_COMPARABLE)
    a["exclusion"] = None
    a.loc[adm.isin(SELECTIVE), "exclusion"] = "selective admission"
    a.loc[adm.isin(NOT_COMPARABLE), "exclusion"] = "alternative or virtual program"
    a.loc[a["band"].isna() & a["exclusion"].isna(), "exclusion"] = "grade span not comparable"
    return a


def poverty_basis() -> pd.DataFrame:
    m = pd.read_parquet(CORE / "school_metric.parquet")
    p = m[
        (m["measure_id"] == "state_pct_of_enrollment")
        & (m["student_group"] == "econ_disadvantaged")
        & (m["status"].isin(["reported", "blended"]))
    ]
    return p[["school_id", "sy", "value"]].rename(columns={"value": "poverty_pct"})


def _catchment_child_poverty(period: str) -> pd.DataFrame:
    """ACS child poverty of every catchment for one ACS period, with school, level, and year."""
    ac = pd.read_parquet(CORE / "area_context.parquet")
    ac = ac[
        (ac["measure_id"] == "acs_pct_children_in_poverty")
        & (ac["status"] == "derived")
        & (ac["acs_period"] == period)
    ]
    c = pd.read_parquet(CORE / "catchment.parquet")[["catchment_id", "school_id", "level", "sy"]]
    return c.merge(ac[["unit_id", "value", "moe"]], left_on="catchment_id", right_on="unit_id")[
        ["school_id", "level", "sy", "value", "moe"]
    ].rename(columns={"sy": "vintage", "value": "child_poverty"})


def by_period(basis_fn, *args) -> pd.DataFrame:
    """Run a census basis for each ACS period and keep, for each school year, the period that
    fits it (2015-2019 through 2019-20, 2020-2024 after)."""
    from .acs import PERIODS, period_for_sy

    parts = []
    for period in PERIODS:
        b = basis_fn(period, *args)
        parts.append(b[b["sy"].map(period_for_sy) == period].assign(acs_period=period))
    return pd.concat(parts, ignore_index=True)


def catchment_basis(period: str, ctx: pd.DataFrame) -> pd.DataFrame:
    """Child poverty of the school's own catchment (neighborhood schools only).

    K-8 schools use their elementary catchment (middle if none); high schools their high
    school catchment. Boundaries: that year's map, or the latest published for later years.
    """
    cp = _catchment_child_poverty(period)
    latest = int(cp["vintage"].max())
    pref = {"k8": ["ES", "MS"], "high": ["HS"], "mixed": ["MS", "HS"]}
    rows = []
    look_moe = cp.set_index(["school_id", "vintage", "level"])["moe"]
    look = cp.set_index(["school_id", "vintage", "level"])["child_poverty"]
    for r in ctx.dropna(subset=["band"]).itertuples():
        v = min(int(r.sy), latest)
        for level in pref[r.band]:
            key = (r.school_id, v, level)
            if key in look.index:
                rows.append(
                    {
                        "school_id": r.school_id,
                        "sy": r.sy,
                        "poverty_pct": look[key],
                        "basis_moe": look_moe[key],
                    }
                )
                break
    return pd.DataFrame(rows, columns=["school_id", "sy", "poverty_pct", "basis_moe"])


def student_neighborhoods_basis(period: str) -> pd.DataFrame:
    """Enrollment-weighted child poverty of the catchments where a school's students live.

    Uses catchment flows (2016-17 on); a K-8 or 6-12 catchment school's ES/MS/HS areas are
    weighted by grade span, as in the neighborhood rollup. Students with unplaced addresses
    are left out of the average.
    """
    from .neighborhoods import LEVEL_WEIGHTS

    cp = _catchment_child_poverty(period)
    latest = int(cp["vintage"].max())
    levels = cp.groupby(["school_id", "vintage"])["level"].apply(lambda x: tuple(sorted(set(x))))
    look = cp.set_index(["school_id", "vintage", "level"])["child_poverty"]
    look_moe = cp.set_index(["school_id", "vintage", "level"])["moe"]
    combined_moe = {}
    combined = {}
    for (sid, v), lv in levels.items():
        w = LEVEL_WEIGHTS.get(lv)
        if w:
            combined[(sid, v)] = sum(look[(sid, v, level)] * wt for level, wt in w.items())
            combined_moe[(sid, v)] = np.sqrt(
                sum((look_moe[(sid, v, level)] * wt) ** 2 for level, wt in w.items())
            )
    f = pd.read_parquet(CORE / "catchment_flow.parquet")
    f = f[(f["catchment_status"] == "reported") & f["count"].notna()].copy()
    f["vintage"] = f["sy"].clip(upper=latest)
    f["child_poverty"] = [
        combined.get((c, v)) for c, v in zip(f["catchment_school_id"], f["vintage"], strict=True)
    ]
    f = f.dropna(subset=["child_poverty"])
    f["child_poverty_moe"] = [
        combined_moe.get((c, v))
        for c, v in zip(f["catchment_school_id"], f["vintage"], strict=True)
    ]
    f["w"] = f["count"] * f["child_poverty"]
    # MOE of an enrollment-weighted average, treating catchments as independent
    f["m2"] = (f["count"] * f["child_poverty_moe"]) ** 2
    g = (
        f.groupby(["enrolled_school_id", "sy"])
        .agg(w=("w", "sum"), n=("count", "sum"), m2=("m2", "sum"))
        .reset_index()
    )
    g = g[g["n"] >= 20]
    g["poverty_pct"] = (g["w"] / g["n"]).round(1)
    g["basis_moe"] = (np.sqrt(g["m2"]) / g["n"]).round(1)
    return g.rename(columns={"enrolled_school_id": "school_id"})[
        ["school_id", "sy", "poverty_pct", "basis_moe"]
    ]


def _position(others: pd.DataFrame, poverty: float, value: float, k: int):
    peers = others.loc[(others["poverty_pct"] - poverty).abs().nsmallest(k).index]
    q = peers["value"].quantile([0.25, 0.5, 0.75])
    if value > q.iloc[2]:
        position = "above peer range"
    elif value < q.iloc[0]:
        position = "below peer range"
    else:
        position = "within peer range"
    return peers, tuple(q), position


def compare(values: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """values: school_id, band, poverty_pct, value (one year, one measure, one window)."""
    rows = []
    for band, g in values.groupby("band"):
        missing = g[g["poverty_pct"].isna()]
        for r in missing.itertuples():
            rows.append(
                {
                    "school_id": r.school_id,
                    "band": band,
                    "value": r.value,
                    "poverty_pct": None,
                    "exclusion": "no poverty figure on this basis",
                }
            )
        g = g.dropna(subset=["poverty_pct", "value"]).reset_index(drop=True)
        for i, r in g.iterrows():
            others = g.drop(index=i)
            if len(others) < k:
                rows.append(
                    {
                        "school_id": r["school_id"],
                        "band": band,
                        "value": r["value"],
                        "poverty_pct": r["poverty_pct"],
                        "exclusion": f"fewer than {k} comparable schools",
                    }
                )
                continue
            peers, (q25, med, q75), position = _position(others, r["poverty_pct"], r["value"], k)
            moe = r.get("basis_moe")
            robust = None
            if pd.notna(moe):
                # Same position with the school's poverty at both edges of its margin of error?
                robust = all(
                    _position(others, r["poverty_pct"] + shift, r["value"], k)[2] == position
                    for shift in (-moe, moe)
                )
            rows.append(
                {
                    "school_id": r["school_id"],
                    "band": band,
                    "value": r["value"],
                    "poverty_pct": round(r["poverty_pct"], 1),
                    "peer_n": k,
                    "peer_poverty_min": round(peers["poverty_pct"].min(), 1),
                    "peer_poverty_max": round(peers["poverty_pct"].max(), 1),
                    "peer_p25": round(q25, 1),
                    "peer_median": round(med, 1),
                    "peer_p75": round(q75, 1),
                    "diff_from_peer_median": round(r["value"] - med, 1),
                    "position": position,
                    "peer_school_ids": "|".join(peers["school_id"]),
                    "basis_moe": moe,
                    "position_robust": robust,
                    "exclusion": None,
                }
            )
    return pd.DataFrame(rows)


def pooled(values: pd.DataFrame, years: int = 3, min_years: int = 2) -> pd.DataFrame:
    """Average value and poverty over the window ending in each year (needs min_years)."""
    rows = []
    for (sid, measure), g in values.groupby(["school_id", "measure_id"]):
        g = g.set_index("sy")
        for sy in g.index:
            w = g.loc[(g.index > sy - years) & (g.index <= sy)]
            if w["value"].notna().sum() >= min_years:
                rows.append(
                    {
                        "school_id": sid,
                        "measure_id": measure,
                        "sy": sy,
                        "value": round(w["value"].mean(), 1),
                        "basis_moe": w["basis_moe"].mean() if "basis_moe" in w else np.nan,
                        "poverty_pct": w["poverty_pct"].mean(),
                        "years_used": int(w["value"].notna().sum()),
                    }
                )
    return pd.DataFrame(rows)


def _compare_all(base: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (sy, measure), g in base.groupby(["sy", "measure_id"]):
        eligible = g["eligible"].fillna(False).astype(bool)
        res = compare(g[eligible])
        if not res.empty:
            res["sy"], res["measure_id"] = sy, measure
            res["status"] = res["exclusion"].isna().map({True: "derived", False: "not_applicable"})
            out.append(res)
        excluded = g[~eligible][["school_id", "value", "exclusion"]]
        out.append(excluded.assign(sy=sy, measure_id=measure, status="not_applicable"))
    df = pd.concat(out, ignore_index=True)
    df["exclusion"] = df["exclusion"].fillna("")
    df.loc[(df["status"] == "not_applicable") & (df["exclusion"] == ""), "exclusion"] = (
        "not on the district school list that year"
    )
    return df


BASES = {
    "school_econ_disadvantaged": "pde_future_ready + pde_fast_facts",
    "catchment_child_poverty": "pde_future_ready + census_acs5 + sdp_catchments",
    "student_neighborhoods_child_poverty": "pde_future_ready + census_acs5 + sdp_catchment_retention",
}


def build_peer_comparison() -> pd.DataFrame:
    """Comparisons for each poverty basis and window (one year, three-year average)."""
    m = pd.read_parquet(CORE / "school_metric.parquet")
    ctx = school_context()
    scores = m[
        m["measure_id"].isin(MEASURES)
        & (m["student_group"] == "all")
        & m["status"].isin(["reported", "blended"])
    ]
    bases = {
        "school_econ_disadvantaged": poverty_basis(),
        "catchment_child_poverty": by_period(catchment_basis, ctx),
        "student_neighborhoods_child_poverty": by_period(student_neighborhoods_basis),
    }
    frames = []
    for basis, pov in bases.items():
        if "basis_moe" not in pov:
            pov = pov.assign(basis_moe=np.nan)
        one = scores.merge(
            pov[["school_id", "sy", "poverty_pct", "basis_moe"]], on=["school_id", "sy"], how="left"
        )[["school_id", "sy", "measure_id", "value", "poverty_pct", "basis_moe"]]
        for window, vals in [("1 year", one), ("3-year average", pooled(one))]:
            df = _compare_all(vals.merge(ctx, on=["school_id", "sy"], how="left"))
            df["window"], df["basis"], df["source_id"] = window, basis, BASES[basis]
            frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["method"] = METHOD
    return out


def write_peer_comparison(df: pd.DataFrame) -> None:
    DERIVED.mkdir(exist_ok=True)
    df.to_parquet(DERIVED / "peer_comparison.parquet", index=False)
    df.to_csv(DERIVED / "peer_comparison.csv", index=False)
