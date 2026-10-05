import pandas as pd

from phillyschools.peers import compare


def _schools(n, band="k8"):
    return pd.DataFrame(
        {
            "school_id": [f"s{i:02d}" for i in range(n)],
            "band": band,
            "poverty_pct": [50 + i for i in range(n)],
            "value": [30.0] * n,
        }
    )


def test_positions_against_closest_poverty_peers():
    v = _schools(20)
    v.loc[0, "value"] = 60.0  # far above everyone
    v.loc[19, "value"] = 5.0  # far below
    r = compare(v, k=15).set_index("school_id")
    assert r.loc["s00", "position"] == "above peer range"
    assert r.loc["s19", "position"] == "below peer range"
    assert r.loc["s10", "position"] == "within peer range"
    peers = r.loc["s00", "peer_school_ids"].split("|")
    assert len(peers) == 15 and "s00" not in peers and "s01" in peers  # nearest in poverty


def test_too_few_schools_is_reported_not_dropped():
    r = compare(_schools(10, band="mixed"), k=15)
    assert len(r) == 10 and r["exclusion"].str.startswith("fewer than").all()


def test_missing_poverty_is_reported_not_dropped():
    v = _schools(20)
    v.loc[3, "poverty_pct"] = None
    r = compare(v, k=15).set_index("school_id")
    assert r.loc["s03", "exclusion"] == "no poverty figure on this basis"
    assert len(r) == 20


def test_area_context_citywide_figures_are_plausible():
    import pytest

    from phillyschools import CORE

    path = CORE / "area_context.parquet"
    if not path.exists():
        pytest.skip("ACS not built")
    a = pd.read_parquet(path)
    t = a[(a["unit_type"] == "tract") & (a["measure_id"] == "acs_pct_children_in_poverty")]
    city = t["numerator"].sum() / t["denominator"].sum() * 100
    assert 20 < city < 40 and t["unit_id"].nunique() == 408
