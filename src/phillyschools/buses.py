"""Archive the district's daily canceled/late bus lists (no public history exists).

The transportation page embeds published Google Sheets. Only the sheets with a
"RUN #" header (the delay lists) are saved; the others are staff contact sheets
with names of individual employees, which this repo does not keep.
"""

import hashlib
import re
from datetime import UTC, datetime

import requests

from . import RAW, USER_AGENT
from .fetch import append_download

SOURCE = "sdp_transportation_late_buses"
PAGE = "https://www.philasd.org/transportation/"
SHEET = re.compile(r"https://docs\.google\.com/spreadsheets/d/e/([\w-]+)/pubhtml")


def _save(directory, name, stamp, content, url, now, resp):
    path = directory / f"{stamp}_{name}"
    path.write_bytes(content)
    append_download(
        {
            "source_key": SOURCE,
            "url": url,
            "local_path": str(path.relative_to(RAW.parent)),
            "retrieved_at_utc": now.isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
            "etag": resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
        }
    )
    return path


def snapshot_late_buses() -> list:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    directory = RAW / SOURCE / "snapshots"
    directory.mkdir(parents=True, exist_ok=True)
    page = session.get(PAGE, timeout=60)
    page.raise_for_status()
    saved = [_save(directory, "page.html", stamp, page.content, PAGE, now, page)]
    for i, sheet_id in enumerate(dict.fromkeys(SHEET.findall(page.text)), 1):
        url = f"https://docs.google.com/spreadsheets/d/e/{sheet_id}/pub?output=csv"
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        if b"RUN #" not in resp.content:
            continue
        saved.append(_save(directory, f"sheet{i}.csv", stamp, resp.content, url, now, resp))
    return saved
