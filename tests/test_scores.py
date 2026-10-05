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
