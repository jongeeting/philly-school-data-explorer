import pandas as pd
import pytest

from phillyschools.metrics import validate_metric
from phillyschools.scores import FR_DIR, parse_value


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("78.4%", (78.4, "reported")),
        (".4", (0.4, "reported")),
        ("100", (100.0, "reported")),
        ("IS", (None, "suppressed")),
        ("Insufficient Sample", (None, "suppressed")),
        ("Insufficient Testers", (None, "suppressed")),
        ("Suppress:Data Does Not Apply", (None, "not_applicable")),
        ("Not Applicable", (None, "not_applicable")),
        ("", (None, "not_reported")),
        (None, (None, "not_reported")),
        ("blueup", (None, "not_reported")),
    ],
)
def test_values_keep_status(raw, expected):
    assert parse_value(raw) == expected


def test_metric_grain_and_dictionary_are_enforced():
    good = pd.DataFrame(
        [
            {
                "school_id": "s",
                "sy": 2025,
                "measure_id": "pct_proficient_ela",
                "student_group": "all",
                "value": 50.0,
                "status": "reported",
                "source_id": "x",
            }
        ]
    )
    assert validate_metric(good) == []
    dup = pd.concat([good, good])
    assert any("grain" in p for p in validate_metric(dup))
    unknown = good.assign(measure_id="made_up_measure")
    assert any("not defined" in p for p in validate_metric(unknown))


@pytest.mark.skipif(
    not any(FR_DIR.glob("Datafile_*.xlsx")) if FR_DIR.exists() else True,
    reason="Future Ready files not archived",
)
def test_real_scores_statuses():
    m = pd.read_parquet(FR_DIR.parents[1] / "core" / "school_metric__future_ready.parquet")
    tests_2020 = m[
        (m["sy"] == 2020) & (m["measure_id"] == "pct_proficient_ela") & m["value"].notna()
    ]
    assert (tests_2020["status"] == "carried_forward").all()  # no spring 2020 tests
    sci_2025 = m[(m["sy"] == 2025) & (m["measure_id"] == "pct_proficient_science")]
    assert (sci_2025["status"] == "waived").mean() > 0.9  # science waived statewide
    shared = m[m["status"] == "not_separately_measurable"]
    assert shared["value"].isna().all()  # never a blended number for a non-host program


@pytest.mark.parametrize(
    "raw,label",
    [
        ("3", "03"),
        ("11", "11"),
        ("All Grades", "ALL"),
        ("3 to 8", "03-08"),
        ("Grades 3-8", "03-08"),
    ],
)
def test_assessment_grades(raw, label):
    from phillyschools.assessment import grade_label

    assert grade_label(raw) == label


def test_assessment_groups_keep_old_asian_pacific_category_separate():
    from phillyschools.assessment import GROUPS

    assert GROUPS["asian/pacific islander (not hispanic)"] == "asian_pacific_islander"
    assert GROUPS["asian (not hispanic)"] == "asian"


@pytest.mark.skipif(
    not (FR_DIR.parent / "pde_fast_facts").exists(), reason="Fast Facts not archived"
)
def test_fast_facts_enrollment_matches_district_counts():
    core = FR_DIR.parents[1] / "core"
    m = pd.read_parquet(core / "school_metric__fast_facts.parquet")
    st = m[(m["measure_id"] == "state_enrollment") & (m["status"] == "reported")]
    e = pd.read_parquet(core / "enrollment.parquet")
    d = e[(e["grade"] == "ALL") & (e["student_group"] == "all") & (e["status"] == "reported")]
    x = st.merge(d, on=["school_id", "sy"])
    assert len(x) > 1000 and x["value"].corr(x["count"]) > 0.99
    attr = pd.read_parquet(core / "school_state_attr.parquet")
    assert set(attr["title_i"].dropna()) <= {"Yes", "No"}


@pytest.mark.parametrize(
    "cat,grp,out",
    [
        ("All Students", "All Students", "all"),
        ("Grade Level", "00", "grade_K"),
        ("Grade Level", "9", "grade_09"),
        ("Race/Ethnicity", "Hispanic/Latino", "hispanic"),
        ("Gender", "Non-Binary", "non_binary"),
    ],
)
def test_attendance_groups(cat, grp, out):
    from phillyschools.attendance import _group

    assert _group(cat, grp) == out


