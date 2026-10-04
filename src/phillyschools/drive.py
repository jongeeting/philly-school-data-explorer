"""Catalog files in public Google Drive folders (the district posts environmental records there).

Uses Drive's public embedded folder view: no login, no API key. Each file becomes a row in
sources/files.csv with `subdir` set to its folder path, so `psd fetch` can archive it.
"""

import html
import re
import time

import requests

from . import USER_AGENT
from .discover import file_row, read_files_catalog, write_files_catalog

FOLDER_VIEW = "https://drive.google.com/embeddedfolderview?id={}"
FILE_DOWNLOAD = "https://drive.google.com/uc?export=download&id={}"
ENTRY = re.compile(
    r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?'
    r'<div class="flip-entry-title">(.*?)</div>',
    re.DOTALL,
)


def safe_name(name: str) -> str:
    return re.sub(r"[/\\:]+", "-", html.unescape(name)).strip()


def list_folder(session: requests.Session, folder_id: str) -> list[tuple[str, str, str]]:
    """(id, title, kind) for each entry; kind is 'folder' or 'file'."""
    resp = session.get(FOLDER_VIEW.format(folder_id), timeout=60)
    resp.raise_for_status()
    out = []
    for entry_id, href, title in ENTRY.findall(resp.text):
        kind = "folder" if "/folders/" in href else "file"
        out.append((entry_id, html.unescape(title).strip(), kind))
    return out


def catalog_drive(
    source_key: str, folder_id: str, prefix: str, pause: float = 0.5, max_depth: int = 4
) -> list[dict]:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    from datetime import UTC, datetime

    today = datetime.now(UTC).date().isoformat()
    found: list[dict] = []
    stack = [(folder_id, prefix, 0)]
    while stack:
        fid, path, depth = stack.pop()
        for entry_id, title, kind in list_folder(session, fid):
            if kind == "folder" and depth < max_depth:
                stack.append((entry_id, f"{path}/{safe_name(title)}", depth + 1))
            elif kind == "file":
                row = file_row(source_key, FILE_DOWNLOAD.format(entry_id), today)
                row.update(filename=safe_name(title), subdir=path, ext=_ext(title))
                found.append(row)
        time.sleep(pause)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in found:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())
    return found


def _ext(title: str) -> str:
    m = re.search(r"(\.[A-Za-z0-9]{2,5})$", title)
    return m.group(1).lower() if m else ""
