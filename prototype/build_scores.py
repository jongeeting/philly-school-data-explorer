"""Build one tidy table of Future Ready PA Index school scores, 2017-18 to 2024-25.

Output: data/scores_long.parquet with columns
  year (spring year, e.g. 2025 = SY 2024-25), aun, schl, name, measure, group, value, flag
Only Pennsylvania-wide; Philadelphia filtering happens downstream via the crosswalk.
"""
import re
import pandas as pd
from pathlib import Path

RAW = Path(__file__).parent / "raw"
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

# measure key -> (regex for old long-format names, prefix for new wide-format columns)
MEASURES = {
    "prof_math": (r"^Percent Proficient or Advanced Mathematics/Algebra 1", "PercentProficientorAdvancedonMathematicsAlgebra1_"),
    "prof_ela": (r"^Percent Proficient or Advanced ELA/Literature", "PercentProficientorAdvancedonELALiterature_"),
    "prof_sci": (r"^Percent Proficient or Advanced Science/Biology", "PercentProficientorAdvancedonScienceBiology_"),
    "growth_math": (r"^Meeting Annual Academic Growth Expectations Mathematics/Algebra 1", "MeetingAnnualAcademicGrowthExpectations_PVAASMathematicsAlgebra1_"),
    "growth_ela": (r"^Meeting Annual Academic Growth Expectations ELA/Literature", "MeetingAnnualAcademicGrowthExpectations_PVAASELALiterature_"),
    "growth_sci": (r"^Meeting Annual Academic Growth Expectations Science/Biology", "MeetingAnnualAcademicGrowthExpectations_PVAASScienceBiology_"),
    "attendance": (r"^Percent Regular Attendance", "PercentPersistentAttendance_"),
    "chronic_absent": (r"^Percent Chronic Absenteeism", "PercentChronicAbsenteeism_"),
    "grad4": (r"^Percent Graduation 4-Year Cohort", "PercentGraduation4YearCohort_"),
    "participation_math": (r"^Percent Mathematics/Algebra I Test Participation", "PercentMathematicsAlgebraITestParticipation_"),
    "participation_ela": (r"^Percent ELA/Literature Test Participation", "PercentELALiteratureTestParticipation_"),
}

# old-format group label -> canonical; new-format suffix -> canonical
OLD_GROUPS = {
    "all student": "all", "all students": "all", "all student group": "all",
    "economically disadvantaged": "econ_dis", "black": "black", "hispanic": "hispanic",
    "white": "white", "asian": "asian", "english learner": "el", "english learners": "el",
    "students with disabilities": "swd", "student with disabilities": "swd",
}
NEW_GROUPS = {
    "AllStudent": "all", "AllStudentGroup": "all", "EconomicallyDisadvantaged": "econ_dis",
    "Black": "black", "Hispanic": "hispanic", "White": "white", "Asian": "asian",
    "EnglishLearner": "el", "StudentswithDisabilities": "swd",
}


def parse_value(v):
    """Return (numeric value or None, flag string or None)."""
    s = str(v).strip()
    if s in ("", "nan", "None"):
        return None, None
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)%?", s)
    if m:
        return float(m.group(1)), None
    return None, s  # e.g. 'IS', 'Insufficient Sample', 'Not Applicable'


def old_year(path, year):
    d = pd.read_parquet(path)
    d["dataelement"] = d["dataelement"].str.replace(r"\s+", " ", regex=True).str.strip()
    rows = []
    for key, (rx, _) in MEASURES.items():
        sub = d[d["dataelement"].str.contains(rx, regex=True)]
        g = sub["dataelement"].str.extract(r"\(([^)]*)\)\s*$")[0].str.strip().str.lower().map(OLD_GROUPS)
        sub = sub.assign(group=g).dropna(subset=["group"])
        rows.append(pd.DataFrame({"year": year, "aun": sub["aun"].astype(str), "schl": sub["schl"].astype(str),
                                  "name": sub["name"], "measure": key, "group": sub["group"],
                                  "raw": sub["displayvalue"]}))
    return pd.concat(rows)


def new_year(path, year):
    w = pd.read_parquet(path)
    rows = []
    for col in w.columns:
        for key, (_, prefix) in MEASURES.items():
            if col.startswith(prefix):
                grp = NEW_GROUPS.get(col[len(prefix):])
                if grp:
                    rows.append(pd.DataFrame({"year": year, "aun": w["AUN"].astype(str), "schl": w["Schl"].astype(str),
                                              "name": w["Name"], "measure": key, "group": grp, "raw": w[col]}))
    return pd.concat(rows)


def load_new_raw(y):
    """Read a wide new-format workbook into one row per school, tolerant of duplicate rows."""
    x = pd.ExcelFile(RAW / f"Datafile_{y}.xlsx", engine="calamine")
    longs = []
    for s in x.sheet_names:
        d = x.parse(s).astype(str)
        d.columns = [str(c).strip() for c in d.columns]
        for k in ("AUN", "Schl"):  # sheets disagree on int vs float ids ("7744" vs "7744.0")
            d[k] = d[k].str.replace(r"\.0$", "", regex=True)
        d = d[d["AUN"] != "nan"]
        longs.append(d.melt(id_vars=["AUN", "Schl", "Name"]))
    lg = pd.concat(longs).drop_duplicates(subset=["AUN", "Schl", "variable"])
    return lg.pivot(index=["AUN", "Schl", "Name"], columns="variable", values="value").reset_index()


def main():
    parts = []
    for y, sy in [("20172018", 2018), ("20182019", 2019), ("20192020", 2020), ("20202021", 2021)]:
        parts.append(old_year(RAW / f"old_{y}.parquet", sy))
    for y, sy in [("20212022", 2022), ("20222023", 2023), ("20232024", 2024), ("20242025", 2025)]:
        p = RAW / f"new_{y}.parquet"
        if not p.exists():
            load_new_raw(y).to_parquet(p)
        parts.append(new_year(p, sy))
    df = pd.concat(parts, ignore_index=True)
    parsed = df["raw"].map(parse_value)
    df["value"] = [v for v, _ in parsed]
    df["flag"] = [f for _, f in parsed]
    df["schl"] = df["schl"].str.replace(r"\.0$", "", regex=True)
    df["aun"] = df["aun"].str.replace(r"\.0$", "", regex=True)
    df = df.drop(columns="raw").drop_duplicates(subset=["year", "aun", "schl", "measure", "group"])
    # No state tests in spring 2020: the 2019-20 file repeats 2018-19 scores. Drop them.
    test = df["measure"].str.startswith(("prof_", "growth_", "participation_"))
    df = df[~(test & (df["year"] == 2020))]
    df.to_parquet(OUT / "scores_long.parquet")
    print(df.groupby(["year", "measure"])["value"].count().unstack().fillna(0).astype(int).to_string())


if __name__ == "__main__":
    main()
