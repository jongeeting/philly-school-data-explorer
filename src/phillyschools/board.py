"""Catalog Board of Education and School Reform Commission records for archiving.

  PrimeGov (2019 on)     public JSON list of meetings per year; compiled agendas, packets and
                         minutes (PDF) plus HTML versions; attachments are linked from the HTML
  NovusAgenda (2018-23)  sequential meeting IDs; HTML agendas linking attachments
  WordPress (2013-18)    PDFs linked from the Board's meetings page (see `psd discover`)
  SRC (2003-13)          Wayback Machine only (see `psd catalog-wayback`)

Only stable URLs are cataloged (PrimeGov redirects to signed, expiring storage links at fetch
time; those are never recorded).
"""

import html
import json
import re
import time
from datetime import UTC, datetime

import requests

from . import RAW, USER_AGENT
from .discover import file_row, read_files_catalog, write_files_catalog
from .fetch import record_local_file

PRIMEGOV = "https://philasd.primegov.com"
NOVUS = "https://philasd.novusagenda.com/agendapublic"
OUTPUT_EXT = {1: ".pdf", 3: ".html"}  # 2 is a Word copy of the PDF; skipped
HISTORY_LINK = re.compile(
    r'href="(/api/compilemeetingattachmenthistory/historyattachment/\?historyId=([0-9a-f-]{36}))"'
    r"[^>]*>(.*?)</a>",
    re.DOTALL,
)
NOVUS_ATTACHMENT = re.compile(
    r'href="(AttachmentViewer\.ashx\?AttachmentID=(\d+)&(?:amp;)?ItemID=(\d+))"[^>]*>(.*?)</a>',
    re.DOTALL,
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _slug(s: str, n: int = 60) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", html.unescape(s)).strip("-")[:n]


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _merge(rows: list[dict]) -> None:
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in rows:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())


def primegov_meetings(year: int, session=None) -> list[dict]:
    session = session or _session()
    resp = session.get(
        f"{PRIMEGOV}/api/v2/PublicPortal/ListArchivedMeetings", params={"year": year}, timeout=60
    )
    resp.raise_for_status()
    return resp.json()


def primegov_rows(meetings: list[dict], today: str) -> list[dict]:
    rows = []
    for m in meetings:
        day = m["dateTime"][:10]
        folder = f"{day[:4]}/{day}_{_slug(m.get('title') or 'meeting')}_{m['id']}"
        for doc in m.get("documentList") or []:
            ext = OUTPUT_EXT.get(doc["compileOutputType"])
            if not ext or doc.get("publishStatus") != 1:
                continue
            if ext == ".html":
                url = f"{PRIMEGOV}/Portal/Meeting?meetingTemplateId={doc['templateId']}"
            else:
                url = (
                    f"{PRIMEGOV}/Public/CompiledDocument?meetingTemplateId={doc['templateId']}"
                    f"&compileOutputType={doc['compileOutputType']}"
                )
            row = file_row("sdp_board_primegov", url, today)
            row.update(
                filename=f"{_slug(doc['templateName'])}_{doc['templateId']}{ext}",
                ext=ext,
                subdir=folder,
                sy="",
            )
            rows.append(row)
    return rows


def catalog_primegov(years: list[int], pause: float = 1.0) -> list[dict]:
    """Archive each year's meeting list (JSON) and catalog every compiled document."""
    session, today, rows = _session(), _today(), []
    out = RAW / "sdp_board_primegov" / "api"
    out.mkdir(parents=True, exist_ok=True)
    for year in years:
        meetings = primegov_meetings(year, session)
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        path = out / f"ListArchivedMeetings_{year}_{stamp}.json"
        path.write_text(json.dumps(meetings, indent=1))
        record_local_file(
            "sdp_board_primegov",
            f"{PRIMEGOV}/api/v2/PublicPortal/ListArchivedMeetings?year={year}",
            path,
        )
        rows += primegov_rows(meetings, today)
        time.sleep(pause)
    _merge(rows)
    return rows


def primegov_attachment_rows(html_text: str, subdir: str, today: str) -> list[dict]:
    rows, seen = [], set()
    for path, hid, label in HISTORY_LINK.findall(html_text):
        if hid in seen:
            continue
        seen.add(hid)
        text = _slug(re.sub(r"<[^>]+>", " ", label), 80) or "attachment"
        row = file_row("sdp_board_primegov", PRIMEGOV + path, today)
        row.update(
            filename=f"{text}_{hid[:8]}.pdf", ext=".pdf", subdir=f"{subdir}/attachments", sy=""
        )
        rows.append(row)
    return rows


def catalog_primegov_attachments() -> list[dict]:
    """After the HTML packets are fetched, catalog the attachments they link."""
    today, rows = _today(), []
    base = RAW / "sdp_board_primegov"
    for page in base.glob("*/*/*.html"):
        subdir = str(page.parent.relative_to(base))
        rows += primegov_attachment_rows(page.read_text(errors="replace"), subdir, today)
    _merge(rows)
    return rows


def novus_page_is_meeting(text: str) -> bool:
    body = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", text, flags=re.DOTALL)
    return len(re.sub(r"\s+", " ", body)) > 300


def catalog_novus(max_id: int = 420, pause: float = 1.0) -> list[dict]:
    session, today, rows = _session(), _today(), []
    for mid in range(1, max_id + 1):
        url = f"{NOVUS}/MeetingView.aspx?MeetingID={mid}&doctype=Agenda"
        resp = session.get(url, timeout=60)
        if resp.status_code != 200 or not novus_page_is_meeting(resp.text):
            time.sleep(pause / 2)
            continue
        subdir = f"meeting_{mid:04d}"
        page = file_row("sdp_board_novusagenda", url, today)
        page.update(filename=f"agenda_{mid:04d}.html", ext=".html", subdir=subdir, sy="")
        rows.append(page)
        for path, att, item, label in NOVUS_ATTACHMENT.findall(resp.text):
            text = _slug(re.sub(r"<[^>]+>", " ", label), 80) or "attachment"
            r = file_row("sdp_board_novusagenda", f"{NOVUS}/{html.unescape(path)}", today)
            r.update(
                filename=f"{text}_{att}.pdf", ext=".pdf", subdir=f"{subdir}/attachments", sy=""
            )
            rows.append(r)
        time.sleep(pause)
    _merge(rows)
    return rows
