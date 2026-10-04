"""The `source` table: one row per source id used, joined to what we actually archived."""

import pandas as pd

from . import SOURCES, spring_year
from .fetch import read_downloads
from .identity import LONGITUDINAL_SOURCE_ID


def _latest_download(downloads: list[dict], matcher) -> dict:
    found = [d for d in downloads if matcher(d["local_path"].split("/")[-1])]
    found.sort(key=lambda d: d["local_path"].endswith(".csv"))  # prefer CSV over xlsx
    return found[-1] if found else {}


def build_source(source_ids: list[str]) -> pd.DataFrame:
    manifest = pd.read_csv(SOURCES / "manifest.csv", dtype=str)
    m = manifest[manifest["source_key"] == "sdp_master_school_list"].iloc[0]
    downloads = [d for d in read_downloads() if d["source_key"] == "sdp_master_school_list"]
    rows = []
    for sid in sorted(source_ids):
        if sid == LONGITUDINAL_SOURCE_ID:
            sy = None
            hit = _latest_download(downloads, lambda n: n.startswith("Longitudinal"))
        else:
            sy = int(sid.rsplit("sy", 1)[1])
            hit = _latest_download(
                downloads, lambda n, sy=sy: "Master School List" in n and spring_year(n) == sy
            )
        rows.append(
            {
                "source_id": sid,
                "source_key": "sdp_master_school_list",
                "publisher": m["publisher"],
                "sy": sy,
                "url": hit.get("url", ""),
                "local_path": hit.get("local_path", ""),
                "sha256": hit.get("sha256", ""),
                "retrieved_at_utc": hit.get("retrieved_at_utc", ""),
                "license": m["license"],
                "note": "" if hit else "raw file not archived",
            }
        )
    return pd.DataFrame(rows)
