import pandas as pd
import pytest

from phillyschools.identity import (
    LOCATION_CORRECTIONS,
    STAGED_COLUMNS,
    build_identity,
    location_jumps,
    mint_ids,
    read_location_corrections,
    validate,
)

EMPTY_REGISTRY = pd.DataFrame(columns=["school_id", "ulcs", "minted_on"])


def staged(rows):
    base = {
        "aun": "126515001",
        "schl": "1",
        "ulcs": "1",
        "src_id": "10",
        "nces": "421899000001",
        "name": "A",
        "governance": "District",
        "category": "SDP K12 Schools",
        "level": "High",
        "admission": "Catchment",
        "council_district": "1",
        "gps": "39.9, -75.2",
    }
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["school_key"] = df["aun"] + "-" + df["schl"]
    return df[STAGED_COLUMNS].astype({"year": str})


def test_ids_are_permanent_and_append_only():
    reg = mint_ids(["20", "3"], EMPTY_REGISTRY, today="2026-10-04")
    assert list(reg["ulcs"]) == ["3", "20"] and list(reg["school_id"]) == ["sch_00001", "sch_00002"]
    again = mint_ids(["3", "20", "7"], reg, today="2026-10-05")
    assert list(again["school_id"][:2]) == ["sch_00001", "sch_00002"]
    assert again.loc[again["ulcs"] == "7", "school_id"].item() == "sch_00003"


def test_rebuild_is_stable():
    df = staged([{"year": 2025}, {"year": 2026}])
    first = build_identity(df, EMPTY_REGISTRY)
    second = build_identity(df, first["_registry"])
    assert first["school"]["school_id"].tolist() == second["school"]["school_id"].tolist()
    assert validate(first) == []


def test_name_governance_and_building_changes_keep_one_school_id():
    df = staged(
        [
            {"year": 2025, "name": "Foo Elementary", "governance": "District"},
            {"year": 2026, "name": "Foo Charter Academy", "governance": "Charter"},
        ]
    )
    t = build_identity(df, EMPTY_REGISTRY)
    assert len(t["school"]) == 1
    kinds = set(t["school_event"]["event_type"])
    assert {"governance_change", "name_change"} <= kinds
    assert (t["school_event"]["status"] == "derived").all()


def test_punctuation_only_name_change_is_not_an_event():
    df = staged(
        [{"year": 2025, "name": "St. Mary School"}, {"year": 2026, "name": "St Mary School"}]
    )
    t = build_identity(df, EMPTY_REGISTRY)
    assert "name_change" not in set(t["school_event"]["event_type"])


def test_xwalk_splits_runs_and_flags_shared_state_keys():
    df = staged(
        [
            {"year": 2024, "ulcs": "1", "schl": "5"},
            {"year": 2026, "ulcs": "1", "schl": "5"},
            {"year": 2026, "ulcs": "2", "schl": "9999", "src_id": "11", "nces": "421899000002"},
            {"year": 2026, "ulcs": "3", "schl": "9999", "src_id": "12", "nces": "421899000003"},
        ]
    )
    t = build_identity(df, EMPTY_REGISTRY)
    xw = t["school_id_xwalk"]
    sid = t["_registry"].set_index("ulcs").loc["1", "school_id"]
    runs = xw[(xw.school_id == sid) & (xw.id_type == "ulcs")]
    assert len(runs) == 2  # 2024 and 2026 are separate runs
    placeholder = xw[(xw.id_type == "state_key") & xw.id_value.str.endswith("-9999")]
    assert placeholder["shared_across_schools"].all()
    gaps = t["issues"][t["issues"]["type"].str.startswith("listing gap")]
    assert len(gaps) == 1


def test_duplicate_ulcs_year_keeps_first_and_reports():
    df = staged([{"year": 2025, "name": "First"}, {"year": 2025, "name": "Second"}])
    t = build_identity(df, EMPTY_REGISTRY)
    assert t["school_year_attr"]["name"].tolist() == ["First"]
    assert (t["issues"]["type"].str.startswith("duplicate")).any()


def test_validation_catches_broken_tables():
    t = build_identity(staged([{"year": 2026}]), EMPTY_REGISTRY)
    t["school_year_attr"] = pd.concat([t["school_year_attr"]] * 2)
    assert any("grain" in m for m in validate(t))


