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
