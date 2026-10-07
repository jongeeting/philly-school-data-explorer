"""Run every example query in docs/queries/ against the built data (skipped without it)."""

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
QUERIES = sorted((ROOT / "docs" / "queries").glob("*.sql"))
BUILT = (ROOT / "marts" / "school_year.parquet").exists() and (
    ROOT / "core" / "school_metric.parquet"
).exists()


@pytest.mark.skipif(not BUILT, reason="needs the built core/ and marts/ tables")
@pytest.mark.parametrize("path", QUERIES, ids=lambda p: p.name)
def test_example_query_runs_and_returns_rows(path):
    con = duckdb.connect()
    try:
        # relative file paths in the examples resolve from the repository root
        con.execute(f"SET file_search_path = '{ROOT}'")
        rows = con.execute(path.read_text()).fetchall()
    finally:
        con.close()
    assert rows, f"{path.name} returned no rows"


def test_every_query_is_listed_in_the_readme():
    readme = (ROOT / "docs" / "queries" / "README.md").read_text()
    for path in QUERIES:
        assert path.name in readme


@pytest.mark.skipif(not BUILT, reason="needs the built core/ and marts/ tables")
def test_building_registry_covers_every_building_with_unique_anchors():
    import pandas as pd

    reg = pd.read_csv(ROOT / "registry" / "building_id_registry.csv", dtype=str)
    b = pd.read_parquet(ROOT / "core" / "building.parquet")
    assert set(b["building_id"]) <= set(reg["building_id"])
    assert not reg.duplicated(["anchor_type", "anchor_value"]).any()


@pytest.mark.skipif(not BUILT, reason="needs the built core/ and marts/ tables")
def test_release_metadata_and_no_personal_columns():
    import re

    from phillyschools.release import datapackage, table_names

    pat = re.compile(
        r"leader|principal|email|phone|fax|liaison|inspector|superintendent|ssn|birth",
        re.IGNORECASE,
    )
    pkg = datapackage("0.0.0", "2026-01-01")
    names = {r["name"] for r in pkg["resources"]}
    assert (
        "core-school-metric" in names and "marts-school-year" in names and "marts-building" in names
    )
    for r in pkg["resources"]:
        assert r["hash"].startswith("sha256:") and r["schema"]["fields"]
        assert not [f["name"] for f in r["schema"]["fields"] if pat.search(f["name"])], r["name"]
    assert "school_metric__crdc" not in table_names() and "issues" not in table_names()
    flat = datapackage("0.0.0", "2026-01-01", url_prefix="https://example.org/dl")
    assert all(r["path"].startswith("https://example.org/dl/") for r in flat["resources"])


def test_finance_parsers():
    from phillyschools.finance import BEFC_ROW, _account_code, _aun, _fy_to_sy, _level

    assert _fy_to_sy("2023-24") == 2024 and _fy_to_sy("2015-16") == 2016
    assert _aun(126515001.0) == "126515001" and _aun(None) is None
    assert _account_code("Basic Education Funding 7110", "revenue_state") == "7110"
    assert (
        _account_code("Object 100 Personnel Services - Salaries", "expenditure_object") == "obj_100"
    )
    assert _account_code("Total Expenditures", "expenditure_function") == "total_expenditures"
    assert [_level(c) for c in ["7000", "7100", "7110", "7111"]] == [1, 2, 3, 4]
    row = (
        "Philadelphia City SD    Philadelphia      $1,418,543,037     $0      37%     "
        "$1,486,042,268     $40,046,952    $202,649,005   $242,695,957"
    )
    m = BEFC_ROW.match(row)
    assert m["name"] == "Philadelphia City SD" and m["county"] == "Philadelphia"
    assert m["gap"] == "1,418,543,037" and m["total"] == "242,695,957"


@pytest.mark.skipif(not BUILT, reason="needs the built core/ and marts/ tables")
def test_finance_tables_reconcile_with_the_commission_report():
    import pandas as pd

    from phillyschools.finance import BEFC_TOTALS

    a = pd.read_parquet(ROOT / "core" / "adequacy_befc_2024.parquet")
    assert len(a) == 500 and a["aun"].notna().all()
    for k, v in BEFC_TOTALS.items():
        assert abs(int(a[k].sum()) - v) <= 50, k
    m = pd.read_parquet(ROOT / "marts" / "district_finance.parquet")
    p = m[(m["lea_name"] == "Philadelphia City SD") & (m["sy"] == 2024)].iloc[0]
    assert abs(p["basic_education_funding_7110"] - 1_486_042_268) / 1_486_042_268 < 0.001


def test_school_budget_parser_handles_both_total_layouts():
    from phillyschools.school_budgets import parse_budget_text

    body = """
   2024-2025 School Budget Allotment Detail
   School Managed Allotments
        Basic Operating
          Teacher Allotment                                  1,000
        Basic Operating Total                                1,000
   School Managed Allotments Sub-total:                      1,000
   Centrally Managed Allotments
        Facilities Total                                       200
   Centrally Managed Allotments Sub-total:                     200
"""
    with_code = parse_budget_text(body + "   Test High School (1234) Total:      1,200\n")
    without = parse_budget_text(body + "   Test Career High School      1,200\n")
    for res in (with_code, without):
        assert res["sy"] == 2025
        kinds = [r["line_type"] for r in res["rows"]]
        assert kinds == [
            "item",
            "group_total",
            "scope_subtotal",
            "group_total",
            "scope_subtotal",
            "school_total",
        ]
        assert res["rows"][-1]["amount"] == 1200