def test_incident_frames_accept_each_archive_header_style():
    from phillyschools.discipline import _incident_frame

    old = pd.DataFrame(
        {
            "ULCS_NO": ["6400"],
            "SCHOOL_YEAR": ["2012-2013"],
            "INCIDENT_TYPE": ["BULLYING"],
            "INCIDENT_COUNT": ["0"],
            "SCHOOL_ID": ["640"],
        }
    )
    new = pd.DataFrame(
        {
            "School Year": ["2024-2025"],
            "Sector": ["District"],
            "ULCS Code": ["1010"],
            "School Name": ["x"],
            "Incident Type": ["Assaults"],
            "# of Incidents": ["3"],
        }
    )
    a, b = _incident_frame(old), _incident_frame(new)
    assert a.loc[0, "sy"] == 2013 and a.loc[0, "ulcs"] == "6400" and a.loc[0, "raw"] == "0"
    assert (
        b.loc[0, "sy"] == 2025
        and b.loc[0, "incident_type"] == "Assaults"
        and b.loc[0, "raw"] == "3"
    )


@pytest.mark.parametrize(
    "col, action, out",
    [
        ("M_BLA_7_MULT_SUS_NO_DIS", "MULTOOS", "SCH_DISCWODIS_MULTOOS_BL_M"),
        ("F_TOT_7_SINGLE_SUS_NO_DIS", "SINGOOS", "TOT_DISCWODIS_SINGOOS_F"),
        ("M_2_OR_MORE_7_LAW_DIS", "REF", "SCH_DISCWDIS_REF_IDEA_TR_M"),
        ("F_TOT_IDEA_7_IN_SCH_SUS_DIS", "ISS", "TOT_DISCWDIS_ISS_IDEA_F"),
        ("M_504_7_EXP_SERV_DIS", "EXPWE", "SCH_DISCWDIS_EXPWE_504_M"),
        ("F_HI_PAC_7_ENROL", None, "SCH_ENR_HP_F"),
        ("M_DIS_IDEA_7_ENROL", None, "SCH_ENR_IDEA_M"),
        ("M_TOT_7_ENROL", None, "TOT_ENR_M"),
        ("Incomplete", None, None),
    ],
)
def test_crdc_2011_12_names_translate(col, action, out):
    from phillyschools.crdc import _rename_2012

    assert _rename_2012(col, action) == out


def test_crdc_groups_are_disjoint_and_add_up():
    from phillyschools.crdc import collection_rows

    cols = {
        "TOT_ENR_M": 60,
        "TOT_ENR_F": 40,
        "SCH_ENR_IDEA_M": 10,
        "SCH_ENR_IDEA_F": 5,
        "SCH_ENR_504_M": 3,
        "SCH_ENR_504_F": 2,
        "TOT_DISCWODIS_SINGOOS_M": 4,
        "TOT_DISCWODIS_SINGOOS_F": 2,
        "TOT_DISCWODIS_MULTOOS_M": 1,
        "TOT_DISCWODIS_MULTOOS_F": 0,
        "TOT_DISCWDIS_SINGOOS_IDEA_M": 2,
        "TOT_DISCWDIS_SINGOOS_IDEA_F": 1,
        "TOT_DISCWDIS_MULTOOS_IDEA_M": 1,
        "TOT_DISCWDIS_MULTOOS_IDEA_F": 0,
        "SCH_DISCWDIS_SINGOOS_504_M": 1,
        "SCH_DISCWDIS_SINGOOS_504_F": 0,
        "SCH_DISCWDIS_MULTOOS_504_M": 0,
        "SCH_DISCWDIS_MULTOOS_504_F": -2,  # suppressed cell
    }
    d = pd.DataFrame([{k: str(v) for k, v in cols.items()}], index=["421899000001"])
    r = collection_rows(d, 2022).set_index(["measure_id", "student_group"])
    assert r.loc[("crdc_enrollment", "without_disabilities"), "value"] == 100 - 15 - 5
    assert r.loc[("crdc_n_oss", "idea"), "value"] == 4
    assert r.loc[("crdc_n_oss", "all"), "status"] == "suppressed"  # a 504 cell is suppressed
    assert r.loc[("crdc_n_oss", "without_disabilities"), "value"] == 7


