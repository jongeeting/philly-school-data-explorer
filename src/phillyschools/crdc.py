"""Civil Rights Data Collection (U.S. Department of Education, Office for Civil Rights):
school discipline by race, sex, disability, and English learner status. District and charter.

Written to school_metric (part `crdc`): for each collection (2011-12 to 2021-22, every other
year; `sy` = spring year) and group, the number of students who received at least one
out-of-school suspension (`crdc_n_oss`), an in-school suspension (`crdc_n_iss`), an expulsion
with or without services (`crdc_n_expelled`), a referral to law enforcement
(`crdc_n_referred_law`), or a school-related arrest (`crdc_n_arrested`), and the enrollment for
that group (`crdc_enrollment`). Also 2011-12 and 2013-14, from Excel workbooks: 2013-14 uses
the modern variable names; 2011-12 uses its own (M_BLA_7_MULT_SUS_NO_DIS), translated to the
modern names, one workbook per table, with small cells written as "<=2" (suppressed).

How groups are built (from the CRDC manual): discipline is reported separately for students
without disabilities, students served under IDEA, and Section 504-only students; the three are
disjoint (non-disability enrollment = ENR - IDEA - 504). So:
  all, male, female, nonbinary  without + IDEA + 504 (nonbinary from 2021-22)
  race and ethnicity groups     without + IDEA (504 counts are not broken out by race, so race
                                counts leave out 504-only students)
  idea, section_504, without_disabilities, english_learner as published

Reserve codes: -2, -11, -12 suppressed (small cells); -9 not applicable; other negatives
missing. OCR rounds other counts for privacy, so totals are approximate. A school missing from
a topic file, or with blank cells, is not_reported. Usage agreement: never link the data with
individually identifiable data.

School IDs: COMBOKEY (12-digit NCES ID) when it is clean. The 2015-16 file stores it in
scientific notation (4.21899E+11), so there it is rebuilt from LEAID and SCHID; in 2017-18
SCHID holds a different code, so a valid COMBOKEY always wins. 2021-22 renamed LEP to EL.
"""

import io
import re
import zipfile

import pandas as pd

from . import CORE, RAW
from .metrics import write_metric_part

CRDC_DIR = RAW / "ed_crdc"
RACES = {
    "HI": "hispanic",
    "AM": "american_indian",
    "AS": "asian",
    "HP": "pacific_islander",
    "BL": "black",
    "WH": "white",
    "TR": "multiracial",
}
ACTIONS = {
    "crdc_n_oss": ["SINGOOS", "MULTOOS"],
    "crdc_n_iss": ["ISS"],
    "crdc_n_expelled": ["EXPWE", "EXPWOE"],
    "crdc_n_referred_law": ["REF"],
    "crdc_n_arrested": ["ARR"],
}
SUPPRESSED = {-2, -11, -12}
TOPIC_FILES = {"enrollment.csv", "suspensions.csv", "expulsions.csv", "referrals and arrests.csv"}
SEXES = "MFX"
LOADED = ["2011-12", "2013-14", "2015-16", "2017-18", "2020-21", "2021-22"]


def _school_members(z: zipfile.ZipFile) -> list[str]:
    """School-level CSVs: the single wide file (2015-16) or the topic files (2017-18 on)."""
    out = []
    for n in z.namelist():
        parts = n.replace("\\", "/").split("/")
        name = parts[-1].lower()
        folders = [p.lower() for p in parts[:-1]]
        if "lea" in folders or any("edfacts" in f for f in folders):
            continue
        in_school = any(f in ("sch", "school") or "school" in f for f in folders)
        if name.endswith("school data.csv") or (name in TOPIC_FILES and in_school):
            out.append(n)
    return out


def _needed(col: str) -> bool:
    if col in {"COMBOKEY", "LEAID", "SCHID"}:
        return True
    return bool(re.match(r"^(SCH|TOT)_(ENR|DISCWODIS|DISCWDIS)_", col)) and not re.search(
        r"(_PS|CORP|TFRALT|EXPZT|DAYS|INSTANCES)", col
    )


def _normalize(col: str) -> str:
    """2021-22 renamed LEP to EL."""
    return re.sub(r"_EL(_|$)", r"_LEP\1", col.strip())


