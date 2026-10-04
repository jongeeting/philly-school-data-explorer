import pandas as pd
import pytest

from phillyschools.identity import STAGED_COLUMNS, build_identity, validate
from phillyschools.stage import (
    LONGITUDINAL,
    bridge_nces,
    canon_level,
    canon_text,
    parse_year_closed,
    repair_nces,
    stage_sdp_master_lists,
)

EMPTY_REGISTRY = pd.DataFrame(columns=["school_id", "ulcs", "minted_on"])


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ELEMENTARYMIDDLE", "Elementary-Middle"),
        ("Elementary-Middle", "Elementary-Middle"),
        ("MIDDLEHIGH", "Middle-High"),
        ("ELEMENTARYMIDDLEHIGH", "Elementary-Middle-High"),
        ("HIGH", "High"),
    ],
)
def test_level_vocabulary_is_unified_across_eras(raw, expected):
    assert canon_level(raw) == expected


def test_text_vocabulary():
    assert canon_text("DISTRICT") == canon_text("District") == "District"
    assert canon_text("  ") is None


@pytest.mark.parametrize(
    "raw,expected",
    [("open", None), ("2012-2013", 2013), (None, None), ("2015-2016", 2016)],
)
def test_year_closed_is_spring_year(raw, expected):
    assert parse_year_closed(raw) == expected


def row(ulcs, year, nces, source="reported"):
    return {"ulcs": ulcs, "year": year, "nces": nces, "nces_source": source if nces else None}


def test_nces_bridge_fills_only_when_neighbors_agree():
    d = pd.DataFrame(
        [
            row("1", 2023, "421899000001"),
            row("1", 2024, None),
            row("1", 2025, "421899000001"),
            row("2", 2023, "421899000002"),
            row("2", 2024, None),
            row("2", 2025, "421899000099"),
            row("3", 2023, None),
            row("3", 2024, None),
        ]
    )
    out = bridge_nces(d).set_index(["ulcs", "year"])
    assert out.loc[("1", 2024), "nces"] == "421899000001"
    assert out.loc[("1", 2024), "nces_source"] == "bridged"
    assert pd.isna(out.loc[("2", 2024), "nces"])  # neighbors disagree: left missing
    assert pd.isna(out.loc[("3", 2024), "nces"])  # nothing to bridge from


def test_nces_repair_from_xlsx_sibling():
    csv = pd.DataFrame([row("1", 2026, None), row("2", 2026, "421899000002")])
    xlsx = pd.DataFrame([row("1", 2026, "421899000001"), row("2", 2026, "421899000002")])
    fixed = repair_nces(csv, xlsx).set_index("ulcs")
    assert fixed.loc["1", "nces"] == "421899000001" and fixed.loc["1", "nces_source"] == "xlsx"
    assert fixed.loc["2", "nces_source"] == "reported"


def test_reported_closure_becomes_event_with_first_closed_year():
    base = {
        "aun": None,
        "schl": "1",
        "ulcs": "9",
        "src_id": None,
        "nces": None,
        "name": "Old School",
        "governance": "District",
        "category": None,
        "level": "High",
        "admission": None,
        "council_district": None,
        "gps": None,
        "school_key": None,
    }
    rows = [{**base, "year": y} for y in (2012, 2013)]
    df = pd.DataFrame(rows)[STAGED_COLUMNS]
    df["year_closed_sy"] = 2013
    df.loc[len(df)] = {
        **{c: None for c in df.columns},
        "ulcs": "8",
        "year": 2014,
        "schl": "2",
        "name": "Other",
        "governance": "District",
        "level": "High",
    }
    t = build_identity(df, EMPTY_REGISTRY)
    ev = t["school_event"]
    closed = ev[ev["event_type"] == "closed"].iloc[0]
    assert closed["sy"] == 2014 and closed["status"] == "reported"
    assert "no_longer_listed" not in set(ev["event_type"])  # reported closure replaces the guess
    assert validate(t) == []


@pytest.mark.skipif(not LONGITUDINAL.exists(), reason="raw files not archived")
def test_real_staging_spans_2002_to_latest_without_era_artifacts():
    d = stage_sdp_master_lists()
    assert d["year"].min() == 2002 and d["year"].nunique() == d["year"].max() - 2002 + 1
    t = build_identity(d, EMPTY_REGISTRY)
    assert validate(t) == []
    ev = t["school_event"]
    boundary = ev[(ev["sy"] == 2018) & ev["event_type"].isin(["governance_change", "level_change"])]
    assert (
        len(boundary) < 10
    )  # vocabulary is unified, so the 2017/2018 seam makes no wave of events
    assert (ev[ev["event_type"] == "closed"]["sy"] == 2014).sum() >= 25  # the 2013 closure round
