"""Can Philadelphia's school-level state scores support a fair composite?

Three tests, all-students group, District + Charter brick-and-mortar schools with a unique state key:
  1. Coverage: how many schools have each measure, by year and sector.
  2. Poverty link: correlation of each measure with % economically disadvantaged.
  3. Stability: school-level correlation of each measure with itself the next tested year,
     and how year-to-year swings scale with school size.
Writes data/analysis_panel.parquet and prints results.
"""
import numpy as np
import pandas as pd
from pathlib import Path

D = Path(__file__).parent / "data"
MEAS = ["prof_ela", "prof_math", "prof_sci", "growth_ela", "growth_math", "attendance", "grad4"]

cw = pd.read_csv(D / "crosswalk.csv", dtype=str)
cw = cw[(cw.state_key_shared == "False") & cw.governance.isin(["District", "Charter"])]
cw = cw.drop_duplicates("school_key")
sc = pd.read_parquet(D / "scores_long.parquet")
sc["school_key"] = sc.aun + "-" + sc.schl
sc = sc[sc.school_key.isin(cw.school_key) & (sc.group == "all") & sc.measure.isin(MEAS)]
panel = sc.pivot_table(index=["school_key", "year"], columns="measure", values="value").reset_index()

ff = pd.read_parquet(D / "school_facts.parquet")[["school_key", "year", "enrollment", "pct_econ_dis", "pct_black", "pct_hispanic", "pct_el", "pct_sped"]]
ff.loc[ff.pct_econ_dis <= 0.5, "pct_econ_dis"] = np.nan  # zeros are missing, not affluent
# fill years without a facts file (2018, 2020) from the nearest year for the same school
ff = ff.dropna(subset=["school_key"]).sort_values(["school_key", "year", "enrollment"]).drop_duplicates(["school_key", "year"], keep="last")
allyears = pd.MultiIndex.from_product([ff.school_key.unique(), range(2018, 2026)], names=["school_key", "year"])
ff = ff.set_index(["school_key", "year"]).reindex(allyears).groupby(level=0).transform(lambda s: s.bfill().ffill()).reset_index()
panel = panel.merge(ff, on=["school_key", "year"], how="left").merge(
    cw[["school_key", "ulcs", "name", "governance", "level", "admission"]], on="school_key")
panel.to_parquet(D / "analysis_panel.parquet")

print("== 1. Coverage: schools with a value (all students)")
print(panel.groupby(["year", "governance"])[MEAS].count().to_string())

print("\n== 2. Correlation with % economically disadvantaged (Pearson r), by year")
rows = []
for y, g in panel.groupby("year"):
    rows.append({"year": y, **{m: g[m].corr(g.pct_econ_dis) for m in MEAS}, "n": g.prof_ela.notna().sum()})
print(pd.DataFrame(rows).set_index("year").round(2).to_string())

# selective admission schools sit at low poverty AND high scores; check without them
nonsel = panel[~panel.admission.fillna("").str.contains("Criteria|Citywide", case=False)]
print("\n   2025, excluding criteria/citywide-admission schools:")
g = nonsel[nonsel.year == 2025]
print("   ", {m: round(g[m].corr(g.pct_econ_dis), 2) for m in MEAS})
print("   share of variance explained by poverty alone (r^2), 2025 all schools:",
      {m: round(panel[panel.year == 2025][m].corr(panel[panel.year == 2025].pct_econ_dis) ** 2, 2) for m in MEAS})

print("\n== 3. Stability: correlation of a school's value with its next tested year")
pairs = [(2018, 2019), (2022, 2023), (2023, 2024), (2024, 2025)]
rows = []
for a, b in pairs:
    A = panel[panel.year == a].set_index("school_key")
    B = panel[panel.year == b].set_index("school_key")
    j = A.join(B, lsuffix="_a", rsuffix="_b", how="inner")
    rows.append({"pair": f"{a}->{b}", **{m: j[f"{m}_a"].corr(j[f"{m}_b"]) for m in MEAS}})
stab = pd.DataFrame(rows).set_index("pair")
print(stab.round(2).to_string())

print("\n   Median absolute year-to-year change (points), 2022->2025 pairs, by school size")
ch = []
for a, b in pairs[1:]:
    A = panel[panel.year == a].set_index("school_key")
    B = panel[panel.year == b].set_index("school_key")
    j = A.join(B, lsuffix="_a", rsuffix="_b", how="inner")
    for m in ["prof_ela", "prof_math", "growth_ela", "growth_math", "attendance"]:
        ch.append(pd.DataFrame({"measure": m, "enroll": j.enrollment_b, "absdiff": (j[f"{m}_b"] - j[f"{m}_a"]).abs()}))
ch = pd.concat(ch).dropna()
ch["size"] = pd.cut(ch.enroll, [0, 300, 500, 800, 5000], labels=["<300", "300-499", "500-799", "800+"])
print(ch.pivot_table(index="size", columns="measure", values="absdiff", aggfunc="median", observed=True).round(1).to_string())

print("\n== 4. Beating the odds: does 'over/under expectation' persist?")
res = {}
for m in ["prof_ela", "prof_math"]:
    r = {}
    for y in [2022, 2023, 2024, 2025]:
        g = panel[(panel.year == y)].dropna(subset=[m, "pct_econ_dis"])
        X = np.c_[np.ones(len(g)), g.pct_econ_dis, g.pct_el.fillna(0), g.pct_sped.fillna(0)]
        beta, *_ = np.linalg.lstsq(X, g[m].values, rcond=None)
        r[y] = pd.Series(g[m].values - X @ beta, index=g.school_key)
    res[m] = r
    cors = [res[m][a].corr(res[m][b]) for a, b in [(2022, 2023), (2023, 2024), (2024, 2025)]]
    print(f"   {m}: residual year-to-year r = {[round(c, 2) for c in cors]}")
avg = pd.concat([res["prof_ela"][y] for y in [2023, 2024, 2025]], axis=1).mean(axis=1)
avg.name = "ela_resid_3yr"
avg.to_frame().to_csv(D / "beating_odds_ela.csv")