def read_collection(path, nces: set[str]) -> pd.DataFrame:
    """One row per Philadelphia school (index: NCES ID), needed columns only."""
    z = zipfile.ZipFile(path)
    merged = None
    for member in _school_members(z):
        raw = z.read(member)
        header = [
            c.strip() for c in pd.read_csv(io.BytesIO(raw), nrows=0, encoding="latin-1").columns
        ]
        keep = frozenset(c for c in header if _needed(c))
        if not {"LEAID", "SCHID"} <= keep:
            continue
        parts = []
        reader = pd.read_csv(
            io.BytesIO(raw),
            usecols=lambda c, k=keep: c.strip() in k,
            dtype=str,
            encoding="latin-1",
            chunksize=100_000,
        )
        for chunk in reader:
            chunk.columns = [c.strip() for c in chunk.columns]
            rebuilt = chunk["LEAID"].str.strip().str.zfill(7) + chunk[
                "SCHID"
            ].str.strip().str.zfill(5)
            combo = chunk["COMBOKEY"].str.strip() if "COMBOKEY" in chunk else rebuilt
            chunk["nces"] = combo.where(combo.str.fullmatch(r"\d{12}", na=False), rebuilt)
            parts.append(chunk[chunk["nces"].isin(nces)])
        d = pd.concat(parts, ignore_index=True)
        d = d.drop(columns=["LEAID", "SCHID", "COMBOKEY"], errors="ignore").set_index("nces")
        d.columns = [_normalize(c) for c in d.columns]
        d = d.loc[:, ~d.columns.duplicated()]
        if merged is None:
            merged = d
        else:
            merged = merged.join(d[d.columns.difference(merged.columns)], how="outer")
    return merged if merged is not None else pd.DataFrame()


XLSX_2014 = ["03 Enrollment.xlsx", "11-2 Suspensions", "11-3 Expulsions", "12 Student Referrals"]
# 2011-12: one workbook per table. Table number (35 = without disabilities, 36 = with) and
# item -> modern action code; 1 (corporal punishment) and 7 (zero tolerance) are not used.
ITEM_2012 = {
    "2": "ISS",
    "3": "SINGOOS",
    "4": "MULTOOS",
    "5": "EXPWE",
    "6": "EXPWOE",
    "8": "REF",
    "9": "ARR",
}
GROUP_2012 = {
    "AME": "AM",
    "ASI": "AS",
    "HIS": "HI",
    "BLA": "BL",
    "WHI": "WH",
    "HI_PAC": "HP",
    "2_OR_MORE": "TR",
}


def _read_xlsx_rows(raw: bytes, nces: set[str]) -> pd.DataFrame:
    d = pd.read_excel(io.BytesIO(raw), sheet_name=0, engine="calamine", dtype=str)
    d.columns = [str(c).strip() for c in d.columns]
    rebuilt = d["LEAID"].str.strip().str.zfill(7) + d["SCHID"].str.strip().str.zfill(5)
    combo = d["COMBOKEY"].str.strip() if "COMBOKEY" in d else rebuilt
    d["nces"] = combo.where(combo.str.fullmatch(r"\d{12}", na=False), rebuilt)
    d = d[d["nces"].isin(nces)].set_index("nces")
    # 2011-12 writes small cells as text ("<=2"); treat as the suppression code
    return d.replace(to_replace=r"^\s*<.*$", value="-2", regex=True)


def _rename_2012(col: str, action: str | None) -> str | None:
    m = re.match(r"^([MF])_(.+?)_7_(.+)$", col)
    if not m:
        return None
    sex, grp, rest = m.groups()
    race = GROUP_2012.get(grp)
    if rest == "ENROL":
        if race:
            return f"SCH_ENR_{race}_{sex}"
        return {
            "TOT": f"TOT_ENR_{sex}",
            "DIS_IDEA": f"SCH_ENR_IDEA_{sex}",
            "DIS_504": f"SCH_ENR_504_{sex}",
            "LEP": f"SCH_ENR_LEP_{sex}",
        }.get(grp)
    if action is None:
        return None
    if rest.endswith("_NO_DIS"):
        if race:
            return f"SCH_DISCWODIS_{action}_{race}_{sex}"
        return {
            "TOT": f"TOT_DISCWODIS_{action}_{sex}",
            "LEP": f"SCH_DISCWODIS_{action}_LEP_{sex}",
        }.get(grp)
    if rest.endswith("_DIS"):
        if race:
            return f"SCH_DISCWDIS_{action}_IDEA_{race}_{sex}"
        return {
            "TOT_IDEA": f"TOT_DISCWDIS_{action}_IDEA_{sex}",
            "504": f"SCH_DISCWDIS_{action}_504_{sex}",
            "LEP": f"SCH_DISCWDIS_{action}_LEP_{sex}",
        }.get(grp)
    return None


