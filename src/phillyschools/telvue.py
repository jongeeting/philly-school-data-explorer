"""Catalog Board and SRC meeting videos on the district's TelVue player (metadata only).

The player serves streams with downloads turned off, so we record what exists (media ID,
title, meeting date, duration, playlist) and never fetch the video itself. Pages are archived
untouched in raw/sdp_board_video/pages/ with hashes.

Listing limits: a playlist page shows at most 50 videos and the all-videos page 25, with no
working pagination, so we combine every playlist page with the all-videos page sorted four ways
and compare the count with the site's reported total.
"""

import html
import re
import time
from datetime import UTC, datetime

import pandas as pd
import requests

from . import RAW, USER_AGENT
from .fetch import record_local_file

PLAYER = "https://videoplayer.telvue.com/player/0bfLByeZXfZHVlpy5BHT5v2arkggCWuH"
ITEM = re.compile(
    r'href="/player/[^/]+/(?:playlists/\d+/)?media/(\d+)".*?'
    r"(\d{2}:\d{2}:\d{2})\s*(?:<[^>]+>\s*)*([^<]{3,200})",
    re.DOTALL,
)
PLAYLIST = re.compile(r'href="/player/[^/]+/playlists/(\d+)/media/\d+"')


def _get(session, path: str, name: str) -> str:
    resp = session.get(f"{PLAYER}/{path}", timeout=60)
    resp.raise_for_status()
    out = RAW / "sdp_board_video" / "pages"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    target = out / f"{name}_{stamp}.html"
    target.write_text(resp.text)
    record_local_file("sdp_board_video", f"{PLAYER}/{path}", target)
    return resp.text


def parse_items(page: str) -> list[dict]:
    out = []
    for media_id, duration, title in ITEM.findall(page):
        title = re.sub(r"\s+", " ", html.unescape(title)).strip()
        out.append({"media_id": media_id, "duration": duration, "title": title})
    return out


def playlist_names(page: str) -> dict[str, str]:
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))
    names = re.findall(r"([A-Z][^()]{2,60}?) \((\d+) Videos?\)", text)
    ids = list(dict.fromkeys(PLAYLIST.findall(page)))
    clean = [re.sub(r"^.*(?:ago|Categories) ", "", n).strip() for n, _ in names]
    return dict(zip(ids, clean, strict=False))


def meeting_date(title: str) -> str | None:
    """YYYYMMDD anywhere in the title ('20240919 BOE Action', 'SRC 20161115', '20160616_SRC')."""
    for y, mo, d in re.findall(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", title):
        if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{mo}-{d}"
    return None


def catalog_videos(pause: float = 1.0) -> tuple[pd.DataFrame, int | None]:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    rows = []
    first = _get(session, "videos", "videos")
    m = re.search(r'data-total-available-count="(\d+)"', first)
    total = int(m.group(1)) if m else None
    rows += [{**r, "playlist_id": None} for r in parse_items(first)]
    for sort in ["created_at", "title"]:
        for order in ["asc", "desc"]:
            page = _get(
                session, f"videos?sort_by={sort}&order_by={order}", f"videos_{sort}_{order}"
            )
            rows += [{**r, "playlist_id": None} for r in parse_items(page)]
            time.sleep(pause)
    names = playlist_names(_get(session, "playlists", "playlists"))
    for pid in names:
        for order in ["desc", "asc"]:
            page = _get(
                session,
                f"playlists/{pid}?sort_by=created_at&order_by={order}",
                f"playlist_{pid}_{order}",
            )
            rows += [{**r, "playlist_id": pid} for r in parse_items(page)]
            time.sleep(pause)
    df = pd.DataFrame(rows)
    df["playlist"] = df["playlist_id"].map(names)
    playlists = (
        df.dropna(subset=["playlist"])
        .groupby("media_id")["playlist"]
        .agg(lambda s: "; ".join(sorted(set(s))))
    )
    out = df.drop_duplicates("media_id")[["media_id", "title", "duration"]].copy()
    out["playlists"] = out["media_id"].map(playlists)
    out["meeting_date"] = out["title"].map(meeting_date)
    out["url"] = PLAYER + "/media/" + out["media_id"]
    out = out.sort_values(["meeting_date", "media_id"], na_position="last").reset_index(drop=True)
    return out, total
