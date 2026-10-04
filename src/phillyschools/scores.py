"""Future Ready PA Index (PDE): test scores, growth, attendance, graduation, 2017-18 on.

Cross-sector (district and charter) on one state definition. Written to school_metric
(part `future_ready`) for Philadelphia schools only: rows whose state key (AUN-school number)
is in our identity crosswalk.

Formats: 2017-18 to 2020-21 are long (DataElement with the group in parentheses,
DisplayValue); 2021-22 on are wide (<Measure>_<Group> columns over three sheets).

Status rules (design rule 5):
  IS / Insufficient Sample / Insufficient Testers   -> suppressed
  Suppress:Data Does Not Apply / Not Applicable     -> not_applicable
  2019-20 test measures (no spring 2020 tests; the file repeats 2018-19) -> carried_forward
  state key shared with placeholder codes 0/9999    -> not_separately_measurable (value withheld)
  state key shared with a host school               -> host gets the value as `blended`; the
                                                       others not_separately_measurable
"""

import re

import pandas as pd

from . import CORE, RAW
from .metrics import write_metric_part

FR_DIR = RAW / "pde_future_ready"

NEW_MEASURES = {
    "PercentProficientorAdvancedonELALiterature": "pct_proficient_ela",
    "PercentProficientorAdvancedonMathematicsAlgebra1": "pct_proficient_math",
    "PercentProficientorAdvancedonScienceBiology": "pct_proficient_science",
    "MeetingAnnualAcademicGrowthExpectations_PVAASELALiterature": "growth_score_ela",
    "MeetingAnnualAcademicGrowthExpectations_PVAASMathematicsAlgebra1": "growth_score_math",
    "MeetingAnnualAcademicGrowthExpectations_PVAASScienceBiology": "growth_score_science",
    "PercentELALiteratureTestParticipation": "participation_ela",
    "PercentMathematicsAlgebraITestParticipation": "participation_math",
    "PercentScienceBiologyTestParticipation": "participation_science",
    "PercentGrade3Reading": "pct_grade3_reading_proficient",
    "PercentGrade7Mathematics": "pct_grade7_math_proficient",
    "PercentPersistentAttendance": "pct_persistent_attendance",
    "PercentChronicAbsenteeism": "pct_chronic_absenteeism",
    "PercentGraduation4YearCohort": "grad_rate_4yr",
    "PercentGraduation5YearCohort": "grad_rate_5yr",
}
OLD_MEASURES = {
    "Percent Proficient or Advanced ELA/Literature": "pct_proficient_ela",
    "Percent Proficient or Advanced Mathematics/Algebra 1": "pct_proficient_math",
    "Percent Proficient or Advanced Science/Biology": "pct_proficient_science",
    "Meeting Annual Academic Growth Expectations ELA/Literature": "growth_score_ela",
    "Meeting Annual Academic Growth Expectations Mathematics/Algebra 1": "growth_score_math",
    "Meeting Annual Academic Growth Expectations Science/Biology": "growth_score_science",
    "Percent ELA/Literature Test Participation": "participation_ela",
    "Percent Mathematics/Algebra I Test Participation": "participation_math",
    "Percent Science/Biology Test Participation": "participation_science",
    "Percent Grade 3 Reading": "pct_grade3_reading_proficient",
    "Percent Grade 7 Mathematics": "pct_grade7_math_proficient",
    "Percent Regular Attendance": "pct_regular_attendance",
    "Percent Graduation 4-Year Cohort": "grad_rate_4yr",
    "Percent Graduation 5-Year Cohort": "grad_rate_5yr",
}
TEST_MEASURES = {
    "pct_proficient_ela",
    "pct_proficient_math",
    "pct_proficient_science",
    "growth_score_ela",
    "growth_score_math",
    "growth_score_science",
    "participation_ela",
    "participation_math",
    "participation_science",
    "pct_grade3_reading_proficient",
    "pct_grade7_math_proficient",
}
SCIENCE_MEASURES = {"pct_proficient_science", "growth_score_science", "participation_science"}
NEW_GROUPS = {
    "AllStudent": "all",
    "AllStudentGroup": "all",
    "EconomicallyDisadvantaged": "econ_disadvantaged",
    "EnglishLearner": "english_learner",
    "StudentswithDisabilities": "students_with_disabilities",
    "Black": "black",
    "Hispanic": "hispanic",
    "White": "white",
    "Asian": "asian",
    "AmericanIndianAlaskaNative": "american_indian",
    "HawaiianPacificIslander": "pacific_islander",
    "2orMoreRaces": "multiracial",
    "CombinedEthnicity": "combined_ethnicity",
}
OLD_GROUPS = {
    "all student": "all",
    "all students": "all",
    "all student group": "all",
    "economically disadvantaged": "econ_disadvantaged",
    "ecomically disadvantaged": "econ_disadvantaged",
    "english learner": "english_learner",
    "english learners": "english_learner",
    "students with disabilities": "students_with_disabilities",
    "student with disabilities": "students_with_disabilities",
    "black": "black",
    "hispanic": "hispanic",
    "white": "white",
    "asian": "asian",
    "american indian/alaska native": "american_indian",
    "hawaiian/pacific islander": "pacific_islander",
    "2 or more races": "multiracial",
    "combined ethnicity": "combined_ethnicity",
}
SUPPRESSED = {"is", "insufficient sample", "insufficient testers"}
NOT_APPLICABLE = {"suppress:data does not apply", "not applicable", "na", "n/a"}