def read_collection_xlsx(path, nces: set[str]) -> pd.DataFrame:
    """2013-14 (modern names in Excel) and 2011-12 (old names, one workbook per table)."""
    z = zipfile.ZipFile(path)
    frames = []
    if "2013-14" in path.name:
        for key in XLSX_2014:
            member = next(n for n in z.namelist() if key in n and n.endswith(".xlsx"))
            d = _read_xlsx_rows(z.read(member), nces)
            frames.append(d[[c for c in d.columns if _needed(c)]])
    else:
        for member in z.namelist():
            name = member.split("/")[-1]
            if "$" in name or not name.endswith(".xlsx"):
                continue
            item = re.search(r"(?<!\d)(35|36)-(\d)(?!\d)", name)
            enrollment = "05 - Overall Enrollment" in name
            if not (enrollment or (item and item.group(2) in ITEM_2012)):
                continue
            action = ITEM_2012[item.group(2)] if item else None
            d = _read_xlsx_rows(z.read(member), nces)
            mapping = {c: _rename_2012(c, action) for c in d.columns}
            d = d[[c for c, n in mapping.items() if n]].rename(columns=mapping)
            frames.append(d)
    merged = None
    for d in frames:
        d = d.drop(columns=["LEAID", "SCHID", "COMBOKEY"], errors="ignore")
        d = d.loc[:, ~d.columns.duplicated()]
        merged = (
            d
            if merged is None
            else merged.join(d[d.columns.difference(merged.columns)], how="outer")
        )
    return merged if merged is not None else pd.DataFrame()


def _sum(d: pd.DataFrame, cols: list[str]) -> tuple[pd.Series, pd.Series]:
    """Sum the columns that exist (non-binary `_X` columns are optional); status from codes."""
    present = [c for c in cols if c in d and not c.endswith("_X")]
    optional = [c for c in cols if c in d and c.endswith("_X")]
    if not present:
        return pd.Series(float("nan"), index=d.index), pd.Series("not_reported", index=d.index)
    v = d[present].apply(pd.to_numeric, errors="coerce")
    # Non-binary counts (2021-22 on) are added when reported; their -9 or blank never
    # makes the whole total missing.
    extra = d[optional].apply(pd.to_numeric, errors="coerce") if optional else None
    extra_sum = extra.where(extra > 0, 0).sum(axis=1) if optional else 0
    neg = v.lt(0)
    missing = v.isna().any(axis=1)
    total = (v.where(~neg, 0).sum(axis=1) + extra_sum).where(~neg.any(axis=1) & ~missing)
    status = pd.Series("reported", index=d.index)
    status[missing | neg.any(axis=1)] = "not_reported"
    status[v.eq(-9).all(axis=1)] = "not_applicable"
    status[v.isin(list(SUPPRESSED)).any(axis=1)] = "suppressed"
    required = [c for c in cols if not c.endswith("_X")]
    if any(c not in d for c in required):
        status[status == "reported"] = "partial"
        total = total.where(status != "partial")
    return total, status


def group_columns(d: pd.DataFrame, part: str) -> dict[str, list[str]]:
    wo, idea = f"DISCWODIS_{part}", f"DISCWDIS_{part}_IDEA"
    s504, lep = f"SCH_DISCWDIS_{part}_504", f"DISCWDIS_{part}_LEP"
    g = {}
    for sex, key in (("M", "male"), ("F", "female"), ("X", "nonbinary")):
        g[key] = [f"TOT_{wo}_{sex}", f"TOT_{idea}_{sex}", f"{s504}_{sex}"]
    g["all"] = g["male"] + g["female"] + g["nonbinary"]
    for code, name in RACES.items():
        g[name] = [f"SCH_{wo}_{code}_{s}" for s in SEXES] + [
            f"SCH_{idea}_{code}_{s}" for s in SEXES
        ]
    g["idea"] = [f"TOT_{idea}_{s}" for s in SEXES]
    g["section_504"] = [f"{s504}_{s}" for s in SEXES]
    g["without_disabilities"] = [f"TOT_{wo}_{s}" for s in SEXES]
    g["english_learner"] = [f"SCH_{wo}_LEP_{s}" for s in SEXES] + [f"SCH_{lep}_{s}" for s in SEXES]
    if not any(c in d for c in g["nonbinary"]):
        del g["nonbinary"]  # non-binary reporting starts in 2021-22
    return g


