"""Out-of-school suspensions and serious incidents (School District of Philadelphia), district
schools only. Published together, under one frame ("safe and fair schools"), by design.

Suspensions (school_metric part `sdp_discipline`), 2013-14 on, by gender, race and ethnicity,
and grade: students with 0, 1, 2, 3, or 4+ out-of-school suspensions in the year, the student
base, and the share with none. Student-based, so it shows how concentrated suspensions are.

Serious incidents (table `school_incident`), 2012-13 on: count by incident type as published.
The district's incident categories changed in 2016-17 (about 20 fine-grained types before,
grouped categories after); `incident_type_scheme` records which scheme a row uses, and types
are never mapped across the break. school_metric gets `sdp_serious_incidents_total`.
"""

import io
import re
import zipfile

import pandas as pd

from . import CORE, RAW
from .attendance import _group
from .metrics import write_metric_part
from .scores import parse_value

PERF_DIR = RAW / "sdp_school_performance"
OSS_COLS = {
    "sdp_oss_students": "Total Students (Yearly)",
    "sdp_n_oss_0": "# with Zero OS Suspensions (Yearly)",
    "sdp_n_oss_1": "# with 1 OS Suspension (Yearly)",
    "sdp_n_oss_2": "# with 2 OS Suspensions (Yearly)",
    "sdp_n_oss_3": "# with 3 OS Suspensions (Yearly)",
    "sdp_n_oss_4plus": "# with 4+ OS Suspensions (Yearly)",
    "sdp_pct_oss_0": "% with Zero OS Suspensions (Yearly)",
}


def _read_csv(f) -> pd.DataFrame:
    d = pd.read_csv(f, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    d.columns = [c.strip().lstrip("﻿") for c in d.columns]
    return d


def _suspension_rows(d: pd.DataFrame) -> pd.DataFrame:
    base = pd.DataFrame(
        {
            "sy": d["School Year"].str.strip().str[-4:].astype(int),
            "ulcs": d["ULCS Code"].str.strip(),
            "student_group": [_group(c, g) for c, g in zip(d["Category"], d["Group"], strict=True)],
        }
    )
    frames = []
    for measure, col in OSS_COLS.items():
        parsed = d[col].map(parse_value)
        frames.append(
            base.assign(
                measure_id=measure, value=[p[0] for p in parsed], status=[p[1] for p in parsed]
            )
        )
    return pd.concat(frames, ignore_index=True)


def stage_suspensions() -> pd.DataFrame:
    z = zipfile.ZipFile(PERF_DIR / "Archive_Suspensions.zip")
    parts = [_suspension_rows(_read_csv(z.open("SDP_OSS_School_S.csv")))]
    for path in sorted(PERF_DIR.glob("SDP_OSS_School_S_*.csv")):
        parts.append(_suspension_rows(_read_csv(path)))
    out = pd.concat(parts, ignore_index=True).dropna(subset=["student_group"])
    # if a year appears in both files, the newer file wins
    return out.drop_duplicates(["sy", "ulcs", "student_group", "measure_id"], keep="last")


def _incident_frame(d: pd.DataFrame) -> pd.DataFrame:
    cols = {re.sub(r"[^a-z]", "", c.lower()): c for c in d.columns}
    ulcs = cols.get("ulcsno") or cols.get("ulcscode")
    return pd.DataFrame(
        {
            "sy": d[cols["schoolyear"]].astype(str).str.strip().str[-4:].astype(int),
            "ulcs": d[ulcs].astype(str).str.strip().str.replace(r"\.0$", "", regex=True),
            "incident_type": d[cols["incidenttype"]].astype(str).str.strip(),
            "raw": d[cols.get("incidentcount") or cols.get("ofincidents")],
        }
    )


def stage_incidents() -> pd.DataFrame:
    z = zipfile.ZipFile(PERF_DIR / "Archive_Serious_Incident_Counts.zip")
    parts = []
    for name in z.namelist():
        data = z.read(name)
        if name.lower().endswith(".txt"):
            d = pd.read_csv(io.BytesIO(data), dtype=str, encoding="latin-1")
        else:
            d = pd.read_excel(io.BytesIO(data), engine="calamine", dtype=str)
        parts.append(_incident_frame(d))
    for path in sorted(PERF_DIR.glob("Serious_Incident_Counts_School_*.csv")):
        parts.append(_incident_frame(_read_csv(path)))
    out = pd.concat(parts, ignore_index=True)
    out = out[out["incident_type"].ne("nan") & out["ulcs"].ne("nan")]
    parsed = out["raw"].map(parse_value)
    out["count"] = [p[0] for p in parsed]
    out["status"] = [p[1] for p in parsed]
    out["incident_type_scheme"] = out["sy"].map(
        lambda sy: "2012-13 to 2015-16 types" if sy <= 2016 else "2016-17 on categories"
    )
    return out.drop(columns="raw")


def build_discipline() -> dict:
    reg = pd.read_csv(RAW.parent / "registry" / "school_id_registry.csv", dtype=str)
    to_id = reg.set_index("ulcs")["school_id"]
    s = stage_suspensions()
    s["school_id"] = s["ulcs"].map(to_id)
    inc = stage_incidents()
    inc["school_id"] = inc["ulcs"].map(to_id)
    issues = pd.concat(
        [
            s[s["school_id"].isna()]
            .drop_duplicates(["sy", "ulcs"])[["sy", "ulcs"]]
            .assign(table="suspensions"),
            inc[inc["school_id"].isna()]
            .drop_duplicates(["sy", "ulcs"])[["sy", "ulcs"]]
            .assign(table="incidents"),
        ]
    )
    s = s.dropna(subset=["school_id"])
    inc = inc.dropna(subset=["school_id"])
    s["source_id"] = "sdp_school_performance:suspensions:sy" + s["sy"].astype(str)
    inc["source_id"] = "sdp_school_performance:serious_incidents:sy" + inc["sy"].astype(str)
    school_incident = inc[
        ["school_id", "sy", "incident_type", "incident_type_scheme", "count", "status", "source_id"]
    ].reset_index(drop=True)
    totals = (
        school_incident[school_incident["status"] == "reported"]
        .groupby(["school_id", "sy"], as_index=False)["count"]
        .sum()
        .rename(columns={"count": "value"})
        .assign(
            measure_id="sdp_serious_incidents_total",
            student_group="all",
            status="reported",
            source_id=lambda t: "sdp_school_performance:serious_incidents:sy" + t["sy"].astype(str),
        )
    )
    metric = pd.concat(
        [
            s[["school_id", "sy", "measure_id", "student_group", "value", "status", "source_id"]],
            totals[
                ["school_id", "sy", "measure_id", "student_group", "value", "status", "source_id"]
            ],
        ],
        ignore_index=True,
    )
    return {"metric": metric, "school_incident": school_incident, "issues": issues}


def write_discipline(t: dict) -> pd.DataFrame:
    t["school_incident"].to_parquet(CORE / "school_incident.parquet", index=False)
    t["school_incident"].to_csv(CORE / "school_incident.csv", index=False)
    t["issues"].to_csv(CORE / "discipline_issues.csv", index=False)
    return write_metric_part("sdp_discipline", t["metric"])
