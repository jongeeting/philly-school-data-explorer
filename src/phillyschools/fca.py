"""Facility condition assessments (Parsons for the district, 2020 cycle, reports dated 2021-22).

The 77 reports on the district's Drive share one layout (eCOMET export). From each:

  facility_condition         one row per site: gross area, year built, last renovation,
                             replacement value, repair cost, facility condition index (FCI =
                             repair cost / replacement value), remaining service life (RSLI),
                             condition, suitability, and overall school scores
  facility_condition_part    one row per building and grounds on the site (B... and G... codes)
                             with its FCI, repair cost, and replacement cost
  facility_condition_system  FCI and costs for 14 major building systems on the site

The district's FCI tiers: under 15% minimal capital need; 15-25% refurbish systems; 25-45%
replace systems; 45-60% consider major renovation; over 60% consider closing or replacement.
System FCIs can exceed 100% (replacing one system can require upgrading others).

Linking: building codes are B + the first three digits of the school's ULCS + a sequence
(B842001 = ULCS 8420); the site links to the school of its first building that is in the
registry, and every building is kept.
"""

import re

import pandas as pd

from . import CORE, RAW
from .envresults import match_site, pdf_text, school_index, site_corrections
from .metrics import write_metric_part

FCA_DIR = RAW / "sdp_facility_condition" / "fca_2020_2022"
MONEY = r"\$([\d,]+)"
PCT = r"(-?[\d.]+)%"
PART_ROW = re.compile(rf"^\s*([BG]\d{{6}})[;:](.+?)\s+{PCT}\s+{MONEY}\s+{MONEY}\s*$")
PART_START = re.compile(r"^\s*([BG]\d{6})[;:](.+?)\s*$")  # a name that wraps
NUMBERS_ONLY = re.compile(rf"^\s*{PCT}\s+{MONEY}\s+{MONEY}\s*$")
OVERALL_ROW = re.compile(rf"^\s*Overall\s+{PCT}\s+{MONEY}\s+{MONEY}\s*$")
SYSTEM_ROW = re.compile(rf"^\s*(\S.+?)\s+{PCT}\s+{MONEY}\s+{MONEY}\s*$")
SITE = re.compile(r"^\s*(S\d{6});(.+?)\s*$", re.MULTILINE)
SUMMARY_FIELDS = {
    "gross_area_sf": r"Gross Area \(SF\):\s*([\d,]+)",
    "year_built": r"Year Built:\s*(\d{4})",
    "last_renovation": r"Last Renovation:\s*(\d{4})",
    "rsli_pct": r"Total RSLI:\s*([\d.]+)%",
    "condition_score_pct": r"Condition Score:\s*([\d.]+)%",
    "suitability_score_pct": r"Suitability Score:\s*([\d.]+)%",
    "school_score_pct": r"School Score:\s*([\d.]+)%",
}
OPEN_IN = 2021  # schools still listed when the 2020 cycle was assessed
HEADER_FIELDS = {
    "address": r"Address[ \t]+(\d.*?)(?:[ \t]{2,}|$)",
    "governance": r"Governance[ \t]+(\S+)",
    "report_type": r"Report Type[ \t]+(\S.*?)[ \t]*$",
    "enrollment": r"Enrollment[ \t]+([\d,]+)",
    "grade_range": r"Grade Range[ \t]+(\S+)",
}
REPORT_DATE = re.compile(r"Assessment Report\s+([A-Z][a-z]+ \d{1,2}, \d{4})")


def _money(s: str) -> float:
    return float(s.replace(",", ""))


