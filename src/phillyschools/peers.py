"""Peer comparison: each school against the schools most similar in student poverty.

Method `poverty_peers_k15_v1` (derived; no ranks, no composite score):
  - For each year, window, and measure, a school's peers are the 15 other schools in the same
    grade band whose poverty share is closest to its own.
  - The comparison reports the school's value, the peers' median and middle half (25th to
    75th percentile), the difference from the peer median, and a plain position: above the
    peer range, within it, or below it.
  - Poverty basis (`basis`): `school_econ_disadvantaged` = PDE's economically disadvantaged
    share of the school's own students (same year, same agency as the scores). The design
    leaves room for a neighborhood basis (census poverty of the school's catchment) once ACS
    data is loaded.
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


def compare(values: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """values: school_id, band, poverty_pct, value (one year, one measure, one window)."""
    rows = []
    for band, g in values.groupby("band"):
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
            dist = (others["poverty_pct"] - r["poverty_pct"]).abs()
            peers = others.loc[dist.nsmallest(k).index]
            q25, med, q75 = peers["value"].quantile([0.25, 0.5, 0.75])
            if r["value"] > q75:
                position = "above peer range"
            elif r["value"] < q25:
                position = "below peer range"
            else:
                position = "within peer range"
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


def build_peer_comparison() -> pd.DataFrame:
    """One-year and three-year-average comparisons (window column)."""
    m = pd.read_parquet(CORE / "school_metric.parquet")
    ctx = school_context()
    pov = poverty_basis()
    scores = m[
        m["measure_id"].isin(MEASURES)
        & (m["student_group"] == "all")
        & m["status"].isin(["reported", "blended"])
    ]
    one = scores.merge(pov, on=["school_id", "sy"], how="left")[
        ["school_id", "sy", "measure_id", "value", "poverty_pct"]
    ]
    frames = []
    for window, vals in [("1 year", one), ("3-year average", pooled(one))]:
        df = _compare_all(vals.merge(ctx, on=["school_id", "sy"], how="left"))
        df["window"] = window
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["basis"] = "school_econ_disadvantaged"
    out["method"] = METHOD
    out["source_id"] = "pde_future_ready + pde_fast_facts"
    return out


def write_peer_comparison(df: pd.DataFrame) -> None:
    DERIVED.mkdir(exist_ok=True)
    df.to_parquet(DERIVED / "peer_comparison.parquet", index=False)
    df.to_csv(DERIVED / "peer_comparison.csv", index=False)
