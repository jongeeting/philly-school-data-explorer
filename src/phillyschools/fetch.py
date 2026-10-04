"""Download cataloged files into raw/ untouched, and record URL, time, and SHA-256.

raw/ is never edited. If a file changes upstream (the district does repost files), the new
version is saved beside the old one and both stay in sources/downloads.csv.
"""

import csv
import hashlib
import re
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


def plan(source_keys=None, years=None, subdir=None, match=None, exclude=None) -> list[dict]:
    """Cataloged files not yet downloaded, optionally filtered by subfolder and file-name regex."""
    done = {r["url"] for r in read_downloads()}
    inc = re.compile(match, re.IGNORECASE) if match else None
    exc = re.compile(exclude, re.IGNORECASE) if exclude else None
    out = []
    for r in read_files_catalog():
        if subdir and not (r.get("subdir") or "").startswith(subdir):
            continue
        if inc and not inc.search(r["filename"]):
            continue
        if exc and exc.search(r["filename"]):
            continue
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
    new, failures = [], []
    for r in rows:
        stamp = datetime.now(UTC)
        directory = RAW / r["source_key"] / (r.get("subdir") or "")
        directory.mkdir(parents=True, exist_ok=True)
        resp = _get_with_retry(session, r["url"])
        if resp is None:
            failures.append(r["url"])
            continue
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
    if failures:
        _log_failures(failures)
    return new


RETRY_STATUS = {429, 500, 502, 503, 504}


def _get_with_retry(session, url: str, attempts: int = 4, backoff: float = 30.0):
    """GET with backoff on rate limits and server errors. None means give up for now.

    Failed URLs are not recorded as downloaded, so the next `psd fetch` retries them.
    """
    for i in range(attempts):
        try:
            resp = session.get(url, timeout=180)
        except requests.RequestException:
            resp = None
        if resp is not None and resp.status_code == 200:
            return resp
        if resp is not None and resp.status_code not in RETRY_STATUS:
            return None
        time.sleep(backoff * (i + 1))
    return None


def _log_failures(urls: list[str]) -> None:
    path = SOURCES / "fetch_failures.csv"
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["failed_at_utc", "url"])
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        w.writerows([stamp, u] for u in urls)


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


def record_local_file(source_key: str, url: str, path: Path) -> dict:
    """Record a file we saved directly (an API response) with its hash, like any download."""
    body = path.read_bytes()
    record = {
        "source_key": source_key,
        "url": url,
        "local_path": str(path.relative_to(RAW.parent)),
        "retrieved_at_utc": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
            timespec="seconds"
        ),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "etag": "",
        "last_modified": "",
    }
    downloads = read_downloads()
    if not any(d["local_path"] == record["local_path"] for d in downloads):
        downloads.append(record)
        _write_downloads(downloads)
    return record
