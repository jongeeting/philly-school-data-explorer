"""The `source` table: one row per upstream dataset-year, joined to what we actually archived."""

import pandas as pd

from . import SOURCES, spring_year
from .fetch import read_downloads


def build_source(identity_years: list[int]) -> pd.DataFrame:
    manifest = pd.read_csv(SOURCES / "manifest.csv", dtype=str)
    downloads = read_downloads()
    rows = []
    for sy in identity_years:
        sid = f"sdp_master_school_list:sy{sy}"
        match = [
            d
            for d in downloads
            if d["source_key"] == "sdp_master_school_list"
            and spring_year(d["local_path"].split("/")[-1]) == sy
            and d["local_path"].endswith(".csv")
        ]
        m = manifest[manifest["source_key"] == "sdp_master_school_list"].iloc[0]
        last = match[-1] if match else {}
        rows.append(
            {
                "source_id": sid,
                "source_key": "sdp_master_school_list",
                "publisher": m["publisher"],
                "sy": sy,
                "url": last.get("url", ""),
                "local_path": last.get("local_path", ""),
                "sha256": last.get("sha256", ""),
                "retrieved_at_utc": last.get("retrieved_at_utc", ""),
                "license": m["license"],
                "note": "" if match else "raw file not yet archived; staged from prototype output",
            }
        )
    return pd.DataFrame(rows)