def enrollment_columns(d: pd.DataFrame) -> dict[str, list[str]]:
    g = {
        "male": ["TOT_ENR_M"],
        "female": ["TOT_ENR_F"],
        "nonbinary": ["TOT_ENR_X"],
        "all": ["TOT_ENR_M", "TOT_ENR_F", "TOT_ENR_X"],
    }
    for code, name in RACES.items():
        g[name] = [f"SCH_ENR_{code}_{s}" for s in SEXES]
    g["idea"] = [f"SCH_ENR_IDEA_{s}" for s in SEXES]
    g["section_504"] = [f"SCH_ENR_504_{s}" for s in SEXES]
    g["english_learner"] = [f"SCH_ENR_LEP_{s}" for s in SEXES]
    if "TOT_ENR_X" not in d:
        del g["nonbinary"]
    return g


def collection_rows(d: pd.DataFrame, sy: int) -> pd.DataFrame:
    rows = []
    enr = enrollment_columns(d)
    for group, cols in enr.items():
        v, st = _sum(d, cols)
        rows.append(
            pd.DataFrame(
                {
                    "nces": d.index,
                    "measure_id": "crdc_enrollment",
                    "student_group": group,
                    "value": v.values,
                    "status": st.values,
                }
            )
        )
    e_all, s_all = _sum(d, enr["all"])
    e_idea, s_idea = _sum(d, enr["idea"])
    e_504, s_504 = _sum(d, enr["section_504"])
    wo = e_all - e_idea - e_504
    wo_status = pd.Series("derived", index=wo.index)
    for part in (s_504, s_idea, s_all):  # a missing or suppressed part makes the result so
        wo_status = wo_status.where(part.isin(["reported", "partial"]), part)
    wo_status = wo_status.where(wo.notna(), "not_reported")
    # the parts can exceed the total after OCR's rounding or in a bad submission
    negative = wo < 0
    wo = wo.where(~negative)
    wo_status = wo_status.where(~negative, "invalid_in_source")
    rows.append(
        pd.DataFrame(
            {
                "nces": d.index,
                "measure_id": "crdc_enrollment",
                "student_group": "without_disabilities",
                "value": wo.values,
                "status": wo_status.values,
            }
        )
    )
    for measure, parts in ACTIONS.items():
        for group in group_columns(d, parts[0]):
            cols = [c for p in parts for c in group_columns(d, p)[group]]
            v, st = _sum(d, cols)
            rows.append(
                pd.DataFrame(
                    {
                        "nces": d.index,
                        "measure_id": measure,
                        "student_group": group,
                        "value": v.values,
                        "status": st.values,
                    }
                )
            )
    out = pd.concat(rows, ignore_index=True)
    out["sy"] = sy
    return out


def _nces_map() -> tuple[set[str], dict[str, str]]:
    xw = pd.read_parquet(CORE / "school_id_xwalk.parquet")
    n = xw[xw["id_type"] == "nces"]
    ever = n.groupby("id_value")["school_id"].nunique()
    unique = n[n["id_value"].isin(ever[ever == 1].index)].drop_duplicates("id_value")
    return set(n["id_value"]), unique.set_index("id_value")["school_id"].to_dict()


def build_crdc() -> dict:
    nces, to_id = _nces_map()
    frames = []
    for period in LOADED:
        path = CRDC_DIR / f"{period}-crdc-data.zip"
        if not path.exists():
            continue
        reader = read_collection_xlsx if period in ("2011-12", "2013-14") else read_collection
        d = reader(path, nces)
        if not d.empty:
            frames.append(collection_rows(d, int(period[:4]) + 1).assign(period=period))
    m = pd.concat(frames, ignore_index=True)
    m["school_id"] = m["nces"].map(to_id)
    unmapped = m[m["school_id"].isna()].drop_duplicates(["sy", "nces"])[["sy", "nces"]]
    m = m.dropna(subset=["school_id"])
    m["source_id"] = "ed_crdc:" + m["period"]
    metric = m[["school_id", "sy", "measure_id", "student_group", "value", "status", "source_id"]]
    return {"metric": metric.reset_index(drop=True), "unmapped": unmapped}


def write_crdc(t: dict) -> pd.DataFrame:
    t["unmapped"].to_csv(CORE / "crdc_unmapped.csv", index=False)
    return write_metric_part("crdc", t["metric"])
