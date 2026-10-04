"""Find downloadable files linked from each source's landing page.

Writes sources/files.csv, a reviewed catalog of file URLs. Nothing is downloaded here
except the landing pages themselves.
"""

import csv
import html
import re
import time
from datetime import UTC, datetime
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlparse

import requests

from . import SOURCES, USER_AGENT, spring_year

FILE_EXTENSIONS = {".csv", ".xlsx", ".xls", ".zip", ".geojson", ".pdf", ".json"}
# Only follow file links on publisher hosts; never an arbitrary third party.
ALLOWED_HOSTS = {
    "cdn.philasd.org",
    "www.philasd.org",
    "opendataphilly.org",
    "futurereadypa.org",
    "www.futurereadypa.org",
    "www.pa.gov",
    "www.education.pa.gov",
    "www.census.gov",
    "www2.census.gov",
    "services.arcgis.com",
    "raw.githubusercontent.com",
    "drive.google.com",
    "drive.usercontent.google.com",
    "web.archive.org",
    "philasd.primegov.com",
    "philasd.novusagenda.com",
}
FILES_FIELDS = [
    "source_key",
    "url",
    "filename",
    "ext",
    "sy",
    "discovered_on",
    "subdir",
    "wayback_timestamp",
    "original_url",
]
HREF = re.compile(r'href\s*=\s*"([^"]+)"', re.IGNORECASE)


def extract_file_links(page_html: str, base_url: str) -> list[str]:
    """Absolute, de-duplicated file URLs in page order, on allowed hosts only."""
    seen: dict[str, None] = {}
    for raw in HREF.findall(page_html):
        url = urljoin(base_url, html.unescape(raw).strip())
        parsed = urlparse(url)
        ext = PurePosixPath(unquote(parsed.path)).suffix.lower()
        if ext in FILE_EXTENSIONS and parsed.hostname in ALLOWED_HOSTS:
            seen.setdefault(url, None)
    return list(seen)


def file_row(source_key: str, url: str, today: str) -> dict:
    name = PurePosixPath(unquote(urlparse(url).path)).name
    upload = re.search(r"/uploads/(?:sites/\d+/)?(\d{4}/\d{2})/", url)
    return {
        "source_key": source_key,
        "url": url,
        "subdir": upload.group(1) if upload else "",
        "filename": name,
        "ext": PurePosixPath(name).suffix.lower(),
        "sy": spring_year(name) or "",
        "discovered_on": today,
    }


def read_manifest() -> list[dict]:
    with open(SOURCES / "manifest.csv", newline="") as f:
        return list(csv.DictReader(f))


def read_files_catalog() -> list[dict]:
    path = SOURCES / "files.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def discover(source_keys: list[str] | None = None, pause: float = 1.0) -> list[dict]:
    """Scan landing pages and merge new links into sources/files.csv (existing rows kept)."""
    today = datetime.now(UTC).date().isoformat()
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    scanned: dict[str, list[str]] = {}
    for src in read_manifest():
        key, page = src["source_key"], src["url"]
        if source_keys and key not in source_keys:
            continue
        if page not in scanned:  # several sources share one landing page
            resp = session.get(page, timeout=60)
            resp.raise_for_status()
            scanned[page] = extract_file_links(resp.text, page)
            time.sleep(pause)
        for url in scanned[page]:
            if _belongs(key, url):
                catalog.setdefault((key, url), file_row(key, url, today))
    write_files_catalog(catalog.values())
    return list(catalog.values())


# Landing pages list many datasets. A link belongs to a source when its folder or file name
# matches the source's hint; sources without a hint take every link from their own page.
PATH_HINTS = {
    "sdp_master_school_list": ["School_List/"],
    "sdp_enrollment": ["Enrollment_Demographics_School/"],
    "sdp_catchments": ["School_Catchment/"],
    "sdp_data_terms": ["Terms-of-Use"],
    "sdp_goals_guardrails": ["Goals_Guardrails", "Goals-Guardrails", "Guardrails"],
    "sdp_spree": ["SPR", "School_Progress"],
    "sdp_pssa_keystone": ["PSSA", "Keystone"],
    "sdp_pses": ["Survey", "PSES"],
    "sdp_board_wordpress": ["schoolboard/wp-content/uploads"],
}


def _belongs(source_key: str, url: str) -> bool:
    hints = PATH_HINTS.get(source_key)
    if hints is None:
        return False  # no rule yet: add a hint after reviewing the page, to avoid mis-filing
    return any(h.lower() in url.lower() for h in hints)


def add_file(source_key: str, url: str) -> dict:
    """Catalog one direct file URL (for publishers with no landing page to scan)."""
    if urlparse(url).hostname not in ALLOWED_HOSTS:
        raise ValueError(f"host not in ALLOWED_HOSTS: {url}")
    if source_key not in {r["source_key"] for r in read_manifest()}:
        raise ValueError(f"unknown source_key {source_key}; add it to sources/manifest.csv first")
    today = datetime.now(UTC).date().isoformat()
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    row = catalog.setdefault((source_key, url), file_row(source_key, url, today))
    write_files_catalog(catalog.values())
    return row


def write_files_catalog(rows) -> None:
    rows = sorted(rows, key=lambda r: (r["source_key"], r.get("subdir") or "", r["url"]))
    with open(SOURCES / "files.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FILES_FIELDS, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