def test_school_purchase_and_position_parsers():
    from phillyschools.school_budgets import (
        parse_positions_text,
        parse_purchase_text,
        position_vocab,
        split_position_parts,
    )

    purchases = """
   2015-2016 Summary of School Purchases
   Budget Allotments
    Funding Type                 Amount
    School Managed Allotments    100
    Total                        100
   School Based Positions
    Position                     Funding Type                 Count   Amount
    Principal                    School Managed Allotment     1.00    100
    Total                                                     1.00    100
   Discretionary Spending
    Expenditure Area             Funding Type                 Amount
    Total
"""
    res = parse_purchase_text(purchases)
    assert res["sy"] == 2016
    assert [(r["section"], r["line_type"]) for r in res["rows"]] == [
        ("budget_allotment", "item"),
        ("budget_allotment", "total"),
        ("position", "item"),
        ("position", "total"),
    ]
    assert parse_purchase_text("No data available for this school.")["rows"] == []

    positions = """
   2015-2016 Position Summary of School Purchases
PIDN      Position Name     Subject/Skill      Funding           Activity            Prev Curr
A0415O1 Teacher,Full Time   Biology 7-12       Basic Operating   Enrollment Driven   1.00   2.00
A0415O1 Teacher,Full Time   Math 7-12          Basic Operating   Enrollment Driven   1.00   1.00
A0415O1 Teacher,Full Time   Grades 7-8 | Grades Basic Operating   Enrollment Driven    0.00   3.00
                                    7-8 Science
"""
    rows = parse_positions_text(positions)["rows"]
    out = split_position_parts(rows, position_vocab(rows))
    assert [r["fte_curr"] for r in out] == [2.0, 1.0, 3.0]
    assert out[2]["funding"] == "Basic Operating"
    assert out[2]["subject_skill"].endswith("7-8 Science")


def test_header_code_reads_the_school_code():
    from phillyschools.school_budgets import header_code

    text = "   2015-2016 School Budget Allotment Detail\n   Lincoln, Abraham High School (8010)\n   FY16 School Budgets (April, 2015)\n"
    assert header_code(text) == "8010"
    assert header_code("No data available for this school.") is None


def test_closure_plan_registry_resolves_to_known_schools():
    import pandas as pd

    from phillyschools.closures import PLAN_CSV

    plan = pd.read_csv(PLAN_CSV, dtype=str).fillna("")
    assert len(plan) == 68
    assert plan["closing_school_id"].str.match(r"^sch_\d{5}$").all()
    assert set(plan["receiving_rule"]) == {"named", "either"}
    blank = plan[plan["receiving_school_id"] == ""]
    assert set(blank["receiving_name"]) == {"Vaux"}


def test_closure_registry_has_23_closed_schools():
    import pandas as pd

    from phillyschools.closure_flows import CLOSED_CSV

    reg = pd.read_csv(CLOSED_CSV, dtype=str)
    assert len(reg) == 23 and reg["school_id"].is_unique
    assert (reg["closed_after_sy"] == "2013").all()


def test_lineage_corrections_have_evidence():
    from phillyschools.identity import read_lineage_corrections

    lin = read_lineage_corrections()
    assert len(lin) >= 1
    assert lin["evidence"].str.len().gt(20).all()
    assert (lin["predecessor_school_id"] != lin["successor_school_id"]).all()


def test_open_questions_reference_real_gaps():
    from phillyschools.gaps import read_gaps, read_open_questions

    gap_ids = {g["gap_id"] for g in read_gaps()}
    questions = read_open_questions()
    ids = [q["question_id"] for q in questions]
    assert len(ids) == len(set(ids)) and len(ids) >= 10
    for q in questions:
        for gid in [x.strip() for x in q["related_gaps"].split(";") if x.strip()]:
            assert gid in gap_ids, (q["question_id"], gid)


def test_pde_per_pupil_parser_reads_a_building_sheet():
    from phillyschools.pde_school import PPE_DIR, read_ppe

    path = PPE_DIR / "2023-2024 per pupil expenditures.xlsx"
    if not path.exists():
        return
    df = read_ppe(path, "Bldg")
    assert df["sy"].eq(2024).all()
    assert df["aun"].str.len().eq(9).all()
    assert abs(df["adm"].sum() - 1629339.224) < 1


def test_measure_coverage_shares_are_valid():

    from phillyschools.marts import build_measure_coverage

    cov = build_measure_coverage()
    assert cov["share_with_value"].between(0, 1.0001).all()
    assert {"District", "Charter"} <= set(cov["governance"])


def test_pde_staff_summary_has_philadelphia_every_year():
    from phillyschools.pde_school import STAFF_SUMMARY_DIR, read_staff_summary

    if not list(STAFF_SUMMARY_DIR.glob("*.xlsx")):
        return
    df = read_staff_summary()
    years = set(df[df["aun"] == "126515001"]["sy"])
    assert years == set(range(2013, 2027))
