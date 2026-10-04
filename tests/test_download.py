import http.server
import threading
from functools import partial

import pytest

from phillyschools import fetch as fetch_mod
from phillyschools import spring_year
from phillyschools.discover import extract_file_links, file_row

PAGE = """
<a href="https://cdn.philasd.org/x/2025-2026%20Enrollment%20&amp;%20Demographics.csv">a</a>
<a href="https://cdn.philasd.org/x/2025-2026%20Enrollment%20&amp;%20Demographics.csv">dup</a>
<a href="/relative/Catchment_2425.zip">rel</a>
<a href="https://evil.example.com/steal.csv">offsite</a>
<a href="https://cdn.philasd.org/x/page.html">not a file</a>
"""


def test_extract_links_unescapes_dedupes_and_limits_hosts():
    links = extract_file_links(PAGE, "https://opendataphilly.org/datasets/x/")
    assert links == [
        "https://cdn.philasd.org/x/2025-2026%20Enrollment%20&%20Demographics.csv",
        "https://opendataphilly.org/relative/Catchment_2425.zip",
    ]


@pytest.mark.parametrize(
    "text,sy",
    [
        ("2025-2026 Enrollment & Demographics.csv", 2026),
        ("2018-2019_Enrollment_and_Demographics_(School_NS).csv", 2019),
        ("SDP_Catchment_2425.zip", None),
        ("FutureReady 2024-25.xlsx", 2025),
        ("Longitudinal School List (20171128).xlsx", None),
    ],
)
def test_spring_year(text, sy):
    assert spring_year(text) == sy


def test_file_row_decodes_name():
    r = file_row("s", "https://cdn.philasd.org/a/2025-2026%20Master%20List.csv", "2026-10-04")
    assert r["filename"] == "2025-2026 Master List.csv" and r["sy"] == 2026


@pytest.fixture
def server(tmp_path):
    (tmp_path / "data.csv").write_text("a,b\n1,2\n")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield tmp_path, f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_fetch_archives_hashes_and_never_overwrites(server, tmp_path, monkeypatch):
    served, base = server
    raw, src = tmp_path / "raw", tmp_path / "sources"
    raw.mkdir(), src.mkdir()
    monkeypatch.setattr(fetch_mod, "RAW", raw)
    monkeypatch.setattr(fetch_mod, "SOURCES", src)
    row = {"source_key": "t", "url": f"{base}/data.csv", "filename": "data.csv", "sy": ""}

    first = fetch_mod.fetch([row], pause=0)
    assert len(first) == 1 and (raw / "t" / "data.csv").read_text() == "a,b\n1,2\n"
    assert len(first[0]["sha256"]) == 64

    assert fetch_mod.fetch([row], pause=0) == []  # same bytes: nothing new

    (served / "data.csv").write_text("a,b\n9,9\n")  # upstream repost
    changed = fetch_mod.fetch([row], pause=0)
    assert len(changed) == 1
    assert (raw / "t" / "data.csv").read_text() == "a,b\n1,2\n"  # original untouched
    assert len(list((raw / "t").glob("data.*.csv"))) == 1
    assert len(fetch_mod.read_downloads()) == 2


def test_rejects_html_where_a_document_was_expected():
    from phillyschools.fetch import _is_unexpected_html

    assert _is_unexpected_html("report.pdf", b"  <!DOCTYPE html><html>Sign in</html>")
    assert not _is_unexpected_html("report.pdf", b"%PDF-1.7 ...")
    assert not _is_unexpected_html("agenda.html", b"<!DOCTYPE html>")


def test_uses_served_extension():
    from phillyschools.fetch import _served_name

    assert (
        _served_name("Testimony_ab12.pdf", 'attachment; filename="notes.docx"')
        == "Testimony_ab12.docx"
    )
    assert (
        _served_name("Testimony_ab12.pdf", "attachment; filename=03.26.pdf") == "Testimony_ab12.pdf"
    )
    assert _served_name("x.pdf", "") == "x.pdf"
