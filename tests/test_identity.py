import pandas as pd
import pytest

from phillyschools.identity import STAGED_COLUMNS, build_identity, mint_ids, validate

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


def test_real_prototype_data_builds_and_validates():
    from phillyschools.cli import PROTOTYPE_INPUT

    if not PROTOTYPE_INPUT.exists():
        pytest.skip("prototype data not present")
    t = build_identity(pd.read_csv(PROTOTYPE_INPUT, dtype=str), EMPTY_REGISTRY)
    assert validate(t) == []
    assert len(t["school"]) == 338