@pytest.mark.parametrize(
    "name, out",
    [
        ("7300-Hopkinson_11-2025_6-Month Report.pdf", (2025, 11)),
        ("7300_Hopkinson_ES_2018_2019_3_Year_AHERA_Report.pdf", (2019, 0)),
        ("2050-Powel_2021_3-Year.pdf", (2021, 0)),  # the building code is not a year
        ("1290-Hamilton_8-20256-Month Report.pdf", (2025, 8)),
    ],
)
def test_environmental_report_dates(name, out):
    from phillyschools.environmental import report_date

    assert report_date(name) == out


def test_environmental_keeps_latest_per_building_and_type():
    from phillyschools.environmental import select_latest

    plan_dir = "ahera/Hopkinson, Francis/AHERA Management Plan Archive"
    names = [
        ("7300-Hopkinson_5-2025_6-Month Report.pdf", plan_dir),
        ("7300-Hopkinson_11-2025_6-Month Report.pdf", plan_dir),
        ("7301-Hopkinson LSH_5-2025_6-Month Report.pdf", plan_dir),
        ("7300-Hopkinson_2023_3-Year.pdf", plan_dir),
        ("16 7300 Francis Hopkinson ES.pdf", plan_dir),
        ("2026-01-20 7300 Bulk PLM Results", "ahera/Hopkinson, Francis/Bulk Sampling"),
        ("Results 2025.pdf", "water/Search by Site/Elementary/Hopkinson"),
        ("Results 2021.pdf", "water/Search by Site/Elementary/Hopkinson/Archives"),
    ]
    rows = [
        {"source_key": "sdp_environmental", "url": n, "filename": n, "subdir": d} for n, d in names
    ]
    got = {r["filename"] for r in select_latest(rows)}
    assert got == {
        "7300-Hopkinson_11-2025_6-Month Report.pdf",
        "7301-Hopkinson LSH_5-2025_6-Month Report.pdf",
        "7300-Hopkinson_2023_3-Year.pdf",
        "16 7300 Francis Hopkinson ES.pdf",
        "Results 2025.pdf",
    }


def test_xrf_rows_read_damage_across_layouts():
    from phillyschools.envresults import xrf_rows

    lines = [
        "1  1  108  Classroom 108  W1  Sheetrock  White  Flaking   1   0.1 Negative",
        "1  1  100  Auditorium  W1  Plaster  White  Peeling  12  N/A  N/A  2.8  Positive",
        "1  PH  PH-1  Tank Room  no  Door  Wood  Varnish  Chipping  8  0  Negative",
        "1  1  102  Classroom 102  Ceiling  Concrete  Unpainted  N/A  N/A  N/A  N/A",
    ]
    text = "\n".join(lines)
    x = xrf_rows(text)
    assert x["damaged_sf"].tolist() == [1, 12, 8]
    assert x["positive"].tolist() == [False, True, False]
    assert x["xrf"].tolist() == [0.1, 2.8, 0]


@pytest.mark.parametrize(
    "addr, out",
    [
        ("4901-31 CHESTNUT ST", (4901, 4931, "CHESTNUT ST")),
        ("600 W. Hunting Park Avenue", (600, 600, "W HUNTING PARK AVE")),
        ("1501 S 7th St", (1501, 1501, "S 07TH ST")),
        ("1501 S 07th St", (1501, 1501, "S 07TH ST")),
        ("6501 Limekiln Pike", (6501, 6501, "LIMEKILN PK")),
    ],
)
def test_split_address(addr, out):
    from phillyschools.envresults import split_address

    assert split_address(addr) == out


def test_water_rows_initial_and_follow_up():
    from phillyschools.envresults import water_rows

    lines = [
        "07/11/2025    01       01       FT         House kitchen sink             <1.0       1       BA",
        "08/15/2025    00       10       FT         In kitchen      54       1   AA",
        "09/09/2025        00       10      FT             In kitchen     3.6    1    Remediation Complete.",
        "08/22/2025    02       25       HS         Hallway       2.3 J      1       BA",
    ]
    w = water_rows("\n".join(lines))
    assert w["lead_ppb"].tolist() == [1.0, 54.0, 3.6, 2.3]
    assert w["below_reporting_limit"].tolist() == [True, False, False, False]
    assert w["above_action_level"].tolist() == [False, True, False, False]
    assert w["estimated"].tolist() == [False, False, False, True]
    assert w["corrective_action"].tolist()[2] == "Remediation Complete."


