from pathlib import Path

import pandas as pd

CROSSWALK = Path(__file__).parent.parent / "prototype" / "data" / "crosswalk.csv"


def test_ulcs_is_unique():
    cw = pd.read_csv(CROSSWALK, dtype=str)
    assert cw["ulcs"].is_unique


def test_school_key_matches_aun_and_schl():
    cw = pd.read_csv(CROSSWALK, dtype=str)
    assert (cw["school_key"] == cw["aun"] + "-" + cw["schl"]).all()


def test_shared_state_keys_are_flagged():
    cw = pd.read_csv(CROSSWALK, dtype=str)
    dup = cw["school_key"].duplicated(keep=False)
    assert (cw.loc[dup, "state_key_shared"] == "True").all()
