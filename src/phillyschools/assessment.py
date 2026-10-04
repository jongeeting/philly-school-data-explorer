"""District PSSA and Keystone results (School District of Philadelphia), 2009-10 on.

Table `assessment_result`, grain: school x sy x test x subject x grade x student group x
performance level, with count, percent, number tested, and status. Long by level, so a
reader can recompute any share from counts.

Formats ("Actual" school files: all tested students, not the accountability subset):
  2009-10 to 2016-17  workbooks, one sheet per group category, SRC school IDs, percents as
                      fractions, title rows above the header
  2017-18, 2018-19    one long sheet (SRC IDs in 2017-18, ULCS from 2018-19)
  2021-22 on          CSVs with short names (denom, prof_num, profadv_score); ULCS
No 2019-20 file (no spring 2020 tests). District files cover district schools; charter
results come from Future Ready (school_metric).
"""

import io
import re
import zipfile

import pandas as pd

from . import CORE, RAW
from .enrollment import _src_to_ulcs, to_count

PSSA_DIR = RAW / "sdp_pssa_keystone"
LEVELS = ["below_basic", "basic", "proficient", "advanced", "proficient_or_advanced"]


def _actual_school_member(zf: zipfile.ZipFile) -> str:
    names = [n for n in zf.namelist() if not n.endswith("/")]
    return next(n for n in names if "actual" in n.lower() and "school" in n.lower())


def _sy(path) -> int:
    return int(re.search(r"(\d{4})_(\d{4})", path.name).group(2))


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def read_workbook_era(data: bytes) -> pd.DataFrame:
    """2009-10 to 2016-17: one sheet per category, header row starts with 'Test Name'."""
    book = pd.ExcelFile(io.BytesIO(data), engine="calamine")
    frames = []
    for sheet in book.sheet_names:
        if sheet.lower() == "notes":
            continue
        d = book.parse(sheet, header=None, dtype=str)
        hit = d.apply(lambda r: r.astype(str).str.strip().eq("Test Name").any(), axis=1)
        if not hit.any():
            continue
        h = int(hit.idxmax())
        cols = [_norm(c) for c in d.iloc[h]]
        body = d.iloc[h + 1 :]
        start = cols.index("Number Tested")
        rec = pd.DataFrame(
            {
                "test": body[cols.index("Test Name")],
                "subject": body[cols.index("Subject")],
                "school_code": body[cols.index("School Code")],
                "school_name": body[cols.index("School Name")],
                "grade": body[cols.index("Grade")],
                "group": body[cols.index("Category")],
                "category": sheet,
                "n_tested": body[start],
            }
        )
        for i, level in enumerate(LEVELS):
            rec[f"{level}_count"] = body[start + 1 + 2 * i]
            rec[f"{level}_pct"] = body[start + 2 + 2 * i]
        frames.append(rec[rec["test"].notna() & rec["school_code"].notna()])
    out = pd.concat(frames, ignore_index=True)
    out["pct_scale"] = "fraction"
    return out


def read_long_sheet(data: bytes) -> pd.DataFrame:
    """2017-18 and 2018-19: one long sheet."""
    d = pd.read_excel(io.BytesIO(data), engine="calamine", dtype=str)
    d.columns = [_norm(c) for c in d.columns]
    code = "SRC School ID" if "SRC School ID" in d else "School ID"
    out = pd.DataFrame(
        {
            "test": d["Test Name"],
            "subject": d["Subject"],
            "school_code": d[code],
            "school_name": d["School Name"],
            "grade": d["Grade"],
            "group": d["Group"],
            "category": d["Category"],
            "n_tested": d["Number Tested"],
        }
    )
    names = {
        "below_basic": "Below Basic",
        "basic": "Basic",
        "proficient": "Proficient",
        "advanced": "Advanced",
        "proficient_or_advanced": "Prof/Adv",
    }
    for level, label in names.items():
        out[f"{level}_count"] = d[f"Count {label}"]
        out[f"{level}_pct"] = d[f"Percent {label}"]
    out["pct_scale"] = "percent"
    out["code_type"] = "src" if code == "SRC School ID" else "ulcs"
    return out