def test_water_letter_stated_counts():
    from phillyschools.envresults import stated_counts

    text = (
        "There were Three (3) outlets tested at your school. Of those outlets, Three (3) "
        "outlets produced water that was below the action level of 10 ppb. No water outlets "
        "were found to have results above the water safety threshold."
    )
    assert stated_counts(text) == (3, 0)
    text = "There were 12 outlets tested at your school. One (1) water outlet was found to have results above"
    assert stated_counts(text) == (12, 1)


def test_xrf_rows_skip_trailing_asbestos_column():
    from phillyschools.envresults import xrf_rows

    line = "2  GT2  Restroom 208  W4  CMU  Pink  Flaking   1 N/A   N/A   0.76 Positive   Negative"
    x = xrf_rows(line)
    assert x["positive"].tolist() == [True] and x["damaged_sf"].tolist() == [1]


def test_asbestos_room_log_rows():
    from phillyschools.asbestos import log_rows, material_group, summarize

    lines = [
        "ROOM-BY-ROOM LOG",
        '    1          1         001K    Classroom K-1    Floor Tile VAT 9" x 9"    Confirmed    798    SF    0    SF    Multi',
        "    1          1         001K    Classroom K-1    Paint associated with Convector    NAD    30    SF    N/A    SF",
        "    1          1         001K    Classroom K-1    Heating Convector    Non Suspect ACM    2    EA    N/A    EA",
        "    1          B         B-12    Boiler Room    Pipe Fitting Insulation    Assumed    1,200    LF    12    LF",
    ]
    log = log_rows("\n".join(lines))
    assert log["acm_status"].tolist() == ["Confirmed", "NAD", "Non-Suspect", "Assumed"]
    s = summarize(log)
    assert (s["acm_items"], s["acm_items_damaged"], s["acm_lf"], s["acm_damaged_lf"]) == (
        2,
        1,
        1200,
        12,
    )
    assert material_group("Pipe Fitting Insulation") == "pipe and boiler insulation"
    assert material_group("Mastic associated with Floor Tile") == "floor tile and mastic"


def test_fca_report_parts_wrap_and_systems():
    from phillyschools.fca import parse_report

    lines = [
        "S802001;Northeast",
        "            Governance               District          Report Type              High",
        "            Address                  1601 Cottman Ave   Enrollment               3,000",
        "Building and Grounds",
        "Overall                 23.47%          $51,098,552          $217,723,791",
        "B802001;Northeast       23.85%          $44,057,009          $184,721,264",
        "B802903;Northeast - Stands and",
        "                         6.66%            $306,088            $4,596,630",
        "Field",
        "G802001:Grounds         1.74%             $289,211           $16,667,327",
        "Major Building Systems",
        "Exterior Doors          108.99%           $207,751             $190,610",
        "Please note that some FCIs may be over 100%",
        "Table of Contents",
        "  Condition Score:       76.53%",
    ]
    text = "\n".join(lines)
    r = parse_report(text)
    assert r["site"]["fci_pct"] == 23.47 and r["site"]["report_type"] == "High"
    assert r["site"]["address"] == "1601 Cottman Ave" and r["site"]["enrollment"] == "3,000"
    assert [p["part_name"] for p in r["parts"]] == [
        "Northeast",
        "Northeast - Stands and Field",
        "Grounds",
    ]
    assert r["systems"][0]["fci_pct"] == 108.99
    assert r["site"]["condition_score_pct"] == 76.53


def test_asbestos_metric_adds_buildings_of_one_school():
    import pandas as pd

    from phillyschools.asbestos import asbestos_metric

    rep = pd.DataFrame(
        {
            "school_id": ["sch_1", "sch_1", "sch_2, sch_3"],
            "is_latest": [True, True, True],
            "report_year": [2025, 2026, 2025],
            "report_month": [11, 1, 5],
            "acm_items": [100, 20, 50],
            "acm_items_damaged": [3, 1, 0],
        }
    )
    m = asbestos_metric(rep)
    assert not m.duplicated(["school_id", "sy", "measure_id", "student_group"]).any()
    one = m[m["school_id"] == "sch_1"].set_index("measure_id")["value"]
    assert one["asbestos_items"] == 120 and one["asbestos_items_damaged"] == 4
    assert set(m["school_id"]) == {"sch_1", "sch_2", "sch_3"}


