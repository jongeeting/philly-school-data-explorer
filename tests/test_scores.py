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
