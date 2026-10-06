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
