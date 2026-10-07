"""Command line: `uv run psd <command>`."""

import argparse
import sys
from datetime import UTC, datetime

import pandas as pd

from . import ROOT, STAGING
from .acs import build_area_context, write_area_context
from .asbestos import build_asbestos, write_asbestos
from .assessment import build_assessments, write_assessments
from .attendance import build_attendance, write_attendance
from .board import catalog_novus, catalog_primegov, catalog_primegov_attachments
from .buildings import build_buildings, write_building_mart, write_buildings
from .crdc import build_crdc, write_crdc
from .discipline import build_discipline, write_discipline
from .discover import add_file, discover
from .drive import catalog_drive
from .enrollment import build_enrollment, validate_enrollment, write_enrollment
from .environmental import latest_environmental
from .envresults import build_lead_paint, build_water, write_lead_paint, write_water
from .fastfacts import build_fast_facts, write_fast_facts
from .fca import build_fca, write_fca
from .fetch import fetch, fetch_one_snapshot, head_sizes, plan, read_downloads
from .finance import (
    build_finance,
    catalog_afr,
    catalog_school_budgets,
    catalog_state_funding,
    write_finance,
)
from .futureready import catalog_future_ready
from .gaps import read_gaps, write_markdown
from .geography import build_geography, write_geography
from .identity import build_identity, load_registry, validate, write_core
from .marts import build_marts
from .neighborhoods import build_neighborhood_flows, publishable, write_neighborhood_flows
from .parcels import build_school_parcel, write_school_parcel
from .peers import build_peer_comparison, write_peer_comparison
from .release import build_release
from .scores import build_scores, write_scores
from .sourcetable import build_source
from .stage import write_staging
from .telvue import catalog_videos
from .validate import run_validation
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


def cmd_catalog_future_ready(a):
    rows = catalog_future_ready()
    print(f"cataloged {len(rows)} Future Ready files")


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