def _field(pattern: str, text: str, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def parse_report(text: str) -> dict:
    """Site summary, parts, and systems from the first pages of one report."""
    site = SITE.search(text)
    head = text[: text.find("Table of Contents")] if "Table of Contents" in text else text[:8000]
    summary = text  # the summary labels appear once, on the site executive summary page
    out = {
        "site_code": site.group(1) if site else None,
        "site_name": site.group(2).strip() if site else None,
        "cycle": _field(r"(20\d\d) Assessment Report", head),
        "report_date": _field(REPORT_DATE.pattern, head),
    }
    for k, p in HEADER_FIELDS.items():
        out[k] = _field(p, head, re.MULTILINE)
    for k, p in SUMMARY_FIELDS.items():
        v = _field(p, summary)
        out[k] = float(v.replace(",", "")) if v else None
    parts, systems, section, pending = [], [], None, None
    for line in head.splitlines():
        if section == "parts" and pending is not None:
            if m := NUMBERS_ONLY.match(line):
                pending.update(
                    fci_pct=float(m.group(1)),
                    repair_cost=_money(m.group(2)),
                    replacement_value=_money(m.group(3)),
                )
                continue
            if "fci_pct" in pending and line.strip() and not PART_START.match(line):
                pending["part_name"] += " " + line.strip()  # the rest of a wrapped name
                continue
            parts.append(pending)
            pending = None
        if "Building and Grounds" in line:
            section = "parts"
        elif "Major Building Systems" in line:
            if pending is not None:
                parts.append(pending)
                pending = None
            section = "systems"
        elif line.strip().startswith("Please note"):
            section = None
        if m := OVERALL_ROW.match(line):
            out.update(
                fci_pct=float(m.group(1)),
                repair_cost=_money(m.group(2)),
                replacement_value=_money(m.group(3)),
            )
        elif section == "parts" and not PART_ROW.match(line) and (m := PART_START.match(line)):
            pending = {"part_code": m.group(1), "part_name": m.group(2).strip()}
        elif (m := PART_ROW.match(line)) and section == "parts":
            parts.append(
                {
                    "part_code": m.group(1),
                    "part_name": m.group(2).strip(),
                    "fci_pct": float(m.group(3)),
                    "repair_cost": _money(m.group(4)),
                    "replacement_value": _money(m.group(5)),
                }
            )
        elif (m := SYSTEM_ROW.match(line)) and section == "systems" and "System FCI" not in line:
            systems.append(
                {
                    "system": m.group(1).strip(),
                    "fci_pct": float(m.group(2)),
                    "repair_cost": _money(m.group(3)),
                    "replacement_value": _money(m.group(4)),
                }
            )
    return {"site": out, "parts": parts, "systems": systems}


def ulcs_for_part(code: str) -> str:
    return code[1:4] + "0"


def build_fca() -> dict:
    reg = pd.read_csv(RAW.parent / "registry" / "school_id_registry.csv", dtype=str)
    to_id = reg.set_index("ulcs")["school_id"]
    school = pd.read_parquet(CORE / "school.parquet")
    open_through = dict(zip(school["school_id"], school["last_sy_in_data"], strict=True))
    idx = school_index()
    fixes = site_corrections()  # keyed by site code for FCA sites
    sites, parts, systems = [], [], []
    for path in sorted(FCA_DIR.glob("*.pdf")):
        r = parse_report(pdf_text(path, 1, 8))
        s = r["site"]
        rel = str(path.relative_to(RAW.parent))
        building_ids = [
            to_id.get(ulcs_for_part(p["part_code"]))
            for p in r["parts"]
            if p["part_code"].startswith("B")
        ]
        # a code can belong to a school that closed before the 2020 assessment
        linked = [b for b in building_ids if b and open_through.get(b, 0) >= OPEN_IN]
        how = "building_code"
        if s.get("site_code") in fixes:
            linked, how = [fixes[s["site_code"]]], "correction"
        if not linked:
            sid, how = match_site(s.get("address") or "", s.get("site_name") or "", idx)
            linked = sid.split(", ") if sid else []
        s.update(
            file=rel,
            school_id=linked[0] if linked else None,
            link_method=how if linked else "unmatched",
        )
        s["school_ids_all"] = ", ".join(sorted(set(linked))) or None
        sites.append(s)
        for p in r["parts"]:
            parts.append(
                {"site_code": s["site_code"], **p, "school_ids": s["school_ids_all"], "file": rel}
            )
        for y in r["systems"]:
            systems.append({"site_code": s["site_code"], **y, "file": rel})
    site = pd.DataFrame(sites)
    # one site was posted twice (under Central and Girls); keep the later report
    site["_d"] = pd.to_datetime(site["report_date"], format="%B %d, %Y", errors="coerce")
    keep = set(site.sort_values("_d").drop_duplicates("site_code", keep="last")["file"])
    site = site[site["file"].isin(keep)].drop(columns="_d").reset_index(drop=True)
    parts = [p for p in parts if p["file"] in keep]
    systems = [y for y in systems if y["file"] in keep]
    site["status"] = site["fci_pct"].map(lambda v: "reported" if pd.notna(v) else "not_reported")
    site["source_id"] = "sdp_facility_condition:fca_2020"
    return {"site": site, "part": pd.DataFrame(parts), "system": pd.DataFrame(systems)}


FCA_MEASURES = {
    "fca_fci_pct": "fci_pct",
    "fca_condition_score_pct": "condition_score_pct",
    "fca_suitability_score_pct": "suitability_score_pct",
    "fca_school_score_pct": "school_score_pct",
}


def fca_metric(site: pd.DataFrame) -> pd.DataFrame:
    """Site figures for each school on the site (a site can house more than one school).

    A school on more than one site (a main building and an annex site) gets the FCI of the
    combined costs and replacement-value-weighted scores."""
    s = site[site["school_ids_all"].notna()].copy()
    s["school_id"] = s["school_ids_all"].str.split(", ")
    s = s.explode("school_id")
    s["sy"] = pd.to_datetime(s["report_date"], format="%B %d, %Y", errors="coerce").map(
        lambda t: None if pd.isna(t) else t.year + (1 if t.month >= 7 else 0)
    )
    s = s.dropna(subset=["sy"])
    rows = []
    for (sid, sy), g in s.groupby(["school_id", "sy"]):
        w = g["replacement_value"]
        row = {"school_id": sid, "sy": int(sy)}
        row["fca_fci_pct"] = round(100 * g["repair_cost"].sum() / w.sum(), 2)
        for measure, col in list(FCA_MEASURES.items())[1:]:
            ok = g[col].notna()
            row[measure] = (
                round((g.loc[ok, col] * w[ok]).sum() / w[ok].sum(), 2) if ok.any() else None
            )
        rows.append(row)
    out = pd.DataFrame(rows).melt(["school_id", "sy"], var_name="measure_id", value_name="value")
    out = out.dropna(subset=["value"])
    return out.assign(
        student_group="all", status="reported", source_id="sdp_facility_condition:fca_2020"
    )


def write_fca(t: dict) -> pd.DataFrame:
    for name, key in [
        ("facility_condition", "site"),
        ("facility_condition_part", "part"),
        ("facility_condition_system", "system"),
    ]:
        t[key].to_parquet(CORE / f"{name}.parquet", index=False)
        t[key].to_csv(CORE / f"{name}.csv", index=False)
    return write_metric_part("fca", fca_metric(t["site"]))
