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


def catalog_pde_school() -> list[dict]:
    today = datetime.now(UTC).date().isoformat()
    rows = []
    for key, url, name in FILES:
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
