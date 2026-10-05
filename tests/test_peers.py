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
