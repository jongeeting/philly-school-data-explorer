import math

import numpy as np
import pandas as pd

from phillyschools.acs import cells_moe, pct_moe, reliability


def test_proportion_moe_matches_census_formula():
    # p = 30/100; MOE = sqrt(10^2 - 0.3^2 * 15^2) / 100 * 100
    expected = math.sqrt(10**2 - 0.3**2 * 15**2)
    assert pct_moe([30], [100], [10], [15])[0] == round(expected, 1)


def test_proportion_moe_falls_back_to_ratio_formula():
    # radicand 2^2 - 0.9^2 * 20^2 < 0 -> use sqrt(2^2 + 0.9^2 * 20^2)
    expected = math.sqrt(2**2 + 0.9**2 * 20**2) / 100 * 100
    assert pct_moe([90], [100], [2], [20])[0] == round(expected, 1)
    assert np.isnan(pct_moe([0], [0], [5], [5])[0])


def test_zero_cells_count_their_largest_moe_once():
    t = pd.DataFrame(
        {
            "X_E001": [10, 0],
            "X_M001": [3, 7],
            "X_E002": [0, 0],
            "X_M002": [5, 9],
            "X_E003": [0, 4],
            "X_M003": [4, 2],
        }
    )
    m = cells_moe(t, ["X_E001", "X_E002", "X_E003"])
    assert m.iloc[0] == math.sqrt(3**2 + 5**2)  # one zero cell's MOE (largest of 5 and 4)
    assert m.iloc[1] == math.sqrt(2**2 + 9**2)  # nonzero 4 (MOE 2) plus largest zero MOE 9
    neg = pd.DataFrame({"X_E001": [5], "X_M001": [-222222222]})
    assert cells_moe(neg, ["X_E001"]).iloc[0] == 0  # special codes are missing, not huge


def test_reliability_labels():
    v = pd.Series([50.0, 50.0, 50.0, 0.0, 10.0])
    m = pd.Series([5.0, 20.0, 40.0, 3.0, None])
    _cv, label = reliability(v, m)
    assert list(label) == ["high", "medium", "low", "low", ""]


def test_position_robust_flags_peer_sets_within_the_margin():
    from phillyschools.peers import compare

    v = pd.DataFrame(
        {
            "school_id": [f"s{i:02d}" for i in range(40)],
            "band": "k8",
            "poverty_pct": [float(i) for i in range(40)],
            "value": [float(i) for i in range(40)],
            "basis_moe": 0.0,
        }
    )
    r = compare(v, k=15).set_index("school_id")
    assert r["position_robust"].all()  # no margin: positions cannot move
    v["basis_moe"] = 20.0
    v.loc[20, "value"] = 25.0  # a little above its immediate peers
    r = compare(v, k=15).set_index("school_id")
    assert not r.loc["s20", "position_robust"]  # a 20-point margin moves its peer set
