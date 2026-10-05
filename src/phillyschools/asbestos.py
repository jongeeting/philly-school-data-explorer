"""Asbestos (AHERA) results from the district's periodic reports (archived by
fetch-environmental-latest).

Each building gets a 6-month periodic surveillance and a 3-year re-inspection. Since 2023 both
use one template, with the building's ULCS code, the inspection dates, and Appendix A, the
room-by-room log: every material in every space, its asbestos status (Confirmed, Assumed, NAD =
no asbestos detected, Non-Suspect), its amount, and the amount damaged, in square feet (SF),
linear feet (LF), each (EA), or cubic feet (CF).

Tables:
  building_asbestos       one row per building report: ULCS, report type, dates, and totals
                          from the log (asbestos items, amounts, damaged items and amounts)
  building_asbestos_item  the log's confirmed and assumed asbestos rows (material, space,
                          amount, damage), from each building's most recent report

Amounts are not added across units. Older reports (2016 to 2021, a different layout) are listed
with status not_reported when their log cannot be read.
"""

import re
from pathlib import Path

import pandas as pd

from . import CORE, RAW
from .environmental import ahera_key, report_date
from .envresults import match_name, pdf_text, school_index, site_corrections, water_site_name
from .metrics import write_metric_part

MIN_LOG_ROWS = 5  # fewer rows means the log was not read (older layouts)
AHERA = RAW / "sdp_environmental" / "ahera"
STATUS = r"Confirmed|Assumed|NAD|Non[\s-]?Suspect(?:\s+ACM)?"
NUM = r"[\d,]*\.?\d+"
UNIT = r"SF|LF|EA|CF"
LOG_ROW = re.compile(
    rf"^\s*(\S+)\s+(\S+)\s+(\S+)\s+(.+?)\s+({STATUS})\s+({NUM})\s+({UNIT})\s+({NUM}|N/A)\s+({UNIT})\b(.*)$"
)
ULCS = re.compile(r"ULCS\s*#?\s*:?\s*(\d{4})")
YEAR_BUILT = re.compile(r"Year Built:\s*(\d{4})")
PERFORMED = re.compile(
    r"(?:Surveillance|Re-Inspection|Inspection) (?:Performed|was completed between):?\s*([A-Za-z]+ \d{1,2}[^\n]*?\d{4})"
)
MATERIAL_GROUPS = [
    (
        "pipe and boiler insulation",
        r"pipe|fitting|insulation|boiler|tank|breeching|duct|aircell|magnesia",
    ),
    ("floor tile and mastic", r"floor tile|vat|mastic|linoleum|sheet flooring|cove base"),
    ("transite", r"transite"),
    ("plaster and surfacing", r"plaster|fireproof|acoustic|surfacing|spray"),
    ("ceiling tile", r"ceiling tile"),
    ("caulk, glazing, and sealants", r"caulk|glazing|sealant|putty|damp ?proof|roof"),
]


def material_group(desc: str) -> str:
    d = desc.lower()
    for group, pattern in MATERIAL_GROUPS:
        if re.search(pattern, d):
            return group
    return "other"


def _num(s: str) -> float | None:
    return None if s == "N/A" else float(s.replace(",", ""))


def log_rows(text: str) -> pd.DataFrame:
    start = text.find("ROOM-BY-ROOM LOG")
    rows = []
    for line in text[max(start, 0) :].splitlines():
        m = LOG_ROW.match(line)
        if not m:
            continue
        element, floor, space, rest, status, amt, unit, dmg, _dunit, notes = m.groups()
        status = "Non-Suspect" if status.lower().startswith("non") else status
        rows.append(
            {
                "element": element,
                "floor": floor,
                "space_id": space,
                "room_and_material": " ".join(rest.split()),
                "acm_status": status,
                "amount": _num(amt),
                "unit": unit,
                "damaged_amount": _num(dmg),
                "notes": " ".join(notes.split()) or None,
            }
        )
    return pd.DataFrame(rows)


def summarize(log: pd.DataFrame) -> dict:
    out = {"log_rows": len(log)}
    acm = log[log["acm_status"].isin(["Confirmed", "Assumed"])] if len(log) else log
    out["acm_items"] = len(acm)
    out["acm_items_confirmed"] = int((acm["acm_status"] == "Confirmed").sum()) if len(acm) else 0
    dmg = acm[acm["damaged_amount"].fillna(0) > 0] if len(acm) else acm
    out["acm_items_damaged"] = len(dmg)
    for unit in ["SF", "LF", "EA"]:
        u = unit.lower()
        out[f"acm_{u}"] = float(acm.loc[acm["unit"] == unit, "amount"].sum()) if len(acm) else 0.0
        out[f"acm_damaged_{u}"] = (
            float(dmg.loc[dmg["unit"] == unit, "damaged_amount"].sum()) if len(dmg) else 0.0
        )
    return out


