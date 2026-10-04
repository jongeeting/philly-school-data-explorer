"""Stage raw SDP master school lists into one table (one row per listed school per school year).

Reads the CSV versions in raw/sdp_master_school_list/. The 2017-18 list (xlsx only, different
layout) and the 2017 Longitudinal List are handled separately.
"""

import re

import pandas as pd

from . import RAW, STAGING, spring_year

SRC = RAW / "sdp_master_school_list"


def clean_id(value) -> str | None:
    s = str(value).strip()
    if s in ("", "nan", "None"):
        return None
    return re.sub(r"\.0$", "", s)


def _read_list(path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    d.columns = [c.strip() for c in d.columns]
    return d


def stage_sdp_master_lists() -> pd.DataFrame:
    frames = []
    for path in sorted(SRC.glob("*Master School List*.csv")):
        sy = spring_year(path.name)
        d = _read_list(path)
        frames.append(
            pd.DataFrame({
                "year": sy,
                "aun": d["AUN Code"].map(clean_id),
                "schl": d["PA Code"].map(clean_id),
                "ulcs": d["ULCS Code"].map(clean_id),
                "src_id": d["SRC School ID"].map(clean_id),
                "nces": d["NCES Code"].map(clean_id),
                "name": d["Publication Name"].str.strip(),
                "governance": d["Governance"].str.strip(),
                "category": d["School Reporting Category"].str.strip(),
                "level": d.get("School Level"),
                "admission": d.get("Admission Type"),
                "council_district": d.get("City Council District"),
                "gps": d.get("GPS Location"),
                "source_file": path.name,
            })
        )
    out = pd.concat(frames, ignore_index=True)
    # Some CSVs saved NCES codes in scientific notation (4.21899E+11): unusable, treat as missing.
    out.loc[out["nces"].fillna("").str.contains("E", case=False), "nces"] = None
    out["school_key"] = out["aun"] + "-" + out["schl"]
    out = out[out["aun"].notna() & out["schl"].notna() & out["ulcs"].notna()]
    return out.reset_index(drop=True)


def write_staging() -> pd.DataFrame:
    STAGING.mkdir(exist_ok=True)
    out = stage_sdp_master_lists()
    out.to_parquet(STAGING / "sdp_master_school_list.parquet", index=False)
    return out