def read_csv_era(data: bytes) -> pd.DataFrame:
    d = pd.read_csv(io.BytesIO(data), dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    d.columns = [c.strip().lower() for c in d.columns]
    code = "ulcs_code" if "ulcs_code" in d else "id_eos"
    out = pd.DataFrame(
        {
            "test": d["testname"],
            "subject": d["subject"],
            "school_code": d[code],
            "school_name": d["publicationname"],
            "grade": d["grade"],
            "group": d["group"],
            "category": d["category"],
            "n_tested": d["denom"],
        }
    )
    short = {
        "below_basic": "bel",
        "basic": "bas",
        "proficient": "prof",
        "advanced": "adv",
        "proficient_or_advanced": "profadv",
    }
    for level, s in short.items():
        out[f"{level}_count"] = d[f"{s}_num"]
        out[f"{level}_pct"] = d[f"{s}_score"]
    out["pct_scale"] = "percent"
    out["code_type"] = "ulcs"
    return out


def stage_assessments() -> pd.DataFrame:
    frames = []
    for path in sorted(PSSA_DIR.glob("20*_20*_*.zip")):
        sy = _sy(path)
        zf = zipfile.ZipFile(path)
        name = _actual_school_member(zf)
        data = zf.read(name)
        if name.lower().endswith(".csv"):
            d = read_csv_era(data)
        elif sy <= 2017:
            d = read_workbook_era(data)
            d["code_type"] = "src"
        else:
            d = read_long_sheet(data)
        d["sy"] = sy
        d["source_file"] = f"{path.name}!{name}"
        frames.append(d)
    out = pd.concat(frames, ignore_index=True)
    for c in ["test", "subject", "group", "category", "school_name"]:
        out[c] = out[c].map(_norm)
    out["school_code"] = (
        out["school_code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )
    out["grade"] = out["grade"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return out


SUBJECTS = {
    "math": "math",
    "reading": "reading",
    "ela": "ela",
    "science": "science",
    "writing": "writing",
    "algebra 1": "algebra_1",
    "algebra i": "algebra_1",
    "biology": "biology",
    "literature": "literature",
}
GROUPS = {
    "all students": "all",
    "ell": "english_learner",
    "not ell": "not_english_learner",
    "iep": "iep",
    "not iep": "not_iep",
    "female": "female",
    "male": "male",
    "econ. disadv.": "econ_disadvantaged",
    "economically disadvantaged": "econ_disadvantaged",
    "not econ. disadv.": "not_econ_disadvantaged",
    "not economically disadvantaged": "not_econ_disadvantaged",
    "american indian/alaskan native (not hispanic)": "american_indian",
    "asian (not hispanic)": "asian",
    # Older files combine Asian and Pacific Islander; kept separate, never merged into "asian".
    "asian/pacific islander (not hispanic)": "asian_pacific_islander",
    "black/african american (not hispanic)": "black",
    "hispanic (any race)": "hispanic",
    "multi-racial/two or more races (not hispanic)": "multiracial",
    "native hawaiian or other pacific islander (not hispanic)": "pacific_islander",
    "white (not hispanic)": "white",
    "other": "other",
}


def grade_label(g: str) -> str:
    low = g.lower()
    if low.startswith("all"):
        return "ALL"
    if "3" in low and "8" in low and not low.isdigit():
        return "03-08"
    return f"{int(g):02d}" if g.isdigit() else g


def build_assessments() -> dict:
    d = stage_assessments()
    src = _src_to_ulcs()
    registry = pd.read_csv(RAW.parent / "registry" / "school_id_registry.csv", dtype=str)
    ulcs_to_id = registry.set_index("ulcs")["school_id"]
    ulcs = [
        src.get((c, sy)) if t == "src" else c
        for c, sy, t in zip(d["school_code"], d["sy"], d["code_type"], strict=True)
    ]
    d["school_id"] = pd.Series(ulcs, index=d.index).map(ulcs_to_id)
    issues = (
        d[d["school_id"].isna()]
        .drop_duplicates(["sy", "school_code"])[["sy", "school_code", "school_name"]]
        .assign(type="assessment school not mapped")
    )
    d = d.dropna(subset=["school_id"])
    d["subject"] = d["subject"].str.lower().map(SUBJECTS)
    d["student_group"] = d["group"].str.lower().map(GROUPS)
    unmapped_groups = sorted(d.loc[d["student_group"].isna(), "group"].unique())
    d = d.dropna(subset=["subject", "student_group"])
    d["grade"] = d["grade"].map(grade_label)
    d["test"] = d["test"].str.lower()

    n = d["n_tested"].map(to_count)
    rows = []
    for level in LEVELS:
        c = d[f"{level}_count"].map(to_count)
        p = d[f"{level}_pct"].map(to_count)
        scale = d["pct_scale"].map({"fraction": 100.0, "percent": 1.0})
        rows.append(
            pd.DataFrame(
                {
                    "school_id": d["school_id"],
                    "sy": d["sy"],
                    "test": d["test"],
                    "subject": d["subject"],
                    "grade": d["grade"],
                    "student_group": d["student_group"],
                    "level": level,
                    "n_tested": [x[0] for x in n],
                    "count": [x[0] for x in c],
                    "pct": [
                        None if x[0] is None else round(x[0] * s, 2)
                        for x, s in zip(p, scale, strict=True)
                    ],
                    "status": [
                        "suppressed"
                        if "suppressed" in (a[1], b[1])
                        else "reported"
                        if a[1] == "reported" or b[1] == "reported"
                        else "not_reported"
                        for a, b in zip(c, p, strict=True)
                    ],
                    "source_id": "sdp_pssa_keystone:sy" + d["sy"].astype(str),
                }
            )
        )
    out = pd.concat(rows, ignore_index=True)
    key = ["school_id", "sy", "test", "subject", "grade", "student_group", "level"]
    dups = out.duplicated(key, keep=False)
    if dups.any():
        # Some old workbooks list a school-grade twice (for example on two sheets); keep the
        # row with more students tested.
        out = out.sort_values("n_tested", ascending=False, na_position="last").drop_duplicates(key)
    return {
        "assessment_result": out.reset_index(drop=True),
        "issues": issues,
        "unmapped_groups": unmapped_groups,
        "duplicates": int(dups.sum()),
    }


def write_assessments(t: dict) -> None:
    t["assessment_result"].to_parquet(CORE / "assessment_result.parquet", index=False)
    t["assessment_result"].to_csv(CORE / "assessment_result.csv", index=False)
    t["issues"].to_csv(CORE / "assessment_issues.csv", index=False)
