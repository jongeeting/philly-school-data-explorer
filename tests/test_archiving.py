from phillyschools import drive
from phillyschools import fetch as fetch_mod

FOLDER_HTML = """
<div class="flip-entry" id="entry-FOLDER1" tabindex="0"><div class="flip-entry-info">
<a href="https://drive.google.com/drive/folders/FOLDER1" target="_blank">
<div class="flip-entry-title">Adaire, Alexander</div></a></div></div>
<div class="flip-entry" id="entry-FILE1" tabindex="0"><div class="flip-entry-info">
<a href="https://drive.google.com/file/d/FILE1/view?usp=drive_web" target="_blank">
<div class="flip-entry-title">5200-Adaire_9-2026_6-Month Report.pdf</div></a></div></div>
"""


class FakeResponse:
    text = FOLDER_HTML

    def raise_for_status(self):
        pass


class FakeSession:
    def get(self, url, timeout):
        return FakeResponse()


def test_drive_listing_separates_folders_and_files():
    entries = drive.list_folder(FakeSession(), "root")
    assert entries == [
        ("FOLDER1", "Adaire, Alexander", "folder"),
        ("FILE1", "5200-Adaire_9-2026_6-Month Report.pdf", "file"),
    ]


def test_safe_name_removes_path_separators():
    assert drive.safe_name("2025/2026 Annual Notice") == "2025-2026 Annual Notice"


def test_plan_filters_by_subdir_and_name(monkeypatch):
    rows = [
        {
            "source_key": "s",
            "url": "u1",
            "filename": "7100-Cooke-3-Year-AHERA-Report.pdf",
            "subdir": "capitalprograms_archive/2019/03",
            "sy": "",
        },
        {
            "source_key": "s",
            "url": "u2",
            "filename": "Bid-Addendum-1.pdf",
            "subdir": "capitalprograms_archive/2019/03",
            "sy": "",
        },
        {
            "source_key": "s",
            "url": "u3",
            "filename": "Adaire.pdf",
            "subdir": "ahera/Adaire",
            "sy": "",
        },
    ]
    monkeypatch.setattr(fetch_mod, "read_files_catalog", lambda: rows)
    monkeypatch.setattr(fetch_mod, "read_downloads", list)
    picked = fetch_mod.plan(
        ["s"], subdir="capitalprograms_archive", match="ahera|addendum", exclude="bid"
    )
    assert [r["url"] for r in picked] == ["u1"]


def test_video_meeting_dates_anywhere_in_title():
    from phillyschools.telvue import meeting_date

    assert meeting_date("20260924 BOE Action Meeting") == "2026-09-24"
    assert meeting_date("SRC 20161115") == "2016-11-15"
    assert meeting_date("20160616_SRC_meeting") == "2016-06-16"
    assert meeting_date("2015119 SRC Meeting") is None  # malformed in the source
    assert meeting_date("March Student of the Month") is None


def test_video_items_parse_id_duration_title():
    from phillyschools.telvue import parse_items

    page = (
        '<a href="/player/KEY/media/1020327"><div>02:01:13</div>'
        "<span>20260430 BOE Special Action Meeting</span></a>"
    )
    assert parse_items(page) == [
        {
            "media_id": "1020327",
            "duration": "02:01:13",
            "title": "20260430 BOE Special Action Meeting",
        }
    ]
