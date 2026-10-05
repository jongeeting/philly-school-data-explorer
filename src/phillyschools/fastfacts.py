"""PDE School Fast Facts: enrollment, student-group shares, and school attributes, 2017-18 on.

State definitions, district and charter alike. Numbers go to school_metric (part
`fast_facts`): `state_enrollment` (group all) and `state_pct_of_enrollment` by student group.
Text attributes (Title I, ESSA designation, grades offered, CTE programs) go to
`school_state_attr` (school x sy). Shared state codes follow the Future Ready rule (host
school gets the value as `blended`; other programs are `not_separately_measurable`).

Formats: 2017-18 to 2020-21 long (DataElement/DisplayValue); 2021-22 on wide.
"""

import re

import pandas as pd

from . import CORE, RAW
from .metrics import write_metric_part
from .scores import assign_schools, parse_value

FF_DIR = RAW / "pde_fast_facts"

# element (long format, trimmed) or column (wide format) -> (measure_id, student_group)
NUMERIC = {
    ("School Enrollment", "Enrollment"): ("state_enrollment", "all"),
    ("Economically Disadvantaged", "EconomicallyDisadvantaged"): (
        "state_pct_of_enrollment",
        "econ_disadvantaged",
    ),
    ("English Learner", "EnglishLearner"): ("state_pct_of_enrollment", "english_learner"),
    ("Special Education", "SpecialEducation"): ("state_pct_of_enrollment", "special_education"),
    ("Percent of Gifted Students", "PercentGiftedStudents"): ("state_pct_of_enrollment", "gifted"),
    ("Homeless", "Homeless"): ("state_pct_of_enrollment", "homeless"),
    ("Foster Care", "FosterCare"): ("state_pct_of_enrollment", "foster_care"),
    ("Military Connected", "MilitaryConnected"): ("state_pct_of_enrollment", "military_connected"),
    ("Female (School)", "Female"): ("state_pct_of_enrollment", "female"),
    ("Male (School)", "Male"): ("state_pct_of_enrollment", "male"),
    ("American Indian/Alaskan Native", "AmericanIndian_AlaskanNative"): (
        "state_pct_of_enrollment",
        "american_indian",
    ),
    ("Asian", "Asian"): ("state_pct_of_enrollment", "asian"),
    ("Native Hawaiian or other Pacific Islander", "NativeHawaiianOtherPacificIslander"): (
        "state_pct_of_enrollment",
        "pacific_islander",
    ),
    ("Black/African American", "Black"): ("state_pct_of_enrollment", "black"),
    ("Hispanic", "Hispanic"): ("state_pct_of_enrollment", "hispanic"),
    ("White", "White"): ("state_pct_of_enrollment", "white"),
    ("2 or More Races", "TwoOrMoreRaces"): ("state_pct_of_enrollment", "multiracial"),
}
TEXT = {
    ("Title I School", "TitleISchool"): "title_i",
    ("ESSA School Designation", "ESSASchoolDesignation"): "essa_designation",
    ("Grades Offered", "GradesOffered"): "grades_offered",
    ("Career and Technical Programs", "CareerTechnicalPrograms"): "career_technical_programs",
}


def _clean(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def read_year(path) -> pd.DataFrame:
    sy = int(re.search(r"_(\d{4})(\d{4})", path.name).group(2))
    book = pd.ExcelFile(path, engine="calamine")
    d = book.parse(book.sheet_names[0], dtype=str)
    lower = {c.lower(): c for c in d.columns}
    if "dataelement" in lower:
        el = d[lower["dataelement"]].fillna("").str.strip()
        lookup = {k[0]: k for k in list(NUMERIC) + list(TEXT)}
        key = el.map(lookup)
        out = pd.DataFrame(
            {
                "sy": sy,
                "aun": _clean(d[lower["aun"]]),
                "schl": _clean(d[lower["schl"]]),
                "name": d[lower.get("name", lower.get("schoolname"))],
                "key": key,
                "raw": d[lower["displayvalue"]],
            }
        ).dropna(subset=["key"])
    else:
        frames = []
        for key in list(NUMERIC) + list(TEXT):
            if key[1] in d:
                frames.append(
                    pd.DataFrame(
                        {
                            "sy": sy,
                            "aun": _clean(d["AUN"]),
                            "schl": _clean(d["Schl"]),
                            "name": d["Name"],
                            "key": [key] * len(d),
                            "raw": d[key[1]],
                        }
                    )
                )
        out = pd.concat(frames, ignore_index=True)
    out["state_key"] = out["aun"] + "-" + out["schl"]
    return out


def build_fast_facts() -> dict:
    raw = pd.concat(
        [read_year(p) for p in sorted(FF_DIR.glob("SchoolFastFacts_*.xlsx"))], ignore_index=True
    )
    is_num = raw["key"].isin(list(NUMERIC))
    num = raw[is_num].copy()
    num["measure_id"] = num["key"].map(lambda k: NUMERIC[k][0])
    num["student_group"] = num["key"].map(lambda k: NUMERIC[k][1])
    parsed = num["raw"].map(parse_value)
    num["value"] = [p[0] for p in parsed]
    num["status"] = [p[1] for p in parsed]
    num = num.drop_duplicates(["sy", "state_key", "measure_id", "student_group"])
    m, issues = assign_schools(num)
    m["source_id"] = "pde_fast_facts:sy" + m["sy"].astype(str)
    metric = m[["school_id", "sy", "measure_id", "student_group", "value", "status", "source_id"]]
    metric = metric.drop_duplicates(["school_id", "sy", "measure_id", "student_group"])

    txt = raw[~is_num].copy()
    txt["field"] = txt["key"].map(TEXT)
    txt["value"] = txt["raw"].where(txt["raw"].notna() & txt["raw"].astype(str).str.strip().ne(""))
    txt["status"] = txt["value"].notna().map({True: "reported", False: "not_reported"})
    tm, _ = assign_schools(txt.drop_duplicates(["sy", "state_key", "field"]))
    tm = tm[tm["status"].isin(["reported", "blended"])]
    attr = tm.pivot_table(
        index=["school_id", "sy"], columns="field", values="value", aggfunc="first"
    ).reset_index()
    attr.columns.name = None
    if "title_i" in attr:
        attr["title_i"] = attr["title_i"].replace({"Y": "Yes", "N": "No"})
    attr["source_id"] = "pde_fast_facts:sy" + attr["sy"].astype(str)
    return {"metric": metric.reset_index(drop=True), "attr": attr, "issues": issues}


def write_fast_facts(t: dict) -> pd.DataFrame:
    t["attr"].to_parquet(CORE / "school_state_attr.parquet", index=False)
    t["attr"].to_csv(CORE / "school_state_attr.csv", index=False)
    return write_metric_part("fast_facts", t["metric"])
