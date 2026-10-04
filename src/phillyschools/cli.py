"""Command line: `uv run psd <command>`."""

import argparse
import sys
from datetime import UTC, datetime

import pandas as pd

from . import ROOT, STAGING
from .board import catalog_novus, catalog_primegov, catalog_primegov_attachments
from .discover import add_file, discover
from .drive import catalog_drive
from .fetch import fetch, fetch_one_snapshot, head_sizes, plan
from .gaps import read_gaps, write_markdown
from .geography import build_geography, write_geography
from .identity import build_identity, load_registry, validate, write_core
from .parcels import build_school_parcel, write_school_parcel
from .sourcetable import build_source
from .stage import write_staging
from .telvue import catalog_videos
from .wayback import catalog_drive_links_on_archived_page, catalog_wayback

PROTOTYPE_INPUT = ROOT / "prototype" / "data" / "school_years.csv"


def _human(n: int | None) -> str:
    if n is None:
        return "size unknown"
    return f"{n / 1_000_000:.1f} MB" if n >= 1_000_000 else f"{n / 1000:.0f} KB"


def cmd_discover(a):
    rows = discover(a.source or None)
    print(f"{len(rows)} files cataloged in sources/files.csv")
    by = pd.DataFrame(rows).groupby("source_key").size()
    print(by.to_string())


def cmd_add_file(a):
    r = add_file(a.source, a.url)
    print(f"cataloged {r['filename']} under {a.source}")


def cmd_catalog_drive(a):
    rows = catalog_drive(a.source, a.folder_id, a.prefix)
    print(f"cataloged {len(rows)} files from Drive folder into {a.source}/{a.prefix}")


def cmd_catalog_wayback(a):
    rows = catalog_wayback(a.source, a.url_prefix, a.prefix)
    print(f"cataloged {len(rows)} archived files under {a.url_prefix}")


def cmd_catalog_archived_links(a):
    rows = catalog_drive_links_on_archived_page(a.source, a.page_url, a.prefix)
    print(f"cataloged {len(rows)} Drive files linked from archived {a.page_url}")


def cmd_catalog_board(a):
    if a.system == "primegov":
        rows = catalog_primegov(list(range(a.start, a.end + 1)))
    elif a.system == "primegov-attachments":
        rows = catalog_primegov_attachments()
    else:
        rows = catalog_novus()
    print(f"cataloged {len(rows)} board files ({a.system})")


def cmd_catalog_video(a):
    df, total = catalog_videos()
    out = ROOT / "core" / "board_video_catalog.csv"
    df.to_csv(out, index=False)
    print(
        f"{len(df)} videos cataloged (site reports {total}); dated: {df['meeting_date'].notna().sum()}"
    )
    print(df.groupby(df["meeting_date"].str[:4]).size().to_string())


def cmd_fetch(a):
    years = {int(y) for y in a.sy} if a.sy else None
    todo = plan(a.source or None, years, a.subdir, a.match, a.exclude)
    if a.limit:
        todo = todo[: a.limit]
    if not todo:
        print("nothing to download")
        return
    if a.dry_run:
        sized = head_sizes(todo)
        for r, n in sized:
            print(f"{r['source_key']:28} {_human(n):>10}  {r['filename']}")
        total = sum(n or 0 for _, n in sized)
        print(f"{len(todo)} files, about {_human(total)}")
        return
    new = fetch(todo)
    print(f"downloaded {len(new)} files; hashes in sources/downloads.csv")


def cmd_snapshot(a):
    path = fetch_one_snapshot(a.source, a.url)
    print(f"saved {path}")


def cmd_gaps(a):
    write_markdown()
    gaps = read_gaps()
    print(f"docs/DATA_GAPS.md written ({len(gaps)} gaps)")


def cmd_build_geography(a):
    t = build_geography()
    write_geography(t)
    for name in ["catchment", "assignment_zone", "geo_unit", "geo_xwalk", "geo_issues"]:
        print(f"  {name:16} {len(t[name]):>7} rows")
    print(f"  2020 population in blocks: {t['_block_pop_total']:,}")


def cmd_link_parcels(a):
    attr = pd.read_parquet(ROOT / "core" / "school_year_attr.parquet")
    df = build_school_parcel(attr, offline=a.offline)
    write_school_parcel(df)
    print(f"  {len(df)} school sites; match: {df['match'].value_counts(dropna=False).to_dict()}")
    print(f"  needs review: {int(df['needs_review'].sum())}")


