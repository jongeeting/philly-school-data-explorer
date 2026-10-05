"""District attendance detail (School District of Philadelphia), 2013-14 on. District schools only.

Written to school_metric (part `sdp_attendance`):
  sdp_pct_attending_95, sdp_n_attending_95   students attending 95%+ of enrolled days, 2013-14 on
  sdp_pct_attending_90, sdp_n_attending_90   students attending 90%+ of enrolled days, 2020-21 on
  sdp_attendance_students                    students in the attendance base for the group
  sdp_average_daily_attendance               average daily attendance (all students)
Groups: all students, gender, race and ethnicity, and grade levels (`grade_K` ... `grade_12`).
Sources: Archive_Attendance.zip (2013-14 to 2019-20) and the current files (2020-21 on).
"""

import zipfile

import pandas as pd

from . import CORE, RAW
from .metrics import write_metric_part
from .scores import parse_value

PERF_DIR = RAW / "sdp_school_performance"
GROUPS = {
    "all students": "all",
    "female": "female",
    "male": "male",
    "non-binary": "non_binary",
    "not listed": "not_listed",
    "american indian/alaskan native": "american_indian",
    "asian": "asian",
    "black/african american": "black",
    "hispanic/latino": "hispanic",
    "multi racial/other": "multiracial",
    "native hawaiian/pacific islander": "pacific_islander",
    "white": "white",
    "unknown": "unknown",
}


def _group(category: str, group: str) -> str | None:
    if str(category).strip().lower() == "grade level":
        g = str(group).strip()
        return "grade_K" if g in {"00", "0", "K"} else f"grade_{int(g):02d}"
    return GROUPS.get(str(group).strip().lower())


def _sy(label: str) -> int:
    return int(str(label).strip()[-4:])


def _threshold_rows(d: pd.DataFrame, level: int) -> pd.DataFrame:
    d.columns = [c.strip().lstrip("﻿") for c in d.columns]
    base = pd.DataFrame(
        {
            "sy": d["School Year"].map(_sy),
            "ulcs": d["ULCS Code"].str.strip(),
            "student_group": [_group(c, g) for c, g in zip(d["Category"], d["Group"], strict=True)],
        }
    )
    cols = {
        f"sdp_pct_attending_{level}": f"% with {level}%+ Attendance (Yearly)",
        f"sdp_n_attending_{level}": f"# with {level}%+ Attendance (Yearly)",
        "sdp_attendance_students": "Total Students (Yearly)",
    }
    frames = []
    for measure, col in cols.items():
        parsed = d[col].map(parse_value)
        frames.append(
            base.assign(
                measure_id=measure, value=[p[0] for p in parsed], status=[p[1] for p in parsed]
            )
        )
    return pd.concat(frames, ignore_index=True)


def _ada_rows(d: pd.DataFrame) -> pd.DataFrame:
    d.columns = [c.strip().lstrip("﻿") for c in d.columns]
    col = next(c for c in d.columns if c.startswith("Average Daily Attendance"))
    parsed = d[col].map(parse_value)
    return pd.DataFrame(
        {
            "sy": d["School Year"].map(_sy),
            "ulcs": d["ULCS Code"].str.strip(),
            "student_group": "all",
            "measure_id": "sdp_average_daily_attendance",
            "value": [p[0] for p in parsed],
            "status": [p[1] for p in parsed],
        }
    )


def stage_attendance() -> pd.DataFrame:
    z = zipfile.ZipFile(PERF_DIR / "Archive_Attendance.zip")
    read = lambda f: pd.read_csv(f, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    parts = [
        _threshold_rows(read(z.open("SDP_95_Attendance_School_S.csv")), 95),
        _ada_rows(read(z.open("Student_ADA_Yearly.csv"))),
    ]
    for path in sorted(PERF_DIR.glob("Student_Attendance_9[05]_School_*.csv")):
        level = 95 if "_95_" in path.name else 90
        parts.append(_threshold_rows(read(path), level))
    for path in sorted(PERF_DIR.glob("Student_ADA_Yearly_School_*.csv")):
        parts.append(_ada_rows(read(path)))
    out = pd.concat(parts, ignore_index=True).dropna(subset=["student_group"])
    # the attendance base appears in both the 90% and 95% files: keep one
    return out.drop_duplicates(["sy", "ulcs", "student_group", "measure_id"])


def build_attendance() -> dict:
    d = stage_attendance()
    reg = pd.read_csv(RAW.parent / "registry" / "school_id_registry.csv", dtype=str)
    d["school_id"] = d["ulcs"].map(reg.set_index("ulcs")["school_id"])
    issues = d[d["school_id"].isna()].drop_duplicates(["sy", "ulcs"])[["sy", "ulcs"]]
    d = d.dropna(subset=["school_id"])
    d["source_id"] = "sdp_school_performance:attendance:sy" + d["sy"].astype(str)
    metric = d[["school_id", "sy", "measure_id", "student_group", "value", "status", "source_id"]]
    return {"metric": metric.reset_index(drop=True), "issues": issues}


def write_attendance(t: dict) -> pd.DataFrame:
    t["issues"].to_csv(CORE / "attendance_issues.csv", index=False)
    return write_metric_part("sdp_attendance", t["metric"])