@pytest.mark.parametrize(
    "raw, out",
    [
        ("1231 N. BROAD ST. - 3RD FLR", "1231 N. BROAD ST"),
        ("550 N BROAD ST, SCIENCE LEADERSHIP ACADEMY, SUITE 202", "550 N BROAD ST"),
        ("7001 Buist Avenue,", "7001 Buist Avenue"),
        ("4641 Roosevelt Blvd RM M1-24", "4641 Roosevelt Blvd"),
    ],
)
def test_building_clean_address(raw, out):
    from phillyschools.buildings import clean_address

    assert clean_address(raw) == out


@pytest.mark.parametrize(
    "name, kind",
    [
        ("Penrose Little School House", "little_school_house"),
        ("Hopkinson, Francis LSH", "little_school_house"),
        ("Catharine School Annex-Truancy Court", "annex"),
        ("Germantown Field (Fieldhouse)", "field_house"),
        ("Lincoln Pool & Field House", "field_house"),
        ("Sayre Pool", "pool"),
        ("Tasker Street Garage", "garage_or_barn"),
        ("John Bartram High School", "school_building"),
    ],
)
def test_building_kind(name, kind):
    from phillyschools.buildings import kind_of

    assert kind_of(name) == kind


def test_building_clusters_merge_same_place_but_keep_annexes_apart():
    import pandas as pd

    from phillyschools.buildings import cluster

    c = pd.DataFrame(
        {
            "source": ["master", "lead", "master", "ahera", "fca", "master"],
            "name": [
                "Franklin HS",
                "Franklin HS",
                "Day School",
                "Day Little School House",
                "Day LSH",
                "Other School",
            ],
            "address": [
                "550 N BROAD ST",
                "550 N. Broad St - 3rd Flr",
                "6324 CRITTENDEN ST",
                "6324-42 Crittenden Street",
                None,
                "100 S BROAD ST",
            ],
            "school_ids": ["sch_1", "sch_1", "sch_2", "sch_2", "sch_2", "sch_3"],
            "ahera_code": [None, None, None, "6201", "6201", None],
        }
    )
    cl = cluster(c).tolist()
    assert cl[0] == cl[1]  # same building, suite text ignored
    assert cl[3] == cl[4]  # shared AHERA code
    assert cl[2] != cl[3]  # little school house stays apart from the main building
    assert cl[5] not in (cl[0], cl[2])


def test_building_ids_are_stable_and_never_reused_for_a_split():
    import pandas as pd

    from phillyschools.buildings import assign_ids

    g1 = pd.DataFrame({"source": ["ahera"], "key": ["8420"], "ahera_code": ["8420"]})
    g2 = pd.DataFrame({"source": ["ahera"], "key": ["8421"], "ahera_code": ["8421"]})
    ids, reg = assign_ids(
        {0: g1, 1: g2},
        pd.DataFrame(columns=["building_id", "anchor_type", "anchor_value", "minted_on"]),
    )
    assert ids == {0: "bld_00001", 1: "bld_00002"}
    again, _ = assign_ids({5: g2, 6: g1}, reg)  # reordered clusters keep their IDs
    assert again == {5: "bld_00002", 6: "bld_00001"}
    both = pd.concat([g1, g2], ignore_index=True)  # one cluster that spans both anchors
    merged, _ = assign_ids({0: both}, reg)
    assert merged[0] == "bld_00001"
    split_ids, _ = assign_ids(
        {0: g1.assign(ahera_code="8420"), 1: g1.assign(key="8420x", ahera_code="8420")}, reg
    )
    assert len(set(split_ids.values())) == 2  # a split cluster cannot reuse a taken ID


def _cand(method, opa, addr, owner="X LLC"):
    return {"method": method, "opa_account": opa, "parcel_address": addr, "parcel_owner": owner}


def test_resolve_parcel_prefers_address_text_over_a_map_point():
    from phillyschools.buildings import resolve_parcel

    r = resolve_parcel(
        [
            _cand("school_map_point", "111", "1500 W CUMBERLAND ST"),  # a neighbor's parcel
            _cand("opa_property_address", "222", "2539 N 16TH ST"),
            _cand("city_address_overlap", "222", "2539-49 N 16TH ST"),
        ],
        "2539 N 16TH ST",
    )
    assert r["opa_account"] == "222" and r["confidence"] == "high" and r["conflict"] == "111"


def test_resolve_parcel_treats_subaccounts_of_one_parcel_as_one():
    from phillyschools.buildings import resolve_parcel

    r = resolve_parcel(
        [
            _cand("school_map_point", "786002100", "9125 ACADEMY RD", "SCHOOL DISTRICT OF PHILA"),
            _cand("opa_property_address", "786002105", "9125 ACADEMY RD"),
        ],
        "9125 Academy Rd",
    )
    assert r["opa_account"] == "786002100" and r["confidence"] == "high" and r["conflict"] is None


