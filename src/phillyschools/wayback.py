"""Catalog files that survive only in the Internet Archive's Wayback Machine.

Uses the public CDX API. Each original URL is cataloged once, at its latest successful
capture, with the raw-bytes form of the capture URL (`id_`), so the archived file is exactly
what the district published.
"""

import html
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import requests

from . import USER_AGENT
from .discover import file_row, read_files_catalog, write_files_catalog

CDX = "https://web.archive.org/cdx/search/cdx"


def cdx_list(url_prefix: str, mimetype: str = "application/pdf") -> list[tuple[str, str]]:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    resp = session.get(
        CDX,
        params={
            "url": url_prefix,
            "matchType": "prefix",
            "output": "json",
            "filter": ["statuscode:200", f"mimetype:{mimetype}"],
            "fl": "timestamp,original",
            "collapse": "urlkey",
        },
        timeout=120,
    )
    resp.raise_for_status()
    rows = resp.json()
    return [(ts, orig) for ts, orig in rows[1:]] if rows else []


def catalog_wayback(source_key: str, url_prefix: str, subdir: str) -> list[dict]:
    today = datetime.now(UTC).date().isoformat()
    found = []
    for ts, original in cdx_list(url_prefix):
        url = f"https://web.archive.org/web/{ts}id_/{original}"
        row = file_row(source_key, url, today)
        path = PurePosixPath(unquote(urlparse(original).path))
        # keep the site's upload folders (e.g. 2017/06) so same-named files do not collide
        parts = path.parts
        sub = "/".join(p for p in parts[-3:-1] if p) if len(parts) > 3 else ""
        row.update(
            subdir=f"{subdir}/{sub}".rstrip("/"), wayback_timestamp=ts, original_url=original
        )
        found.append(row)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in found:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())
    return found


DRIVE_LINK = re.compile(
    r'<a[^>]+href="[^"]*drive\.google\.com/file/d/([A-Za-z0-9_-]+)[^"]*"[^>]*>(.*?)</a>', re.DOTALL
)


def catalog_drive_links_on_archived_page(source_key: str, page_url: str, subdir: str) -> list[dict]:
    """Catalog Drive files linked from the latest archived copy of a (possibly deleted) page."""
    from .drive import FILE_DOWNLOAD, safe_name

    captures = cdx_list(page_url, mimetype="text/html")
    if not captures:
        raise ValueError(f"no archived capture of {page_url}")
    ts, original = captures[-1]
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    resp = session.get(f"https://web.archive.org/web/{ts}id_/{original}", timeout=120)
    resp.raise_for_status()
    today = datetime.now(UTC).date().isoformat()
    found = []
    for file_id, text in DRIVE_LINK.findall(resp.text):
        label = safe_name(re.sub(r"<[^>]+>", "", html.unescape(text)))
        row = file_row(source_key, FILE_DOWNLOAD.format(file_id), today)
        row.update(
            filename=f"{label} [{file_id[:8]}].pdf",
            ext=".pdf",
            subdir=subdir,
            wayback_timestamp=ts,
            original_url=original,
        )
        found.append(row)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in found:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())
    return found
