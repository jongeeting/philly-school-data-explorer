"""PDE school-level files: per-pupil expenditures (ESSA), public school enrollment (all sectors,
including charters), low-income enrollment, and English learner counts by LEA and school."""

from datetime import UTC, datetime

from .discover import file_row, read_files_catalog, write_files_catalog

PA = "https://www.pa.gov/content/dam/copapwp-pagov/en/education/documents/"
PPE_YEARS = [f"{y}-{y + 1}" for y in range(2018, 2024)]
FILES = [
    *[
        (
            "pde_essa_ppe",
            f"{PA}schools/essa/{y}%20per%20pupil%20expenditures.xlsx",
            f"{y} per pupil expenditures.xlsx",
        )
        for y in PPE_YEARS
    ],
    (
        "pde_enrollment",
        f"{PA}data-and-reporting/enrollment/public-school/enrollment%20public%20school%201617%20through%202526.xlsx",
        "enrollment public school 1617 through 2526.xlsx",
    ),
    (
        "pde_enrollment",
        f"{PA}data-and-reporting/loan-cancellation/public/low%20income%20enrollments%20public%20school%201617%20through%202526.xlsx",
        "low income enrollments public school 1617 through 2526.xlsx",
    ),
    (
        "pde_enrollment",
        f"{PA}data-and-reporting/english-learners/2024-2025%20el%20student%20counts%20by%20lea%20and%20school.xlsx",
        "2024-2025 el student counts by lea and school.xlsx",
    ),
    (
        "pde_enrollment",
        f"{PA}data-and-reporting/english-learners/2025-2026%20el%20student%20counts%20by%20lea%20and%20school.xlsx",
        "2025-2026 el student counts by lea and school.xlsx",
    ),
]


STAFF = PA + "data-and-reporting/professional-and-support-personnel/"


def _staff_files() -> list[tuple[str, str, str]]:
    """Aggregate staff files only; the individual staff reports are deliberately not fetched."""
    out = []
    summary_years = [f"{y}-{str(y + 1)[-2:]}" for y in range(2012, 2026)]
    for y in summary_years:
        name = (
            f"{y} professional staff summary report"
            + ("_revised" if y == "2016-17" else "")
            + ".xlsx"
        )
        out.append(
            ("pde_staff_summary", f"{STAFF}prof-staff-summary/{name.replace(' ', '%20')}", name)
        )
    pairs = [
        "2015-16-2016-17",
        "2017-18-2018-19",
        "2019-20-2020-21",
        "2022-23-2023-24",
        "2023-24-2024-25",
        "2024-25-2025-26",
    ]
    for pr in pairs:
        for kind in (
            "retention-classroom-teachers",
            "attrition-classroom-teacher-exits-from-teaching",
        ):
            name = f"{pr}-{kind}.xlsx"
            url = f"{STAFF}{name}"
            if pr == "2015-16-2016-17" and kind.startswith("attrition"):
                url = f"{STAFF}2015-16%20to%202016-17-{kind}.xlsx"  # this one file is named differently
            out.append(("pde_staff_retention", url, name))
    out.append(
        (
            "pde_staff_retention",
            f"{STAFF}21-22%20to%2022-23-retention-classroom-teachers.xlsx",
            "21-22 to 22-23-retention-classroom-teachers.xlsx",
        )
    )
    out.append(
        (
            "pde_staff_retention",
            f"{STAFF}21-22%20to%2022-23-attrition-classroom-teacher-exits-from-teaching.xlsx",
            "21-22 to 22-23-attrition-classroom-teacher-exits-from-teaching.xlsx",
        )
    )
    out.append(
        (
            "pde_staff_retention",
            f"{STAFF}classroomteacherterminationcodessy2015-2023.xlsx",
            "classroomteacherterminationcodessy2015-2023.xlsx",
        )
    )
    out.append(
        ("pde_staff_vacancy", f"{STAFF}vacancysummary2023-24.xlsx", "vacancysummary2023-24.xlsx")
    )
    for q in (1, 2, 3, 4):
        name = f"2024-25-professional-staff-vacancy-report-q{q}.xlsx"
        out.append(("pde_staff_vacancy", f"{STAFF}{name}", name))
    out.append(
        (
            "pde_staff_vacancy",
            f"{STAFF}2025-26%20professional%20%20staff%20vacancy%20report%20q1.xlsx",
            "2025-26 professional staff vacancy report q1.xlsx",
        )
    )
    for q in (2, 3):
        name = f"2025-26 professional vacancies q{q}.xlsx"
        out.append(("pde_staff_vacancy", f"{STAFF}{name.replace(' ', '%20')}", name))
    out.append(
        ("pde_staff_vacancy", f"{STAFF}act%2035%20report%20final.xlsx", "act 35 report final.xlsx")
    )
    out.append(
        (
            "pde_staff_vacancy",
            f"{STAFF}act%2035%20report%20final%202025-26.xlsx",
            "act 35 report final 2025-26.xlsx",
        )
    )
    for y in [f"{y}-{str(y + 1)[-2:]}" for y in range(2015, 2026)]:
        stem = f"{y} public school support personnel" if y >= "2019" else f"{y} support personnel"
        name = stem + ".xlsx"
        out.append(("pde_support_staff", f"{STAFF}support-staff/{name.replace(' ', '%20')}", name))
    return out