def cmd_fetch_environmental_latest(a):
    done = {r["url"] for r in read_downloads()}
    todo = [r for r in latest_environmental() if r["url"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    if a.dry_run:
        sized = head_sizes(todo)
        known = [n for _, n in sized if n]
        print(f"{len(todo)} files; {len(known)} report a size, totaling {_human(sum(known))}")
        return
    new = fetch(todo)
    print(f"downloaded {len(new)} of {len(todo)} files; hashes in sources/downloads.csv")


def cmd_snapshot(a):
    path = fetch_one_snapshot(a.source, a.url)
    print(f"saved {path}")


def cmd_snapshot_buses(a):
    from .buses import snapshot_late_buses

    for path in snapshot_late_buses():
        print(f"saved {path}")


def cmd_gaps(a):
    write_markdown()
    gaps = read_gaps()
    print(f"docs/DATA_GAPS.md written ({len(gaps)} gaps)")


def cmd_build_geography(a):
    from .places import fetch_places

    fetch_places()
    t = build_geography()
    write_geography(t)
    for name in [
        "catchment",
        "assignment_zone",
        "geo_unit",
        "geo_xwalk",
        "geo_issues",
        "school_place",
    ]:
        print(f"  {name:16} {len(t[name]):>7} rows")
    print(f"  2020 population in blocks: {t['_block_pop_total']:,}")


def cmd_link_parcels(a):
    attr = pd.read_parquet(ROOT / "core" / "school_year_attr.parquet")
    df = build_school_parcel(attr, offline=a.offline)
    write_school_parcel(df)
    print(f"  {len(df)} school sites; match: {df['match'].value_counts(dropna=False).to_dict()}")
    print(f"  needs review: {int(df['needs_review'].sum())}")


def cmd_build_enrollment(a):
    t = build_enrollment(load_registry())
    problems = validate_enrollment(t)
    if problems:
        print("VALIDATION FAILED:\n  " + "\n  ".join(problems))
        sys.exit(1)
    write_enrollment(t)
    for name in [
        "enrollment",
        "catchment_flow",
        "school_metric",
        "school_placeholder",
        "enrollment_issues",
    ]:
        print(f"  {name:20} {len(t[name]):>8} rows")


def cmd_neighborhood_flows(a):
    t = build_neighborhood_flows()
    off = t["checks"]["difference"].abs().max()
    if off > 1:
        print(f"CHECK FAILED: allocated + unplaced differs from flow totals by {off:.1f}")
        print(t["checks"].to_string())
        sys.exit(1)
    pub = publishable(t)
    defined = set(pd.read_csv(ROOT / "registry" / "measures.csv")["measure_id"])
    undefined = set(pub["neighborhood_metric"]["measure_id"]) - defined
    if undefined:
        print(f"UNDEFINED MEASURES (add to registry/measures.csv): {sorted(undefined)}")
        sys.exit(1)
    write_neighborhood_flows(t, pub)
    print(t["checks"].round(0).to_string(index=False))
    for name, df in pub.items():
        print(
            f"  {name:20} {len(df):>8} rows; suppressed {int((df['status'] == 'suppressed').sum())}"
        )


def cmd_build_scores(a):
    t = build_scores()
    combined = write_scores(t)
    m = t["metric"]
    print(f"  future_ready rows {len(m)}; school_metric now {len(combined)} rows")
    print(m.groupby(["sy", "status"]).size().unstack(fill_value=0).to_string())
    print(f"  shared state keys: {len(t['issues'])} (core/future_ready_issues.csv)")


def cmd_build_assessments(a):
    t = build_assessments()
    write_assessments(t)
    r = t["assessment_result"]
    print(
        f"  assessment_result {len(r)} rows; unmapped schools {len(t['issues'])}; "
        f"duplicate keys resolved {t['duplicates']}; unmapped groups {t['unmapped_groups']}"
    )
    print(r.groupby(["sy", "status"]).size().unstack(fill_value=0).to_string())


def cmd_build_fast_facts(a):
    t = build_fast_facts()
    combined = write_fast_facts(t)
    m = t["metric"]
    print(
        f"  fast_facts rows {len(m)}; school_metric now {len(combined)}; "
        f"school_state_attr {len(t['attr'])} rows"
    )
    print(m.groupby(["sy", "status"]).size().unstack(fill_value=0).to_string())


def cmd_peer_comparison(a):
    df = build_peer_comparison()
    write_peer_comparison(df)
    d = df[df["status"] == "derived"]
    print(f"  {len(d)} comparisons; {int((df['status'] == 'not_applicable').sum())} not applicable")
    print(d.groupby(["window", "measure_id", "position"]).size().unstack(fill_value=0).to_string())


def cmd_build_area_context(a):
    df = build_area_context()
    write_area_context(df)
    print(f"  area_context {len(df)} rows")
    print(df.groupby(["unit_type", "status"]).size().unstack(fill_value=0).to_string())


def cmd_build_attendance(a):
    t = build_attendance()
    combined = write_attendance(t)
    m = t["metric"]
    print(
        f"  sdp_attendance rows {len(m)}; school_metric now {len(combined)}; unmapped {len(t['issues'])}"
    )
    print(
        m[m["student_group"] == "all"]
        .groupby(["sy", "measure_id"])
        .size()
        .unstack(fill_value=0)
        .to_string()
    )


def cmd_build_discipline(a):
    t = build_discipline()
    combined = write_discipline(t)
    print(
        f"  sdp_discipline rows {len(t['metric'])}; school_incident {len(t['school_incident'])}; "
        f"school_metric now {len(combined)}; unmapped school-years {len(t['issues'])}"
    )


def cmd_build_env_results(a):
    lead = build_lead_paint()
    combined = write_lead_paint(lead)
    linked = lead["school_id"].notna().mean()
    print(f"  lead-safe files {len(lead)} ({linked:.0%} linked to schools)")
    water = build_water()
    combined = write_water(water)
    files = water.drop_duplicates("file")
    print(
        f"  water letters {len(files)} ({files['school_id'].notna().mean():.0%} linked), "
        f"outlet samples {water['lead_ppb'].notna().sum()}"
    )
    print(f"  school_metric now {len(combined)}")


def cmd_build_asbestos(a):
    t = build_asbestos()
    combined = write_asbestos(t)
    rep = t["report"]
    print(
        f"  AHERA reports {len(rep)} for {rep['building_code'].nunique()} buildings; "
        f"log read for {(rep['status'] == 'reported').sum()}; asbestos items {len(t['item'])}"
    )
    print(f"  school_metric now {len(combined)}")


def cmd_build_fca(a):
    t = build_fca()
    combined = write_fca(t)
    site = t["site"]
    print(
        f"  FCA sites {len(site)} ({site['school_id'].notna().mean():.0%} linked), "
        f"buildings and grounds {len(t['part'])}, systems {len(t['system'])}"
    )
    print(f"  school_metric now {len(combined)}")


def cmd_build_marts(a):
    t = build_marts()
    sy, prof = t["school_year"], t["school_profile"]
    print(f"  school_year {len(sy)} rows x {len(sy.columns)} columns")
    print(f"  school_profile {len(prof)} rows x {len(prof.columns)} columns")
    print("  wrote schema/*.json and docs/DATA_DICTIONARY.md")


def cmd_validate(a):
    hard, recon = run_validation()
    failed = [c for c in hard if not c["ok"]] + [c for c in recon if not c["ok"]]
    for c in hard:
        print(f"  {'ok  ' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}")
    for c in recon:
        print(
            f"  {'ok  ' if c['ok'] else 'FAIL'} {c['check']}: r={c['r']:.3f} ratio={c['ratio']:.3f} (n={c['n']})"
        )
    print("  wrote docs/VALIDATION.md")
    if failed:
        raise SystemExit(f"{len(failed)} validation checks failed")


def cmd_build_buildings(a):
    t = build_buildings(offline=a.offline)
    write_buildings(t)
    mart = write_building_mart(t)
    b = t["building"]
    print(
        f"  buildings {len(b)}; with OPA account {b['opa_account'].notna().sum()}; "
        f"school_building rows {len(t['school_building'])}; xwalk keys {len(t['building_xwalk'])}"
    )
    print(f"  marts/building {len(mart)} rows x {len(mart.columns)} columns")


def cmd_release(a):
    r = build_release(a.version, skip_validation=a.skip_validation)
    mb = sum(p.stat().st_size for p in r["assets"]) / 1e6
    print(
        f"  release v{r['version']}: {r['tables']} core tables, {r['package_files']} files in the package"
    )
    print(f"  zip: {r['zip']}  ({r['zip'].stat().st_size / 1e6:.0f} MB)")
    print(f"  {len(r['assets'])} release assets in {r['dir'] / 'assets'} ({mb:.0f} MB)")


def cmd_catalog_afr(a):
    rows = catalog_afr()
    print(
        f"cataloged {len(rows)} PDE Annual Financial Report files; run `psd fetch --source pde_afr`"
    )


def cmd_build_school_budget(a):
    from .school_budgets import write_school_budget, write_school_purchases_positions

    sb, log = write_school_budget()
    print(
        f"  {int(log['has_budget'].sum())} school-years with a budget of {len(log)} reports; "
        f"{len(sb)} rows"
    )
    purchases, positions = write_school_purchases_positions()
    print(f"  purchase summary lines {len(purchases)}; position lines {len(positions)}")


def cmd_build_closure_plan(a):
    from .closures import write_closure_plan

    plan = write_closure_plan()
    closing = plan.drop_duplicates("closing_school_id")
    print(
        f"  {len(plan)} proposed closing-to-receiving pairs for {len(closing)} proposed closures; "
        f"{int(closing['closed_in_2013_wave'].sum())} closed in the 2013 wave"
    )


def cmd_build_closure_flows(a):
    from .closure_flows import write_closure_flows

    flows, summary = write_closure_flows()
    print(f"  {len(flows)} closed-to-receiving school pairs; {len(summary)} closed schools covered")


def cmd_catalog_pde_school(a):
    from .pde_school import catalog_pde_school

    rows = catalog_pde_school()
    print(
        f"cataloged {len(rows)} PDE school-level files; "
        "run `psd fetch --source pde_essa_ppe` and `psd fetch --source pde_enrollment`"
    )


def cmd_build_pde_school(a):
    from .pde_school import write_pde_school

    t = write_pde_school()
    print("  " + "; ".join(f"{k} {len(v)} rows" for k, v in t.items()))


def cmd_build_pde_staff(a):
    from .pde_school import write_pde_staff

    t = write_pde_staff()
    print("  " + "; ".join(f"{k} {len(v)} rows" for k, v in t.items()))


def cmd_build_finance(a):
    t = build_finance()
    mart = write_finance(t)
    print(
        f"  agencies {len(t['finance_lea'])}; account lines {len(t['finance_lea_line'])}; "
        f"district_finance {len(mart)} rows x {len(mart.columns)} columns"
    )


def cmd_catalog_school_budgets(a):
    rows = catalog_school_budgets(tuple(a.kinds))
    print(
        f"cataloged {len(rows)} school budget reports; run `psd fetch --source sdp_school_budgets`"
    )


def cmd_catalog_state_funding(a):
    rows = catalog_state_funding()
    print(f"cataloged {len(rows)} state funding and adequacy files")


def cmd_build_crdc(a):
    t = build_crdc()
    combined = write_crdc(t)
    print(
        f"  crdc rows {len(t['metric'])}; school_metric now {len(combined)}; "
        f"unmapped school-years {len(t['unmapped'])}"
    )


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

    s = sub.add_parser("catalog-future-ready", help="catalog PDE Future Ready data files")
    s.set_defaults(fn=cmd_catalog_future_ready)

    s = sub.add_parser("fetch", help="download cataloged files into raw/")
    s.add_argument("--source", nargs="*")
    s.add_argument("--sy", nargs="*", help="spring years, e.g. 2025 2026")
    s.add_argument("--dry-run", action="store_true", help="list files and sizes only")
    s.add_argument("--subdir", help="only files under this raw/<source>/ subfolder")
    s.add_argument("--match", help="regex the file name must match")
    s.add_argument("--exclude", help="regex the file name must not match")
    s.add_argument("--limit", type=int, help="at most this many files")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser(
        "fetch-environmental-latest",
        help="download the most recent environmental report per school and type",
    )
    s.add_argument("--dry-run", action="store_true", help="count files and sizes only")
    s.add_argument("--limit", type=int, help="at most this many files")
    s.set_defaults(fn=cmd_fetch_environmental_latest)

    s = sub.add_parser("snapshot", help="archive a web page (no file to download)")
    s.add_argument("source")
    s.add_argument("url")
    s.set_defaults(fn=cmd_snapshot)

    s = sub.add_parser("snapshot-buses", help="archive today's canceled/late bus lists")
    s.set_defaults(fn=cmd_snapshot_buses)

    s = sub.add_parser("gaps", help="regenerate docs/DATA_GAPS.md from sources/gaps.csv")
    s.set_defaults(fn=cmd_gaps)

    s = sub.add_parser("build-geography", help="catchments, zones, geo units, weighted crosswalk")
    s.set_defaults(fn=cmd_build_geography)

    s = sub.add_parser("link-parcels", help="match school locations to City parcels (OPA)")
    s.add_argument("--offline", action="store_true", help="use archived answers only")
    s.set_defaults(fn=cmd_link_parcels)

    s = sub.add_parser("build-enrollment", help="enrollment, catchment flows, school metrics")
    s.set_defaults(fn=cmd_build_enrollment)

    s = sub.add_parser("neighborhood-flows", help="roll catchment flows up to neighborhoods")
    s.set_defaults(fn=cmd_neighborhood_flows)

    s = sub.add_parser(
        "build-scores", help="Future Ready test scores, growth, attendance, graduation"
    )
    s.set_defaults(fn=cmd_build_scores)

    s = sub.add_parser("build-assessments", help="district PSSA and Keystone results, 2009-10 on")
    s.set_defaults(fn=cmd_build_assessments)

    s = sub.add_parser(
        "build-fast-facts", help="state School Fast Facts demographics and attributes"
    )
    s.set_defaults(fn=cmd_build_fast_facts)

    s = sub.add_parser("peer-comparison", help="compare schools with their closest-poverty peers")
    s.set_defaults(fn=cmd_peer_comparison)

    s = sub.add_parser("build-area-context", help="ACS neighborhood context by tract and geo unit")
    s.set_defaults(fn=cmd_build_area_context)

    s = sub.add_parser("build-attendance", help="district attendance detail, 2013-14 on")
    s.set_defaults(fn=cmd_build_attendance)

    s = sub.add_parser("build-discipline", help="district suspensions and serious incidents")
    s.set_defaults(fn=cmd_build_discipline)

    s = sub.add_parser("build-crdc", help="federal Civil Rights Data Collection discipline")
    s.set_defaults(fn=cmd_build_crdc)

    s = sub.add_parser("build-fca", help="facility condition assessments (2020 cycle)")
    s.set_defaults(fn=cmd_build_fca)

    s = sub.add_parser("build-buildings", help="buildings, school-building links, building mart")
    s.add_argument("--offline", action="store_true", help="use archived City parcel answers only")
    s.set_defaults(fn=cmd_build_buildings)

    s = sub.add_parser("release", help="validate, then build the release package and assets")
    s.add_argument("--version", required=True, help="for example 0.1.0")
    s.add_argument("--skip-validation", action="store_true")
    s.set_defaults(fn=cmd_release)

    s = sub.add_parser("catalog-afr", help="catalog the PDE Annual Financial Report files")
    s.set_defaults(fn=cmd_catalog_afr)

    s = sub.add_parser(
        "build-school-budget", help="parse the district's school budget allotment PDFs"
    )
    s.set_defaults(fn=cmd_build_school_budget)

    s = sub.add_parser(
        "build-closure-plan", help="the December 2012 closure proposal (a plan, not lineage)"
    )
    s.set_defaults(fn=cmd_build_closure_plan)

    s = sub.add_parser(
        "build-closure-flows", help="observed enrollment change around the 2013 closures"
    )
    s.set_defaults(fn=cmd_build_closure_flows)

    s = sub.add_parser(
        "catalog-pde-school", help="catalog PDE per-pupil expenditure and enrollment files"
    )
    s.set_defaults(fn=cmd_catalog_pde_school)

    s = sub.add_parser(
        "build-pde-school", help="school-level per-pupil expenditures and LEA enrollment from PDE"
    )
    s.set_defaults(fn=cmd_build_pde_school)

    s = sub.add_parser(
        "build-pde-staff", help="professional staff profile and teacher retention by agency (PDE)"
    )
    s.set_defaults(fn=cmd_build_pde_staff)

    s = sub.add_parser("build-finance", help="state school finance tables from the AFR files")
    s.set_defaults(fn=cmd_build_finance)

    s = sub.add_parser(
        "catalog-school-budgets", help="catalog the district's public school budget reports"
    )
    s.add_argument(
        "--kinds", nargs="*", default=["allotment"], choices=["allotment", "purchases", "positions"]
    )
    s.set_defaults(fn=cmd_catalog_school_budgets)

    s = sub.add_parser(
        "catalog-state-funding", help="catalog state subsidy files and the adequacy studies"
    )
    s.set_defaults(fn=cmd_catalog_state_funding)

    s = sub.add_parser("build-marts", help="wide tables, schema JSON, and the data dictionary")
    s.set_defaults(fn=cmd_build_marts)

    s = sub.add_parser(
        "validate", help="hard checks and reconciliations; writes docs/VALIDATION.md"
    )
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("build-asbestos", help="asbestos (AHERA) results from the reports")
    s.set_defaults(fn=cmd_build_asbestos)

    s = sub.add_parser("build-env-results", help="lead paint and water results from the PDFs")
    s.set_defaults(fn=cmd_build_env_results)

    s = sub.add_parser("stage", help="stage raw SDP master lists into staging/")
    s.set_defaults(fn=cmd_stage)

    s = sub.add_parser("build-identity", help="build identity tables into core/")
    s.set_defaults(fn=cmd_build_identity)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