# Two schools trade places, as in the 2026-27 list's Kensington High and Pollock rows.
CUMBERLAND, RYAN, WELSH = "39.98483, -75.12640", "40.04561, -75.04421", "40.06012, -75.02713"


def two_schools(years_a, years_b):
    return staged(
        [{"year": y, "ulcs": "1", "gps": g} for y, g in years_a]
        + [{"year": y, "ulcs": "2", "src_id": "11", "gps": g} for y, g in years_b]
    )


def test_location_jump_onto_a_school_that_moved_away_fails_validation():
    df = two_schools([(2026, CUMBERLAND), (2027, RYAN)], [(2026, RYAN), (2027, WELSH)])
    t = build_identity(df, EMPTY_REGISTRY)
    jumps = location_jumps(t["school_year_attr"])
    assert jumps[["school_id", "sy", "prior_holder"]].values.tolist() == [
        ["sch_00001", 2027, "sch_00002"]
    ]
    assert any("jumps onto sch_00002" in m for m in validate(t))


def test_moving_into_a_shared_or_closed_building_is_not_a_jump():
    shared = two_schools([(2026, CUMBERLAND), (2027, RYAN)], [(2026, RYAN), (2027, RYAN)])
    closed = two_schools([(2026, CUMBERLAND), (2027, RYAN)], [(2026, RYAN)])
    for df in (shared, closed):
        assert location_jumps(build_identity(df, EMPTY_REGISTRY)["school_year_attr"]).empty


def test_location_corrections_replace_withhold_and_log():
    df = two_schools([(2026, CUMBERLAND), (2027, RYAN)], [(2026, RYAN), (2027, WELSH)])
    fixes = pd.DataFrame(
        [
            ["corr_loc_901", "sch_00002", 2026, "replace", 40.06012, -75.02713],
            ["corr_loc_902", "sch_00001", 2026, "withhold", None, None],
        ],
        columns=["correction_id", "school_id", "sy", "action", "lat", "lon"],
    ).assign(reason="stale GPS", corrected_on="2026-10-22", corrected_by="test")
    t = build_identity(df, EMPTY_REGISTRY, fixes)
    attr = t["school_year_attr"].set_index(["school_id", "sy"])
    assert attr.loc[("sch_00002", 2026), ["lat", "lon"]].tolist() == [40.06012, -75.02713]
    assert attr.loc[("sch_00002", 2026), "location_status"] == "derived"
    assert pd.isna(attr.loc[("sch_00001", 2026), "lat"])
    assert attr.loc[("sch_00001", 2026), "location_status"] == "invalid_in_source"
    assert attr.loc[("sch_00001", 2027), "location_status"] == "reported"
    log = t["correction"].set_index("correction_id")
    assert log.loc["corr_loc_901", "old_value"] == "40.04561, -75.04421"
    assert log.loc["corr_loc_901", "key"] == "sch_00002|2026"
    assert validate(t) == []
    unmatched = fixes.assign(sy=2020)
    with pytest.raises(ValueError, match="matches 0 rows"):
        build_identity(df, EMPTY_REGISTRY, unmatched)


def test_location_corrections_file_is_well_formed():
    if not LOCATION_CORRECTIONS.exists():
        pytest.skip("no location corrections")
    c = read_location_corrections()
    assert c["correction_id"].is_unique
    assert not c.duplicated(["school_id", "sy"]).any()
    assert set(c["action"]) <= {"replace", "withhold"}
    replace = c[c["action"] == "replace"]
    assert replace["lat"].between(39.8, 40.2).all() and replace["lon"].between(-75.3, -74.9).all()
    assert c.loc[c["action"] == "withhold", ["lat", "lon"]].isna().all().all()
    assert c[["reason", "evidence", "corrected_on", "corrected_by"]].notna().all().all()


def test_real_prototype_data_builds_and_validates():
    from phillyschools.cli import PROTOTYPE_INPUT

    if not PROTOTYPE_INPUT.exists():
        pytest.skip("prototype data not present")
    t = build_identity(pd.read_csv(PROTOTYPE_INPUT, dtype=str), EMPTY_REGISTRY)
    assert validate(t) == []
    assert len(t["school"]) == 338