def catalog_pde_school() -> list[dict]:
    today = datetime.now(UTC).date().isoformat()
    rows = []
    for key, url, name in [*FILES, *_staff_files()]:
        r = file_row(key, url, today)
        r["filename"] = name
        rows.append(r)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in rows:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())
    return rows


# ---------------------------------------------------------------------------------------------
# Parsing

import re

import pandas as pd
from python_calamine import CalamineWorkbook

from . import CORE, RAW

PPE_DIR = RAW / "pde_essa_ppe"
ENROLLMENT_DIR = RAW / "pde_enrollment"
EXP_COLS = [
    "local_personnel",
    "local_nonpersonnel",
    "state_personnel",
    "state_nonpersonnel",
    "federal_personnel",
    "federal_nonpersonnel",
]
SOURCE_ID = "pde_essa_ppe"


def _aun(value) -> str:
    return str(int(float(value))).zfill(9) if str(value).strip() else ""


def _num(value):
    if value is None or str(value).strip() in {"", "`"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _sheet(path, prefix: str) -> list[list]:
    wb = CalamineWorkbook.from_path(str(path))
    name = next(n for n in wb.sheet_names if n.startswith(prefix))
    return wb.get_sheet_by_name(name).to_python()


def _frame(rows: list[list]) -> pd.DataFrame:
    header = [re.sub(r"\s+", " ", str(c)).strip() for c in rows[0]]
    return pd.DataFrame(rows[1:], columns=header)


def read_ppe(path, level: str) -> pd.DataFrame:
    """One year's per-pupil expenditure sheet: `level` is 'Bldg' or 'LEA'."""
    year = int(path.name[:4]) + 1
    df = _frame(_sheet(path, f"ESSA Exp per ADM {level}"))
    df = df[df["AUN"].astype(str).str.strip() != ""]
    df = df[df["LEA Name"].astype(str).str.strip() != ""]
    cols = list(df.columns)
    first_exp = next(i for i, c in enumerate(cols) if "Local Personnel expenditures" in c)
    out = pd.DataFrame(
        {
            "sy": year,
            "aun": df["AUN"].map(_aun),
            "lea_name": df["LEA Name"].astype(str).str.strip(),
            "county": df["County"].astype(str).str.strip(),
            "ctgy": df["Ctgy"].map(_num) if "Ctgy" in df else None,
        }
    )
    if level == "Bldg":
        out["building_number"] = df["Building Number"].map(
            lambda v: str(int(float(v))) if _num(v) is not None else ""
        )
        out["building_name"] = df["Building Name"].astype(str).str.strip()
    for i, name in enumerate(EXP_COLS):
        out[name] = df.iloc[:, first_exp + i].map(_num).values
    out["adm"] = df.iloc[:, first_exp + 6].map(_num).values
    return out.reset_index(drop=True)


def build_pde_school() -> dict[str, pd.DataFrame]:
    xw = pd.read_parquet(CORE / "school_id_xwalk.parquet")
    ids = dict(
        zip(
            xw[xw["id_type"] == "state_key"]["id_value"],
            xw[xw["id_type"] == "state_key"]["school_id"],
            strict=False,
        )
    )
    buildings, leas = [], []
    for path in sorted(PPE_DIR.glob("* per pupil expenditures.xlsx")):
        buildings.append(read_ppe(path, "Bldg"))
        leas.append(read_ppe(path, "LEA"))
    b = pd.concat(buildings, ignore_index=True)
    lea = pd.concat(leas, ignore_index=True)
    for df in (b, lea):
        df["total_expenditures"] = df[EXP_COLS].sum(axis=1, min_count=1)
        df["expenditure_per_adm"] = (df["total_expenditures"] / df["adm"]).round(2)
        df["status"] = "reported"
        df["source_id"] = SOURCE_ID
    b["state_key"] = b["aun"] + "-" + b["building_number"]
    b.insert(0, "school_id", b["state_key"].map(ids))
    return {
        "finance_school_ppe": b,
        "finance_lea_ppe": lea,
        "finance_lea_enrollment": read_lea_enrollment(),
    }


LEA_ENROLL_SOURCE = "pde_enrollment"


def read_lea_enrollment() -> pd.DataFrame:
    """October 1 enrollment and low-income counts by LEA (districts, charters, CTCs) by year."""
    path = ENROLLMENT_DIR / "enrollment public school 1617 through 2526.xlsx"
    rows = _sheet(path, "10 Year LEA Enrollment")
    start = next(i for i, r in enumerate(rows) if r and r[0] == "LEA Name")
    years = [str(c) for c in rows[start][4:]]
    out = []
    for r in rows[start + 1 :]:
        if not r[1] or not str(r[1]).strip().isdigit():
            continue
        for y, v in zip(years, r[4:], strict=False):
            n = _num(v)
            if n is not None:
                out.append(
                    {
                        "aun": _aun(r[1]),
                        "lea_name": str(r[0]).strip(),
                        "lea_type": str(r[2]).strip(),
                        "county": str(r[3]).strip(),
                        "sy": int(y[-4:]),
                        "enrollment": n,
                    }
                )
    enroll = pd.DataFrame(out)
    low = _sheet(
        ENROLLMENT_DIR / "low income enrollments public school 1617 through 2526.xlsx", "10 Yr"
    )
    hdr = next(i for i, r in enumerate(low) if r and r[0] == "LEA")
    yrs = [(j, str(c)) for j, c in enumerate(low[hdr - 1]) if str(c).startswith("20")]
    li = []
    for r in low[hdr + 1 :]:
        if not r[1] or not str(r[1]).strip().isdigit():
            continue
        for j, y in yrs:
            n = _num(r[j])
            if n is not None:
                li.append({"aun": _aun(r[1]), "sy": int(y[-4:]), "low_income_students": n})
    enroll = enroll.merge(pd.DataFrame(li), on=["aun", "sy"], how="left")
    enroll["low_income_share"] = (enroll["low_income_students"] / enroll["enrollment"]).round(4)
    enroll["status"] = "reported"
    enroll["source_id"] = LEA_ENROLL_SOURCE
    return enroll


def write_pde_school() -> dict[str, pd.DataFrame]:
    t = build_pde_school()
    for name, df in t.items():
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    return t


# ---------------------------------------------------------------------------------------------
# PDE staff files (aggregate by agency only; the individual staff reports are not fetched)

STAFF_SOURCE = "pde_staff_summary"
RETENTION_SOURCE = "pde_staff_retention"
CATEGORIES = ["pp", "ad", "ct", "co", "ot"]


def _staff_cols() -> list[str]:
    cols = []
    for c in CATEGORIES:
        cols += [f"{c}_total", f"{c}_female", f"{c}_male"]
    for prefix in ("avg_salary", "avg_years_service", "avg_years_in_lea", "avg_education_level"):
        cols += [f"{prefix}_{c}" for c in CATEGORIES]
    return cols


def read_staff_summary() -> pd.DataFrame:
    """Professional staff by agency and year: counts by category and sex, and averages for
    full-time staff (salary, years of service, years in the agency, education level)."""
    cols = _staff_cols()
    parts = []
    for path in sorted(STAFF_SUMMARY_DIR.glob("* professional staff summary report*.xlsx")):
        year = int(path.name[:4]) + 1
        rows = _sheet(path, "LEA_Averages")
        h = next(i for i, r in enumerate(rows[:12]) if str(r[0]).strip().upper() == "AUN")
        recs = []
        for r in rows[h + 1 :]:
            if not str(r[0]).strip().replace(".", "").isdigit():
                continue
            rec = {
                "aun": _aun(r[0]),
                "lea_name": str(r[1]).strip(),
                "lea_type": str(r[2]).strip(),
                "county": str(r[3]).strip(),
                "sy": year,
            }
            for name, v in zip(cols, r[4 : 4 + len(cols)], strict=False):
                rec[name] = _num(v)
            recs.append(rec)
        parts.append(pd.DataFrame(recs))
    df = pd.concat(parts, ignore_index=True)
    df["status"] = "reported"
    df["source_id"] = STAFF_SOURCE
    return df


STAFF_SUMMARY_DIR = RAW / "pde_staff_summary"
RETENTION_DIR = RAW / "pde_staff_retention"


def read_teacher_retention() -> pd.DataFrame:
    """Classroom teacher retention by agency for each pair of consecutive years (All group)."""
    keep = {
        "GROUP_SIZE": "classroom_teachers_start",
        "N RETAINED CT": "n_retained_as_teacher",
        "% RETAINED CT": "pct_retained_as_teacher",
        "N SAME LEA NOT CT": "n_same_agency_other_role",
        "% SAME LEA NOT CT": "pct_same_agency_other_role",
        "N NEW LEA CT": "n_new_agency_as_teacher",
        "% NEW LEA CT": "pct_new_agency_as_teacher",
        "N NEW LEA NOT CT": "n_new_agency_other_role",
        "% NEW LEA NOT CT": "pct_new_agency_other_role",
        "PCT_SOC": "pct_students_of_color",
        "PCT_POV": "pct_students_poverty",
    }
    parts = []
    for path in sorted(RETENTION_DIR.glob("*retention-classroom-teachers.xlsx")):
        wb = CalamineWorkbook.from_path(str(path))
        sheet = next(n for n in wb.sheet_names if n.strip().lower() == "all")
        rows = wb.get_sheet_by_name(sheet).to_python()
        header = [re.sub(r"\s+", " ", str(c)).strip() for c in rows[0]]
        df = pd.DataFrame(rows[1:], columns=header)
        df = df[df["GROUP"].astype(str).str.strip() == "ALL CT"]
        exited = next(c for c in header if c.startswith("N EXITED"))
        pct_exited = next(c for c in header if c.startswith("% EXITED"))
        out = pd.DataFrame(
            {
                "aun": df["DISTRICT_KEY"].map(_aun),
                "lea_name": df["DISTRICT_NAME"].astype(str).str.strip(),
                "lea_type": df["ORG_TYPE_LONG"].astype(str).str.strip(),
                "county": df["COUNTY"].astype(str).str.strip(),
                "sy": int(str(df["SY_2"].iloc[0])[-2:]) + 2000,
            }
        )
        for src, dst in keep.items():
            out[dst] = df[src].map(_num).values
        out["n_left_education"] = df[exited].map(_num).values
        out["pct_left_education"] = df[pct_exited].map(_num).values
        parts.append(out)
    res = pd.concat(parts, ignore_index=True)
    res["status"] = "reported"
    res["source_id"] = RETENTION_SOURCE
    return res


def write_pde_staff() -> dict[str, pd.DataFrame]:
    t = {"staff_lea_profile": read_staff_summary(), "staff_lea_retention": read_teacher_retention()}
    for name, df in t.items():
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    return t
