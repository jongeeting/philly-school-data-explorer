"""Command line: `uv run psd <command>`."""

import argparse
import sys

import pandas as pd

from . import ROOT, STAGING
from .discover import discover
from .fetch import fetch, fetch_one_snapshot, head_sizes, plan
from .gaps import read_gaps, write_markdown
from .identity import build_identity, load_registry, validate, write_core
from .sourcetable import build_source
from .stage import write_staging

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


def cmd_fetch(a):
    years = {int(y) for y in a.sy} if a.sy else None
    todo = plan(a.source or None, years)
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
    years = sorted(tables["school_year_attr"]["sy"].unique().tolist())
    src = build_source(years)
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

    s = sub.add_parser("fetch", help="download cataloged files into raw/")
    s.add_argument("--source", nargs="*")
    s.add_argument("--sy", nargs="*", help="spring years, e.g. 2025 2026")
    s.add_argument("--dry-run", action="store_true", help="list files and sizes only")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("snapshot", help="archive a web page (no file to download)")
    s.add_argument("source")
    s.add_argument("url")
    s.set_defaults(fn=cmd_snapshot)

    s = sub.add_parser("gaps", help="regenerate docs/DATA_GAPS.md from sources/gaps.csv")
    s.set_defaults(fn=cmd_gaps)

    s = sub.add_parser("stage", help="stage raw SDP master lists into staging/")
    s.set_defaults(fn=cmd_stage)

    s = sub.add_parser("build-identity", help="build identity tables into core/")
    s.set_defaults(fn=cmd_build_identity)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