def report_rows() -> list[dict]:
    """Latest 6-month and 3-year report per building code among the archived files."""
    latest: dict = {}
    for path in AHERA.rglob("*"):
        if not path.is_file() or not path.parent.name.endswith("Management Plan Archive"):
            continue
        key, when = ahera_key(path.name), report_date(path.name)
        if not key or not when or key[1] not in {"6-month", "3-year"}:
            continue
        if key not in latest or when > latest[key][0]:
            latest[key] = (when, path)
    return [
        {"building_code": k[0], "report_type": k[1], "file_date": w, "path": p}
        for k, (w, p) in latest.items()
    ]


def read_report(path: Path) -> tuple[dict, pd.DataFrame]:
    text = pdf_text(path)
    head = text[:20000]
    log = log_rows(text)
    info = {
        "ulcs_in_report": (m.group(1) if (m := ULCS.search(head)) else None),
        "year_built": int(m.group(1)) if (m := YEAR_BUILT.search(head)) else None,
        "inspection_period": " ".join(m.group(1).split())
        if (m := PERFORMED.search(head))
        else None,
    }
    return {**info, **summarize(log)}, log


def link_building(code: str, ulcs: str | None, folder: str, to_id, idx: dict, fixes=None):
    """The school's ULCS code, the code printed in the report, then the folder's school name.

    Annexes and little school houses have their own codes and link by name to their school;
    garages, field houses, and offices stay unlinked."""
    if fixes and folder in fixes:
        return fixes[folder], "correction"
    if code in to_id:
        return to_id[code], "building_code"
    if ulcs and ulcs in to_id:
        return to_id[ulcs], "ulcs_in_report"
    name = re.sub(r"\b(Annex|Little School House|LSH|Building)\b.*$", "", folder).strip(" -,")
    sid, how = match_name(water_site_name(name), idx, partial=False)
    return sid, how


def build_asbestos() -> dict:
    reg = pd.read_csv(RAW.parent / "registry" / "school_id_registry.csv", dtype=str)
    to_id = reg.set_index("ulcs")["school_id"]
    idx = school_index()
    reports, items = [], []
    for r in sorted(report_rows(), key=lambda r: (r["building_code"], r["report_type"])):
        info, log = read_report(r["path"])
        y, mo = r["file_date"]
        rel = str(r["path"].relative_to(RAW.parent))
        reports.append(
            {
                "building_code": r["building_code"],
                "school_id": None,
                "site_folder": r["path"].parent.parent.name,
                "report_type": r["report_type"],
                "report_year": y,
                "report_month": mo or None,
                "file": rel,
                **info,
                "status": "reported" if info["log_rows"] >= MIN_LOG_ROWS else "not_reported",
            }
        )
        if len(log):
            acm = log[log["acm_status"].isin(["Confirmed", "Assumed"])].copy()
            acm["material_group"] = acm["room_and_material"].map(material_group)
            items.append(
                acm.assign(building_code=r["building_code"], report_type=r["report_type"], file=rel)
            )
    rep = pd.DataFrame(reports)
    fixes = site_corrections()
    links = [
        link_building(c, u, f, to_id, idx, fixes)
        for c, u, f in zip(
            rep["building_code"], rep["ulcs_in_report"], rep["site_folder"], strict=True
        )
    ]
    rep["school_id"] = [x[0] for x in links]
    rep["link_method"] = [x[1] for x in links]
    rep["source_id"] = "sdp_environmental:ahera"
    # the most recent readable report per building feeds the item table and school_metric
    rep["_order"] = rep["report_year"] * 100 + rep["report_month"].fillna(0)
    rep["is_latest"] = False
    ok = rep[rep["status"] == "reported"].sort_values("_order")
    rep.loc[ok.groupby("building_code").tail(1).index, "is_latest"] = True
    rep = rep.drop(columns="_order")
    latest_files = set(rep.loc[rep["is_latest"], "file"])
    item = pd.concat(items, ignore_index=True) if items else pd.DataFrame()
    if len(item):
        item = item[item["file"].isin(latest_files)].reset_index(drop=True)
    return {"report": rep, "item": item}


ASBESTOS_MEASURES = {
    "asbestos_items": "acm_items",
    "asbestos_items_damaged": "acm_items_damaged",
}


def asbestos_metric(rep: pd.DataFrame) -> pd.DataFrame:
    """Per school: the latest report of each of its buildings, added together.

    A school with an annex or little school house has more than one building code; counts of
    items add across buildings, and the school's year is its most recent report's."""
    latest = rep[rep["is_latest"] & rep["school_id"].notna()].copy()
    latest["school_id"] = latest["school_id"].str.split(", ")
    latest = latest.explode("school_id")
    latest["sy"] = [
        y + (1 if (m or 0) >= 7 else 0)
        for y, m in zip(latest["report_year"], latest["report_month"], strict=True)
    ]
    agg = latest.groupby("school_id").agg(
        sy=("sy", "max"), **{m: (c, "sum") for m, c in ASBESTOS_MEASURES.items()}
    )
    out = agg.reset_index().melt(["school_id", "sy"], var_name="measure_id", value_name="value")
    return out.assign(student_group="all", status="reported", source_id="sdp_environmental:ahera")


def write_asbestos(t: dict) -> pd.DataFrame:
    for name, df in [("building_asbestos", t["report"]), ("building_asbestos_item", t["item"])]:
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    return write_metric_part("env_asbestos", asbestos_metric(t["report"]))
