"""Future Ready PA Index (PDE): school performance data files, 2017-18 on.

The site serves files as /home/getdatafile?id=N; the real file name comes from the
Content-Disposition header, so the catalog records it explicitly.
"""

import re
import time
from datetime import UTC, datetime

import requests

from . import USER_AGENT, spring_year
from .discover import file_row, read_files_catalog, write_files_catalog

SITE = "https://futurereadypa.org"
PAGE = f"{SITE}/Home/DataFiles"
SOURCE_KEYS = {
    "Datafile_": "pde_future_ready",
    "SchoolFastFacts": "pde_fast_facts",
    "DistrictFastFacts": "pde_district_fast_facts",
    "School Fiscal Data": "pde_school_fiscal",
    "District Fiscal Data": "pde_district_fiscal",
}


def _served_name(resp: requests.Response) -> str | None:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename="?([^";]+)"?', cd)
    return m.group(1).strip() if m else None


def catalog_future_ready(pause: float = 0.5) -> list[dict]:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    page = s.get(PAGE, timeout=60)
    page.raise_for_status()
    ids = sorted({int(i) for i in re.findall(r"getdatafile\?id=(\d+)", page.text)})
    today = datetime.now(UTC).date().isoformat()
    rows = []
    for i in ids:
        url = f"{SITE}/home/getdatafile?id={i}"
        head = s.head(url, allow_redirects=True, timeout=60)
        name = _served_name(head)
        time.sleep(pause)
        if not name:
            continue
        key = next((k for prefix, k in SOURCE_KEYS.items() if name.startswith(prefix)), None)
        if key is None:
            continue
        row = file_row(key, url, today)
        sy = spring_year(name) or _compact_year(name)
        # the oldest Fast Facts files have no year in the name: they are SY 2017-18
        if sy is None and "FastFacts" in name:
            sy = 2018
        row.update(
            filename=name if sy is None else _with_year(name, sy),
            ext=".xlsx",
            sy=sy or "",
            subdir="",
        )
        rows.append(row)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in rows:
        catalog[(r["source_key"], r["url"])] = r
    write_files_catalog(catalog.values())
    return rows


def _compact_year(name: str) -> int | None:
    m = re.search(r"_(20\d{2})(20\d{2})", name)
    return int(m.group(2)) if m else None


def _with_year(name: str, sy: int) -> str:
    if re.search(r"20\d{2}", name):
        return name
    stem, ext = name.rsplit(".", 1)
    return f"{stem}_{sy - 1}{sy}.{ext}"
