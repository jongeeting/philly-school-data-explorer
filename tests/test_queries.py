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