def cmd_stage(a):
    out = write_staging()
    print(out.groupby("year").size().to_string())


def cmd_build_identity(a):
    path = STAGING / "sdp_master_school_list.parquet"
    if path.exists():
        staged = pd.read_parquet(path)
        origin = path
    else:
        staged = pd.read_csv(PROTOTYPE_INPUT, dtype=str)
        origin = PROTOTYPE_INPUT
    print(f"input: {origin.relative_to(ROOT)} ({len(staged)} rows)")
    tables = build_identity(staged, load_registry())
    problems = validate(tables)
    if problems:
        print("VALIDATION FAILED:\n  " + "\n  ".join(problems))
        sys.exit(1)
    write_core(tables)
    used = set(tables["school_year_attr"]["source_id"]) | set(tables["school_event"]["source_id"])
    src = build_source(sorted(used))
    src.to_parquet(ROOT / "core" / "source.parquet", index=False)
    src.to_csv(ROOT / "core" / "source.csv", index=False)
    for name, df in tables.items():
        if not name.startswith("_"):
            print(f"  {name:18} {len(df):>6} rows")
    print(f"  issues needing review: {len(tables['issues'])} (core/issues.csv)")


def main():
    p = argparse.ArgumentParser(prog="psd", description=__doc__)
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("discover", help="catalog file links from landing pages")
    s.add_argument("--source", nargs="*")
    s.set_defaults(fn=cmd_discover)

    s = sub.add_parser("add-file", help="catalog one direct file URL")
    s.add_argument("source")
    s.add_argument("url")
    s.set_defaults(fn=cmd_add_file)

    s = sub.add_parser("catalog-drive", help="catalog every file in a public Drive folder tree")
    s.add_argument("source")
    s.add_argument("folder_id")
    s.add_argument("prefix", help="subfolder under raw/<source>/")
    s.set_defaults(fn=cmd_catalog_drive)

    s = sub.add_parser("catalog-wayback", help="catalog PDFs archived under a URL prefix")
    s.add_argument("source")
    s.add_argument("url_prefix")
    s.add_argument("prefix")
    s.set_defaults(fn=cmd_catalog_wayback)

    s = sub.add_parser("catalog-archived-links", help="catalog Drive links on an archived page")
    s.add_argument("source")
    s.add_argument("page_url")
    s.add_argument("prefix")
    s.set_defaults(fn=cmd_catalog_archived_links)

    s = sub.add_parser("catalog-board", help="catalog Board of Education records")
    s.add_argument("system", choices=["primegov", "primegov-attachments", "novus"])
    s.add_argument("--start", type=int, default=2019)
    s.add_argument("--end", type=int, default=datetime.now(UTC).year)
    s.set_defaults(fn=cmd_catalog_board)

    s = sub.add_parser("catalog-video", help="list Board/SRC meeting videos (metadata only)")
    s.set_defaults(fn=cmd_catalog_video)

    s = sub.add_parser("fetch", help="download cataloged files into raw/")
    s.add_argument("--source", nargs="*")
    s.add_argument("--sy", nargs="*", help="spring years, e.g. 2025 2026")
    s.add_argument("--dry-run", action="store_true", help="list files and sizes only")
    s.add_argument("--subdir", help="only files under this raw/<source>/ subfolder")
    s.add_argument("--match", help="regex the file name must match")
    s.add_argument("--exclude", help="regex the file name must not match")
    s.add_argument("--limit", type=int, help="at most this many files")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("snapshot", help="archive a web page (no file to download)")
    s.add_argument("source")
    s.add_argument("url")
    s.set_defaults(fn=cmd_snapshot)

    s = sub.add_parser("gaps", help="regenerate docs/DATA_GAPS.md from sources/gaps.csv")
    s.set_defaults(fn=cmd_gaps)

    s = sub.add_parser("build-geography", help="catchments, zones, geo units, weighted crosswalk")
    s.set_defaults(fn=cmd_build_geography)

    s = sub.add_parser("link-parcels", help="match school locations to City parcels (OPA)")
    s.add_argument("--offline", action="store_true", help="use archived answers only")
    s.set_defaults(fn=cmd_link_parcels)

    s = sub.add_parser("stage", help="stage raw SDP master lists into staging/")
    s.set_defaults(fn=cmd_stage)

    s = sub.add_parser("build-identity", help="build identity tables into core/")
    s.set_defaults(fn=cmd_build_identity)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