def test_resolve_parcel_confidence_levels():
    from phillyschools.buildings import resolve_parcel

    corner = resolve_parcel(
        [_cand("school_map_point", "5", "4201 SPRUCE ST", "SCHOOL DISTRICT OF PHILA")],
        "4209 Spruce St",
    )
    assert corner["confidence"] == "medium"  # a School District parcel at a school's point
    weak = resolve_parcel([_cand("school_map_point", "6", "3900 JASPER ST")], "1840 Torresdale Ave")
    assert weak["confidence"] == "low"
    assert resolve_parcel([], "1 Main St") == {}


def test_judge_accepts_only_trustworthy_geocode_results():
    from phillyschools.building_parcels import judge

    overlap = lambda a, b: a.split()[0] == str(b).split()[0]
    base = {"opa_account": "1", "distance_m": 3.0, "match": "nearest", "geocode": "Exact"}
    assert judge(
        {**base, "parcel_address": "800 X ST", "parcel_owner": "A"}, "N", "800 X ST", overlap
    )
    assert (
        judge(
            {**base, "parcel_address": "4431 ALMOND ST", "parcel_owner": "ARCHDIOCESE"},
            "Annex",
            "4435 ALMOND ST",
            overlap,
        )
        is None
    )
    door = judge(
        {**base, "parcel_address": "4431 ALMOND ST", "parcel_owner": "ARCHDIOCESE"},
        "Annex",
        "4435 ALMOND ST",
        overlap,
        near_number=True,
    )
    assert door == "geocode_next_door"
    private = {**base, "parcel_address": "324 H ST", "parcel_owner": "SPINKS JOHN"}
    assert judge(private, "Field House", "342 H ST", overlap) is None


def test_cover_parser_reads_both_layouts():
    from phillyschools.buildings import parse_cover

    new = (
        "  JOHN BARTRAM HIGH SCHOOL\n     ULCS # 1010\n  2401 South 67th Street\n"
        "  Philadelphia, Pennsylvania 19142\n  Year Built: 1939\n"
    )
    c = parse_cover(new)
    assert (c["address"], c["zip"], c["year_built"], c["ulcs_codes"]) == (
        "2401 South 67th Street",
        "19142",
        1939,
        ["1010"],
    )
    old = (
        "for the\nPaul Robeson High School\nULCS# 1050\nBuilding # B105001-1\n"
        "4125 Ludlow Street\nPhiladelphia, Pennsylvania\n19104\n"
    )
    o = parse_cover(old)
    assert (o["address"], o["zip"], o["fca_ref"]) == ("4125 Ludlow Street", "19104", "B105001")
    multi = parse_cover(
        "PLA WEST\nULCS # 1590/8460/1450\n4300 Westminster Avenue\nPhiladelphia, PA 19104"
    )
    assert multi["ulcs_codes"] == ["1590", "8460", "1450"]


def test_building_ids_follow_anchors_when_a_building_splits():
    import pandas as pd

    from phillyschools.buildings import assign_ids

    empty = pd.DataFrame(columns=["building_id", "anchor_type", "anchor_value", "minted_on"])
    both = pd.DataFrame(
        {
            "source": ["ahera", "master"],
            "key": ["5330", "sch_1|1 A ST"],
            "ahera_code": ["5330", None],
        }
    )
    ids, reg = assign_ids({0: both}, empty)
    first = ids[0]
    assert set(reg["building_id"]) == {first}
    # the building later splits in two: each part keeps a distinct ID and records its anchors
    a = both.iloc[[0]]
    b = both.iloc[[1]]
    ids2, reg2 = assign_ids({0: a, 1: b}, reg)
    assert ids2[0] != ids2[1] and first in ids2.values()
    homes = dict(
        zip(
            zip(reg2["anchor_type"], reg2["anchor_value"], strict=True),
            reg2["building_id"],
            strict=True,
        )
    )
    assert (
        homes[("ahera_code", "5330")] == ids2[0]
        and homes[("master_address", "sch_1|1 A ST")] == ids2[1]
    )
    ids3, reg3 = assign_ids({0: a, 1: b}, reg2)  # the next run finds the same IDs
    assert ids3 == ids2 and len(reg3) == len(reg2)