def parse_value(raw) -> tuple[float | None, str]:
    s = "" if raw is None else str(raw).strip()
    if s in ("", "nan", "None"):
        return None, "not_reported"
    m = re.fullmatch(r"(-?\d*\.?\d+)%?", s)
    if m:
        return float(m.group(1)), "reported"
    low = s.lower()
    if low in SUPPRESSED:
        return None, "suppressed"
    if low in NOT_APPLICABLE:
        return None, "not_applicable"
    if low.startswith("waiv"):
        return None, "waived"
    return None, "not_reported"


def _clean_id(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def read_old(path, sy: int) -> pd.DataFrame:
    book = pd.ExcelFile(path, engine="calamine")
    d = pd.concat([book.parse(s, dtype=str) for s in book.sheet_names], ignore_index=True)
    d.columns = [c.lower() for c in d.columns]
    element = d["dataelement"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    stem = element.str.replace(r"\s*\([^)]*\)\s*$", "", regex=True).str.strip()
    group = element.str.extract(r"\(([^)]*)\)\s*$")[0].str.strip().str.lower()
    out = pd.DataFrame(
        {
            "sy": sy,
            "aun": _clean_id(d["aun"]),
            "schl": _clean_id(d["schl"]),
            "name": d["name"],
            "measure_id": stem.map(OLD_MEASURES),
            "student_group": group.map(OLD_GROUPS),
            "raw": d["displayvalue"],
        }
    )
    return out.dropna(subset=["measure_id", "student_group"])


def read_new(path, sy: int) -> pd.DataFrame:
    book = pd.ExcelFile(path, engine="calamine")
    frames = []
    for sheet in book.sheet_names:
        d = book.parse(sheet, dtype=str)
        d.columns = [str(c).strip() for c in d.columns]
        for col in d.columns:
            if "_" not in col:
                continue
            prefix, suffix = col.rsplit("_", 1)
            measure, group = NEW_MEASURES.get(prefix), NEW_GROUPS.get(suffix)
            if not measure or not group:
                continue
            frames.append(
                pd.DataFrame(
                    {
                        "sy": sy,
                        "aun": _clean_id(d["AUN"]),
                        "schl": _clean_id(d["Schl"]),
                        "name": d["Name"],
                        "measure_id": measure,
                        "student_group": group,
                        "raw": d[col],
                    }
                )
            )
    return pd.concat(frames, ignore_index=True)


def stage_future_ready() -> pd.DataFrame:
    frames = []
    for path in sorted(FR_DIR.glob("Datafile_*.xlsx")):
        sy = int(re.search(r"_(\d{4})(\d{4})", path.name).group(2))
        frames.append(read_old(path, sy) if sy <= 2021 else read_new(path, sy))
    d = pd.concat(frames, ignore_index=True)
    d = d[d["aun"].ne("nan") & d["schl"].ne("nan")]
    d["state_key"] = d["aun"] + "-" + d["schl"]
    parsed = d["raw"].map(parse_value)
    d["value"] = [p[0] for p in parsed]
    d["status"] = [p[1] for p in parsed]
    # "AllStudent" and "AllStudentGroup" both mean all students: keep the row with a value.
    d = d.sort_values("value", na_position="last").drop_duplicates(
        ["sy", "state_key", "measure_id", "student_group"]
    )
    return d


def _tokens(name) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", str(name).lower())) - {"school", "the", "high", "charter"}


def key_to_schools() -> pd.DataFrame:
    """(state_key, sy) -> school_id rows from the identity crosswalk."""
    xw = pd.read_parquet(CORE / "school_id_xwalk.parquet")
    xw = xw[xw["id_type"] == "state_key"]
    rows = []
    for r in xw.itertuples():
        last = int(r.valid_to_sy) if pd.notna(r.valid_to_sy) else 2100
        for sy in range(int(r.valid_from_sy), last + 1):
            rows.append((r.id_value, sy, r.school_id))
    return pd.DataFrame(rows, columns=["state_key", "sy", "school_id"])


def assign_schools(fr: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = key_to_schools()
    names = pd.read_parquet(CORE / "school_year_attr.parquet")[
        ["school_id", "sy", "name", "category"]
    ]
    # Fall back to other years only when the key has only ever meant one school.
    ever = keys.groupby("state_key")["school_id"].nunique()
    unique_any = keys[keys["state_key"].isin(ever[ever == 1].index)].drop_duplicates("state_key")
    m = fr.merge(keys, on=["state_key", "sy"], how="left")
    miss = m["school_id"].isna()
    fb = m.loc[miss, ["state_key"]].merge(
        unique_any[["state_key", "school_id"]], on="state_key", how="left"
    )
    m.loc[miss, "school_id"] = fb["school_id"].to_numpy()
    m = m.dropna(subset=["school_id"])  # not a Philadelphia school in our lists

    shared = m.groupby(["sy", "state_key"])["school_id"].nunique()
    shared = shared[shared > 1].reset_index()[["sy", "state_key"]]
    issues = []
    if not shared.empty:
        flagged = m.merge(shared, on=["sy", "state_key"], how="left", indicator=True)
        sm = flagged[flagged["_merge"] == "both"].drop(columns="_merge")
        rest = flagged[flagged["_merge"] == "left_only"].drop(columns="_merge")
        resolved = []
        for (sy, key), g in sm.groupby(["sy", "state_key"]):
            placeholder = key.split("-")[-1] in {"0", "9999"}
            host = None
            if not placeholder:
                cands = names[(names["sy"] == sy) & names["school_id"].isin(g["school_id"])]
                # A regular school sharing its code with alternative programs (an EOP evening
                # program, a continuation academy) is the host.
                regular = cands[~cands["category"].fillna("").str.lower().str.startswith("altern")]
                if len(regular) == 1:
                    host = regular["school_id"].iloc[0]
                fr_name = _tokens(g["name"].iloc[0])
                scores = {r.school_id: len(fr_name & _tokens(r.name)) for r in cands.itertuples()}
                best = sorted(scores.items(), key=lambda kv: -kv[1])
                if host is None and best and (len(best) == 1 or best[0][1] > best[1][1]):
                    host = best[0][0]
            g = g.copy()
            g.loc[g["school_id"] != host, ["value", "status"]] = [None, "not_separately_measurable"]
            g.loc[(g["school_id"] == host) & (g["status"] == "reported"), "status"] = "blended"
            resolved.append(g)
            issues.append(
                {
                    "type": "state key shared",
                    "id": key,
                    "sy": sy,
                    "detail": f"{g['school_id'].nunique()} schools; host {host or 'none'}",
                }
            )
        m = pd.concat([rest] + resolved, ignore_index=True)
    return m, pd.DataFrame(issues, columns=["type", "id", "sy", "detail"])


def build_scores() -> dict:
    fr = stage_future_ready()
    m, issues = assign_schools(fr)
    carried = (m["sy"] == 2020) & m["measure_id"].isin(TEST_MEASURES) & m["value"].notna()
    m.loc[carried, "status"] = "carried_forward"
    # Science results were waived statewide in 2024-25; the file leaves them blank.
    waived = (
        (m["sy"] == 2025) & m["measure_id"].isin(SCIENCE_MEASURES) & (m["status"] == "not_reported")
    )
    m.loc[waived, "status"] = "waived"
    m["source_id"] = "pde_future_ready:sy" + m["sy"].astype(str)
    out = m[["school_id", "sy", "measure_id", "student_group", "value", "status", "source_id"]]
    out = out.drop_duplicates(["school_id", "sy", "measure_id", "student_group"])
    return {"metric": out.reset_index(drop=True), "issues": issues}


def write_scores(t: dict) -> pd.DataFrame:
    t["issues"].to_csv(CORE / "future_ready_issues.csv", index=False)
    return write_metric_part("future_ready", t["metric"])
