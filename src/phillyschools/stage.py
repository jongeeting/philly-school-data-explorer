"""Stage raw SDP master school lists into one table (one row per listed school per school year).

Sources, in raw/sdp_master_school_list/:
  - Longitudinal School List (2001-02 to 2016-17): xlsx, upper-case vocabulary, no AUN or NCES
  - 2017-18 list: xlsx only, header cells contain line breaks
  - 2018-19 onward: CSV (some also xlsx). CSVs saved NCES codes in scientific notation in some
    years, destroying them; the xlsx sibling is used to repair those when it exists.

Vocabulary (governance, level, admission) is normalized to the modern list style so that a
change at an era boundary is never mistaken for a real change.
"""

import re

import pandas as pd

from . import RAW, STAGING, spring_year

SRC = RAW / "sdp_master_school_list"
LONGITUDINAL = SRC / "Longitudinal School List (20171128).xlsx"
LEVELS = {
    "elementary": "Elementary",
    "middle": "Middle",
    "high": "High",
    "elementarymiddle": "Elementary-Middle",
    "middlehigh": "Middle-High",
    "elementarymiddlehigh": "Elementary-Middle-High",
}
NCES_OK = re.compile(r"^\d{12}$")
OUT_COLUMNS = [
    "year",
    "aun",
    "schl",
    "ulcs",
    "src_id",
    "nces",
    "nces_source",
    "name",
    "governance",
    "category",
    "level",
    "admission",
    "council_district",
    "gps",
    "year_opened",
    "year_closed_sy",
    "school_key",
    "source_file",
]


def clean_id(value) -> str | None:
    s = str(value).strip()
    if s in ("", "nan", "None"):
        return None
    return re.sub(r"\.0$", "", s)


def canon_level(value) -> str | None:
    if pd.isna(value):
        return None
    key = re.sub(r"[^a-z]", "", str(value).lower())
    return LEVELS.get(key, str(value).strip())


def canon_text(value) -> str | None:
    """Title-case vocabulary (DISTRICT -> District); None for blanks."""
    if pd.isna(value) or not str(value).strip():
        return None
    return str(value).strip().title()


def parse_year(value) -> int | None:
    m = re.search(r"(1[89]|20)\d{2}", str(value))
    return int(m.group(0)) if m else None


def parse_year_closed(value) -> int | None:
    """'open' -> None; '2012-2013' -> 2013 (spring year of the last year open)."""
    if pd.isna(value) or str(value).strip().lower() == "open":
        return None
    return spring_year(str(value)) or parse_year(value)


