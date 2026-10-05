"""Results extracted from the district's environmental PDFs (archived by fetch-environmental-latest).

Lead paint (table `school_lead_paint`, one row per assessment file): the lead-safe assessments
list every painted component tested with an XRF reading (mg/cm2), the inspector's
positive/negative call, and the square feet of damaged paint. Each firm (ACER, Synertech,
Vertex, Viva EHS, BATTA) uses the same table, so rows are read by their common ending:
damaged square feet, reading, positive/negative. Summary per file: components tested, positive,
positive with damaged paint (the hazard the lead-safe certification addresses), and damaged
square feet on positive components. The firm's call is kept as published; firms differ in the
cutoff they cite (1.0 mg/cm2 is the federal level), so the count at or above 1.0 is also given.

Files are linked to schools by street address (folder name vs. the school's parcel address).
"""

import re
import subprocess
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import CORE, RAW
from .metrics import write_metric_part

ENV = RAW / "sdp_environmental"
# reading, lead call, and (ACER certification reports) a trailing asbestos status column
ROW_END = re.compile(
    r"\s([<>]?-?\d*\.?\d+|N/A)\s+(Positive|Negative|POS|NEG)"
    r"(?:\s+(?:Positive|Negative|Not Sampled|Trace\w*|N/A))?\s*$",
    re.IGNORECASE,
)
CELL = re.compile(r"^(-?\d*\.?\d+|N/A|Positive|Negative|POS|NEG)$", re.IGNORECASE)
MONTHS = "January February March April May June July August September October November December"
MONTH_DATE = re.compile(r"\b(" + "|".join(MONTHS.split()) + r")\s+(\d{1,2}),?\s+(20\d\d)\b")
FIRM = re.compile(r"Inspection Company:\s*([A-Za-z]+(?: EHS)?)")
DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
SUFFIX = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "ROAD": "RD",
    "PIKE": "PK",
    "PK": "PK",
    "LANE": "LN",
    "BOULEVARD": "BLVD",
    "DRIVE": "DR",
    "PLACE": "PL",
}


def pdf_text(path: Path, first: int | None = None, last: int | None = None) -> str:
    cmd = ["pdftotext", "-layout", "-q"]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    out = subprocess.run([*cmd, str(path), "-"], capture_output=True, text=True, check=False)
    return out.stdout


