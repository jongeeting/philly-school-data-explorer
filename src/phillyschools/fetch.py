"""Download cataloged files into raw/ untouched, and record URL, time, and SHA-256.

raw/ is never edited. If a file changes upstream (the district does repost files), the new
version is saved beside the old one and both stay in sources/downloads.csv.
"""

import csv
import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from . import RAW, SOURCES, USER_AGENT
from .discover import read_files_catalog

DOWNLOAD_FIELDS = [
    "source_key",
    "url",
    "local_path",
    "retrieved_at_utc",
    "sha256",
    "bytes",
    "etag",
    "last_modified",
]


def read_downloads() -> list[dict]:
    path = SOURCES / "downloads.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _write_downloads(rows: list[dict]) -> None:
    with open(SOURCES / "downloads.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DOWNLOAD_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def plan(source_keys=None, years=None) -> list[dict]:
    """Cataloged files not yet downloaded."""
    done = {r["url"] for r in read_downloads()}
    out = []
    for r in read_files_catalog():
        if r["url"] in done:
            continue
        if source_keys and r["source_key"] not in source_keys:
            continue
        if years and r["sy"] and int(r["sy"]) not in years:
            continue
        out.append(r)
    return out


def head_sizes(rows: list[dict]) -> list[tuple[dict, int | None]]:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    sizes = []
    for r in rows:
        try:
            resp = session.head(r["url"], allow_redirects=True, timeout=30)
            n = resp.headers.get("Content-Length")
            sizes.append((r, int(n) if n else None))
        except requests.RequestException:
            sizes.append((r, None))
    return sizes


def _unique_path(directory: Path, name: str, stamp: str) -> Path:
    path = directory / name
    if not path.exists():
        return path
    return directory / f"{path.stem}.{stamp}{path.suffix}"


def fetch(rows: list[dict], pause: float = 1.0) -> list[dict]:
    """Download each row, never overwriting. Returns the new download records."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    downloads = read_downloads()
    new = []
    for r in rows:
        stamp = datetime.now(UTC)
        directory = RAW / r["source_key"]
        directory.mkdir(parents=True, exist_ok=True)
        resp = session.get(r["url"], timeout=120)
        resp.raise_for_status()
        sha = hashlib.sha256(resp.content).hexdigest()
        prior = [d for d in downloads if d["url"] == r["url"] and d["sha256"] == sha]
        if prior:
            continue  # identical bytes already archived
        path = _unique_path(directory, r["filename"], stamp.strftime("%Y%m%d"))
        path.write_bytes(resp.content)
        record = {
            "source_key": r["source_key"],
            "url": r["url"],
            "local_path": str(path.relative_to(RAW.parent)),
            "retrieved_at_utc": stamp.isoformat(timespec="seconds"),
            "sha256": sha,
            "bytes": len(resp.content),
            "etag": resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
        }
        downloads.append(record)
        new.append(record)
        _write_downloads(downloads)  # persist after every file so a crash loses nothing
        time.sleep(pause)
    return new


def fetch_one_snapshot(source_key: str, url: str) -> Path:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    now = datetime.now(UTC)
    directory = RAW / source_key / "snapshots"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{now.strftime('%Y%m%dT%H%M%SZ')}.html"
    path.write_bytes(resp.content)
    downloads = read_downloads()
    downloads.append(
        {
            "source_key": source_key,
            "url": url,
            "local_path": str(path.relative_to(RAW.parent)),
            "retrieved_at_utc": now.isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(resp.content).hexdigest(),
            "bytes": len(resp.content),
            "etag": resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
        }
    )
    _write_downloads(downloads)
    return path