def _normalize_columns(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
    return d


def _read_csv(path) -> pd.DataFrame:
    return _normalize_columns(
        pd.read_csv(path, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    )


def _read_xlsx_list(path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    sheet = next(s for s in xl.sheet_names if s.lower() != "user guide")
    return _normalize_columns(xl.parse(sheet, dtype=str))


def _from_list_frame(d: pd.DataFrame, sy: int, source_file: str) -> pd.DataFrame:
    nces = d["NCES Code"].map(clean_id)
    nces = nces.where(nces.fillna("").str.match(NCES_OK))  # drops 4.21899E+11 and other damage
    out = pd.DataFrame(
        {
            "year": sy,
            "aun": d["AUN Code"].map(clean_id),
            "schl": d["PA Code"].map(clean_id),
            "ulcs": d["ULCS Code"].map(clean_id),
            "src_id": d["SRC School ID"].map(clean_id),
            "nces": nces,
            "nces_source": nces.map(lambda v: None if v is None or pd.isna(v) else "reported"),
            "name": d["Publication Name"].str.strip(),
            "governance": d["Governance"].map(canon_text),
            "category": d["School Reporting Category"].str.strip(),
            "level": d["School Level"].map(canon_level),
            "admission": d["Admission Type"].map(canon_text),
            "council_district": d["City Council District"],
            "gps": d["GPS Location"],
            "year_opened": d["Year Opened"].map(parse_year),
            "year_closed_sy": None,
            "source_file": source_file,
        }
    )
    return out


def repair_nces(csv_part: pd.DataFrame, xlsx_part: pd.DataFrame) -> pd.DataFrame:
    """Fill NCES codes the CSV lost, from the same list's xlsx (matched on ULCS)."""
    good = xlsx_part.dropna(subset=["nces"]).drop_duplicates("ulcs").set_index("ulcs")["nces"]
    fixed = csv_part.copy()
    missing = fixed["nces"].isna() & fixed["ulcs"].isin(good.index)
    fixed.loc[missing, "nces"] = fixed.loc[missing, "ulcs"].map(good)
    fixed.loc[missing, "nces_source"] = "xlsx"
    return fixed


def bridge_nces(d: pd.DataFrame) -> pd.DataFrame:
    """Fill a missing NCES only when the same school's nearest earlier and later codes agree.

    Labeled `bridged` so it is never mistaken for a reported value.
    """
    d = d.sort_values(["ulcs", "year"]).copy()
    prev = d.groupby("ulcs")["nces"].ffill()
    nxt = d.groupby("ulcs")["nces"].bfill()
    fill = d["nces"].isna() & prev.notna() & (prev == nxt)
    d.loc[fill, "nces"] = prev[fill]
    d.loc[fill, "nces_source"] = "bridged"
    return d


def stage_lists() -> pd.DataFrame:
    parts = []
    for path in sorted(SRC.glob("*Master School List*.csv")):
        sy = spring_year(path.name)
        part = _from_list_frame(_read_csv(path), sy, path.name)
        sibling = path.with_suffix(".xlsx")
        if sibling.exists():
            x = _from_list_frame(_read_xlsx_list(sibling), sy, sibling.name)
            part = repair_nces(part, x)
        parts.append(part)
    for path in sorted(SRC.glob("*Master School List*.xlsx")):
        sy = spring_year(path.name)
        if not path.with_suffix(".csv").exists():  # xlsx-only years (2017-18)
            parts.append(_from_list_frame(_read_xlsx_list(path), sy, path.name))
    return pd.concat(parts, ignore_index=True)


def stage_longitudinal() -> pd.DataFrame:
    d = _normalize_columns(pd.read_excel(LONGITUDINAL, sheet_name="Sheet1", dtype=str))
    closed = d["Year Closed"].map(parse_year_closed)
    return pd.DataFrame(
        {
            "year": d["School Year"].map(spring_year),
            "aun": None,
            "schl": d["PA Code"].map(clean_id),
            "ulcs": d["ULCS Code"].map(clean_id),
            "src_id": d["SRC School ID"].map(clean_id),
            "nces": None,
            "nces_source": None,
            "name": d["Publication Name"].str.strip(),
            "governance": d["Governance"].map(canon_text),
            "category": None,
            "level": d["School Level"].map(canon_level),
            "admission": d["Admission Type"].map(canon_text),
            "council_district": d["School Year City Council District"],
            "gps": None,
            "year_opened": d["Year Opened"].map(parse_year),
            "year_closed_sy": closed,
            "source_file": LONGITUDINAL.name,
        }
    )


def stage_sdp_master_lists() -> pd.DataFrame:
    out = pd.concat([stage_longitudinal(), stage_lists()], ignore_index=True)
    out = bridge_nces(out)
    out["school_key"] = (out["aun"] + "-" + out["schl"]).where(
        out["aun"].notna() & out["schl"].notna()
    )
    out = out[out["ulcs"].notna() & (out["schl"].notna() | out["aun"].isna())]
    out["year_closed_sy"] = pd.to_numeric(out["year_closed_sy"], errors="coerce").astype("Int64")
    out["year_opened"] = pd.to_numeric(out["year_opened"], errors="coerce").astype("Int64")
    out["year"] = out["year"].astype(int)
    return out[OUT_COLUMNS].sort_values(["year", "ulcs"]).reset_index(drop=True)


def write_staging() -> pd.DataFrame:
    STAGING.mkdir(exist_ok=True)
    out = stage_sdp_master_lists()
    out.to_parquet(STAGING / "sdp_master_school_list.parquet", index=False)
    return out