def xrf_rows(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        m = ROW_END.search(line)
        if not m:
            continue
        reading, call = m.groups()
        # Walk back over the numeric cells before the reading: the first is the damaged
        # square feet. Some layouts add paint-chip lab columns between the two.
        cells = line[: m.start()].split()
        k = len(cells)
        while k > 0 and CELL.match(cells[k - 1]):
            k -= 1
        qty = cells[k] if k < len(cells) else "N/A"
        rows.append(
            {
                "damaged_sf": float(qty) if re.match(r"^-?\d*\.?\d+$", qty) else None,
                # ">10" is above the analyzer's range: kept as 10
                "xrf": None if reading.upper() == "N/A" else float(reading.lstrip("<>")),
                "positive": call.upper().startswith("POS"),
            }
        )
    return pd.DataFrame(rows, columns=["damaged_sf", "xrf", "positive"])


def inspection_dates(text: str) -> tuple[str | None, str | None]:
    head = text[:6000]
    found = []
    for mon, dy, yr in MONTH_DATE.findall(head):
        found.append(f"{yr}-{MONTHS.split().index(mon) + 1:02d}-{int(dy):02d}")
    for mo, dy, yr in DATE.findall(head):
        y = int(yr) + (2000 if len(yr) == 2 else 0)
        if 1 <= int(mo) <= 12 and 1 <= int(dy) <= 31 and 2015 <= y <= 2030:
            found.append(f"{y:04d}-{int(mo):02d}-{int(dy):02d}")
    # ACER writes the period as (5-18-26-6-8-26)
    m = re.search(r"\((\d{1,2})-(\d{1,2})-(\d{2})-(\d{1,2})-(\d{1,2})-(\d{2})\)", head)
    if m:
        a = m.groups()
        found += [
            f"20{a[2]}-{int(a[0]):02d}-{int(a[1]):02d}",
            f"20{a[5]}-{int(a[3]):02d}-{int(a[4]):02d}",
        ]
    # certificates also print expiration dates; keep dates up to today
    found = [f for f in found if f <= datetime.now(UTC).date().isoformat()]
    return (min(found), max(found)) if found else (None, None)


def summarize_lead_file(path: Path) -> dict:
    text = pdf_text(path)
    x = xrf_rows(text)
    tested = x[x["xrf"].notna()]
    pos = x[x["positive"].astype(bool)]
    first, last = inspection_dates(text)
    firm = FIRM.search(text[:3000])
    return {
        "n_components_tested": len(tested),
        "n_positive": len(pos),
        "n_positive_damaged": int((pos["damaged_sf"].fillna(0) > 0).sum()),
        "positive_damaged_sf": float(pos["damaged_sf"].fillna(0).sum()),
        "n_xrf_ge_1": int((tested["xrf"] >= 1.0).sum()),
        "max_xrf": tested["xrf"].max() if len(tested) else None,
        "inspection_start": first,
        "inspection_end": last,
        "firm": firm.group(1).title() if firm else None,
    }


def doc_type(name: str) -> str:
    n = name.lower()
    for key, label in [
        ("assessment data", "assessment_data"),
        ("certification", "certification_report"),
        ("assessment report", "assessment_report"),
        ("exemption", "exemption"),
    ]:
        if key in n:
            return label
    return "other"


def norm_street(s: str) -> str:
    s = re.sub(r"[.,]", " ", str(s).upper())
    s = re.sub(r"\b(\d+)(ST|ND|RD|TH)\b", lambda m: f"{int(m.group(1)):02d}TH", s)
    s = re.sub(r"\b0?(\d)TH\b", r"0\1TH", s)
    words = [SUFFIX.get(w, w) for w in s.split()]
    words = [{"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}.get(w, w) for w in words]
    return " ".join(words)


def split_address(addr: str) -> tuple[int, int, str] | None:
    m = re.match(r"\s*(\d+)[A-Z]?(?:-(\d+))?\s+(.+)", str(addr).upper())
    if not m:
        return None
    lo, hi, street = int(m.group(1)), m.group(2), norm_street(m.group(3))
    if hi:  # 4901-31 means 4901 to 4931
        hi_full = int(str(lo)[: len(str(lo)) - len(hi)] + hi) if len(hi) < len(str(lo)) else int(hi)
        return lo, max(lo, hi_full), street
    return lo, lo, street


def _master_lists() -> pd.DataFrame:
    frames = []
    for path in sorted((RAW / "sdp_master_school_list").glob("*Master School List*.csv")):
        d = pd.read_csv(path, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
        d.columns = [c.strip() for c in d.columns]
        if "Street Address" in d:
            frames.append(d.assign(list_file=path.name))
    return pd.concat(frames, ignore_index=True)


def school_index() -> dict:
    """Street addresses and names, from the master lists (school addresses) and parcels."""
    reg = pd.read_csv(RAW.parent / "registry" / "school_id_registry.csv", dtype=str)
    to_id = reg.set_index("ulcs")["school_id"]
    m = _master_lists()
    m["school_id"] = m["ULCS Code"].str.strip().map(to_id)
    m = m.dropna(subset=["school_id"])
    m["list_sy"] = m["list_file"].str.extract(r"\d{4}-(\d{4})")[0].astype(int)
    master = []
    for sid, addr, sy in zip(m["school_id"], m["Street Address"], m["list_sy"], strict=True):
        a = split_address(addr)
        if a:
            master.append((*a, sid, sy))
    p = pd.read_parquet(CORE / "school_parcel.parquet")
    parcel = []
    for sid, addr, sy in zip(p["school_id"], p["parcel_address"], p["valid_to_sy"], strict=True):
        a = split_address(addr)
        if a:
            parcel.append((*a, sid, int(sy) if pd.notna(sy) else 0))
    names: dict[str, set] = {}
    current: dict[str, set] = {}  # names in the latest list, for partial matches
    latest = m["list_sy"].max()
    for col in ["Abbreviated Name", "Publication Name"]:
        for sid, name, sy in zip(m["school_id"], m[col], m["list_sy"], strict=True):
            names.setdefault(norm_name(name), set()).add(sid)
            if sy == latest:
                current.setdefault(sid, set()).add(norm_name(name))
    attr = pd.read_parquet(CORE / "school_year_attr.parquet")
    for sid, name in zip(attr["school_id"], attr["name"], strict=True):
        names.setdefault(norm_name(name), set()).add(sid)
    return {
        "master": sorted(set(master)),
        "parcel": sorted(set(parcel)),
        "names": names,
        "current": current,
    }


def match_name(variants: list[str], idx: dict, partial: bool = True) -> tuple[str | None, str]:
    """Exact matches on all but the last variant; the last (a bare surname) only partially."""
    for name in variants[:-1] or variants:
        hits = idx["names"].get(norm_name(name), set())
        if len(hits) == 1:
            return next(iter(hits)), "name"
    # a unique current school whose name contains every word of the last name
    words = set(norm_name(variants[-1]).split())
    if partial and words:
        hits = {
            sid for sid, ns in idx["current"].items() if any(words <= set(n.split()) for n in ns)
        }
        if len(hits) == 1:
            return hits.pop(), "name_partial"
    return None, "unmatched"


def norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Z ]", " ", s.upper())
    drop = {"SCHOOL", "ELEMENTARY", "MIDDLE", "HIGH", "THE", "ES", "MS", "HS", "OF", "AT"}
    return " ".join(w for w in s.split() if w not in drop and len(w) > 1)


def _hits(addr, index) -> set:
    """Schools at the address in the most recent year any school was listed there."""
    lo, hi, street = addr
    found = [
        (sy, sid) for plo, phi, pst, sid, sy in index if pst == street and plo <= hi and lo <= phi
    ]
    if not found:
        return set()
    latest = max(sy for sy, _ in found)
    return {sid for sy, sid in found if sy == latest}


def match_site(addr: str, name: str, idx: dict) -> tuple[str | None, str]:
    """One school_id, or several comma-separated when schools share the building."""
    a = split_address(addr)
    for key in ["master", "parcel"]:
        hits = _hits(a, idx[key]) if a else set()
        if len(hits) == 1:
            return hits.pop(), f"address_{key}"
        if len(hits) > 1:
            by_name = hits & idx["names"].get(norm_name(name), set())
            if len(by_name) == 1:
                return by_name.pop(), f"address_{key}_and_name"
            return ", ".join(sorted(hits)), f"address_{key}_shared_building"
    by_name = idx["names"].get(norm_name(name), set())
    if len(by_name) == 1:
        return next(iter(by_name)), "name"
    return None, "unmatched"


def folder_address(folder: str) -> str:
    """'Bridesburg_2824 Jenks St_19137' -> '2824 Jenks St'."""
    parts = folder.split("_")
    return parts[1] if len(parts) >= 3 else ""


def build_lead_paint() -> pd.DataFrame:
    idx = school_index()
    fixes = site_corrections()
    rows = []
    for path in sorted((ENV / "lead").rglob("*")):
        if not path.is_file():
            continue
        kind = doc_type(path.name)
        folder = path.relative_to(ENV / "lead").parts[0]
        sid, how = match_site(folder_address(folder), folder.split("_")[0], idx)
        if folder in fixes:
            sid, how = fixes[folder], "correction"
        row = {
            "school_id": sid,
            "link_method": how,
            "site_folder": folder,
            "file": str(path.relative_to(RAW.parent)),
            "doc_type": kind,
        }
        if kind in {"assessment_data", "assessment_report", "certification_report"}:
            row.update(summarize_lead_file(path))
        rows.append(row)
    d = pd.DataFrame(rows)
    d["sy"] = pd.to_datetime(d["inspection_end"], errors="coerce").map(
        lambda t: None if pd.isna(t) else t.year + (1 if t.month >= 7 else 0)
    )
    d["status"] = d["n_components_tested"].map(
        lambda n: "reported" if pd.notna(n) and n > 0 else "not_reported"
    )
    d["source_id"] = "sdp_environmental:lead"
    return d


LEAD_MEASURES = {
    "lead_paint_components_tested": "n_components_tested",
    "lead_paint_components_positive": "n_positive",
    "lead_paint_positive_damaged": "n_positive_damaged",
}
FULL_SURVEY_MIN = 200  # components; smaller files are follow-up checks of a few rooms


def lead_paint_metric(d: pd.DataFrame) -> pd.DataFrame:
    """Per school: the most recent full survey of each of its buildings, added together."""
    full = d[(d["n_components_tested"] >= FULL_SURVEY_MIN) & d["school_id"].notna()]
    full = full.dropna(subset=["sy"]).sort_values("inspection_end")
    latest = full.groupby("site_folder").tail(1).copy()
    latest["school_id"] = latest["school_id"].str.split(", ")
    latest = latest.explode("school_id")
    agg = latest.groupby("school_id").agg(
        sy=("sy", "max"), **{m: (c, "sum") for m, c in LEAD_MEASURES.items()}
    )
    out = agg.reset_index().melt(["school_id", "sy"], var_name="measure_id", value_name="value")
    return out.assign(
        sy=lambda t: t["sy"].astype(int),
        student_group="all",
        status="reported",
        source_id="sdp_environmental:lead",
    )


def write_lead_paint(d: pd.DataFrame) -> pd.DataFrame:
    d.to_parquet(CORE / "school_lead_paint.parquet", index=False)
    d.to_csv(CORE / "school_lead_paint.csv", index=False)
    return write_metric_part("env_lead", lead_paint_metric(d))


# Water: one row per outlet sample. "<1.0" is below the reporting limit (kept as a
# censored value), "J" marks an estimate below the limit; AA/BA is above/below the
# district's 10 ppb action level.
WATER_ROW = re.compile(
    r"^\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+(\S+)\s+(\S+)\s+([A-Z]{2})\b(.*?)\s"
    r"(<?\d+(?:\.\d+)?)\s*(J?)\s+(\d+(?:\.\d+)?)\s+(AA|BA)\s*$"
)
# follow-up letters: same columns, then the corrective action in words instead of AA/BA
WATER_FOLLOW_UP_ROW = re.compile(
    r"^\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+(\S+)\s+(\S+)\s+([A-Z]{2})\b(.*?)\s"
    r"(<?\d+(?:\.\d+)?)\s*(J?)\s+(\d+(?:\.\d+)?)(?:\s+(\S.*?))?\s*$"
)
WATER_ACTION_PPB = 10
STATED_TESTED = re.compile(
    r"There were (?:[A-Za-z-]+ )*\(?(\d+)\)? (?:water )?outlets tested"
    r"|\(?(\d+)\)? (?:water )?outlets (?:at your school )?were (?:initially )?tested"
)
STATED_ABOVE = re.compile(
    r"(?:\((\d+)\)|(\d+)) (?:water )?outlets? (?:was|were) found to have results above"
)


def stated_counts(text: str) -> tuple[int | None, int | None]:
    """Outlets tested and above the action level, as the letter states them in words."""
    t = " ".join(text.split())
    m, a = STATED_TESTED.search(t), STATED_ABOVE.search(t)
    tested = int(m.group(1) or m.group(2)) if m else None
    above = int(a.group(1) or a.group(2)) if a else None
    if above is None and "No water outlets were found" in t:
        above = 0
    return tested, above


def water_rows(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        m = WATER_ROW.match(line) or WATER_FOLLOW_UP_ROW.match(line)
        if not m:
            continue
        when, floor, outlet, otype, desc, result, j, pql, action = m.groups()
        corrective = None
        if action not in {"AA", "BA"}:
            corrective, action = action, None
        mo, dy, yr = when.split("/")
        yr = int(yr) + (2000 if len(yr) == 2 else 0)
        rows.append(
            {
                "sample_date": f"{yr:04d}-{int(mo):02d}-{int(dy):02d}",
                "floor": floor,
                "outlet": outlet,
                "outlet_type": otype,
                "outlet_description": " ".join(desc.split()) or None,
                "lead_ppb": float(result.lstrip("<")),
                "below_reporting_limit": result.startswith("<"),
                "estimated": j == "J",
                "reporting_limit_ppb": float(pql),
                "above_action_level": action == "AA"
                if action
                else (not result.startswith("<") and float(result) > WATER_ACTION_PPB),
                "corrective_action": corrective,
            }
        )
    return pd.DataFrame(rows)


def water_site_name(folder: str) -> list[str]:
    """Name variants for a water folder like 'Comegys, Benjamin Site 1_SW43CBB1'."""
    base = re.sub(
        r"\s*Site \d+.*$|_[A-Z]{1,2}-?\d{2}[A-Z0-9]+$|\s[A-Z]{1,2}-?\d{2}[A-Z]{3}\d$", "", folder
    )
    base = base.split("(")[0].strip()
    out = [base]
    if "," in base:
        last, first = [p.strip() for p in base.split(",", 1)]
        out += [f"{first} {last}", last]
    return out


def site_corrections() -> dict[str, str]:
    c = pd.read_csv(RAW.parent / "corrections" / "env_site_school.csv", dtype=str)
    return dict(zip(c["site_folder"], c["school_id"], strict=True))


def letter_school_name(filename: str) -> str:
    """'Childs ES Follow Up Water Results Letter 9.28.2025.docx.pdf' -> 'Childs'."""
    stem = re.split(r"\s+(?:Follow|Lead|Water|Elementary Water)\b", filename, maxsplit=1)[0]
    return re.sub(r"\b(ES|MS|HS|and LSH|and Annex|Building)\b", " ", stem).strip()


def _sha_by_path() -> dict[str, str]:
    from .fetch import read_downloads

    return {r["local_path"]: r["sha256"] for r in read_downloads()}


def build_water() -> pd.DataFrame:
    idx = school_index()
    fixes = site_corrections()
    sha = _sha_by_path()
    seen: set[str] = set()
    frames = []
    # site folders first, so a letter posted in both trees keeps its site copy
    paths = sorted((ENV / "water").rglob("*"), key=lambda p: ("Search by Site" not in str(p), p))
    for path in paths:
        if not path.is_file():
            continue
        digest = sha.get(str(path.relative_to(RAW.parent)))
        if digest in seen:
            continue  # the same letter posted in two folders
        seen.add(digest or str(path))
        folder = path.parent.name
        if "archive" in folder.lower():
            continue  # superseded results
        sid, how = None, "unmatched"
        street = re.search(r"\((\d+[^)]*)\)", folder)  # e.g. (5741 North Rising Sun Avenue)
        if street:
            sid, how = match_site(street.group(1), letter_school_name(path.name), idx)
        if sid is None:
            letter = letter_school_name(path.name)
            sid, how = match_name([letter, letter], idx)
        if sid is None:
            # building names are often a former school's: exact matches only
            sid, how = match_name(water_site_name(folder), idx, partial=False)
        if folder in fixes:
            sid, how = fixes[folder], "correction"
        text = pdf_text(path)
        rows = water_rows(text)
        stated_tested, stated_above = stated_counts(text)
        if rows.empty:
            rows = pd.DataFrame([{"sample_date": None}])
        frames.append(
            rows.assign(
                school_id=sid,
                link_method=how,
                site_folder=folder,
                file=str(path.relative_to(RAW.parent)),
                follow_up=bool(re.search(r"follow[\s-]*up", path.name, re.IGNORECASE)),
                letter_outlets_tested=stated_tested,
                letter_outlets_above=stated_above,
            )
        )
    d = pd.concat(frames, ignore_index=True)
    d["status"] = d["lead_ppb"].map(lambda v: "reported" if pd.notna(v) else "not_reported")
    d["source_id"] = "sdp_environmental:water"
    return d


WATER_MEASURES = {
    "water_outlets_tested": "tested",
    "water_outlets_above_action": "above",
}


def water_metric(d: pd.DataFrame) -> pd.DataFrame:
    """Per school: the latest initial test letter of each of its sites, added together.

    Counts are the letter's own stated totals where it states them (some table rows wrap and
    cannot be read); otherwise the parsed rows."""
    init = d[~d["follow_up"] & d["lead_ppb"].notna() & d["school_id"].notna()].copy()
    per_file = init.groupby(["site_folder", "file", "school_id"], as_index=False).agg(
        last_sample=("sample_date", "max"),
        tested=("outlet", "count"),
        above=("above_action_level", "sum"),
        letter_tested=("letter_outlets_tested", "first"),
        letter_above=("letter_outlets_above", "first"),
    )
    per_file["tested"] = per_file["letter_tested"].fillna(per_file["tested"])
    per_file["above"] = per_file["letter_above"].fillna(per_file["above"])
    latest = per_file.sort_values("last_sample").groupby("site_folder").tail(1)
    latest["school_id"] = latest["school_id"].str.split(", ")
    latest = latest.explode("school_id")
    latest["sy"] = pd.to_datetime(latest["last_sample"]).map(
        lambda t: t.year + (1 if t.month >= 7 else 0)
    )
    agg = latest.groupby("school_id").agg(
        sy=("sy", "max"), **{m: (c, "sum") for m, c in WATER_MEASURES.items()}
    )
    out = agg.reset_index().melt(["school_id", "sy"], var_name="measure_id", value_name="value")
    return out.assign(student_group="all", status="reported", source_id="sdp_environmental:water")


def write_water(d: pd.DataFrame) -> pd.DataFrame:
    d.to_parquet(CORE / "school_water_lead.parquet", index=False)
    d.to_csv(CORE / "school_water_lead.csv", index=False)
    return write_metric_part("env_water", water_metric(d))
