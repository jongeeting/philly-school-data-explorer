import pandas as pd
import pytest

from phillyschools.enrollment import ENROLL_DIR, grade_code, placeholder_kind, read_table, to_count


@pytest.mark.parametrize(
    "raw,code",
    [
        ("0", "K"),
        ("00", "K"),
        ("K", "K"),
        ("1", "01"),
        ("09", "09"),
        ("12", "12"),
        ("All Grades", "ALL"),
    ],
)
def test_grade_codes_are_unified(raw, code):
    assert grade_code(raw) == code


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("151", (151.0, "reported")),
        (".", (None, "suppressed")),
        ("Data is Private", (None, "suppressed")),
        ("", (None, "not_reported")),
        (None, (None, "not_reported")),
    ],
)
def test_counts_keep_status(raw, expected):
    assert to_count(raw) == expected


def test_read_table_detects_excel_named_csv(tmp_path):
    xlsx = tmp_path / "really_excel.csv"
    pd.DataFrame({"School Year": ["2016-2017"], "Enrolled School ID": ["1010"]}).to_excel(
        xlsx, index=False
    )
    assert read_table(xlsx).loc[0, "Enrolled School ID"] == "1010"


@pytest.mark.parametrize(
    "name,kind",
    [
        ("Commonwealth Connections Academy", "cyber charter"),
        ("Central PA Digital Learning", "cyber charter"),
        ("School Lane Charter School", "charter outside the district list"),
        ("Student Transition Center", "program outside the district list"),
        ("Non Public Special Education", "non-public special education"),
    ],
)
def test_placeholder_kinds(name, kind):
    assert placeholder_kind(name) == kind


@pytest.mark.skipif(
    not any(ENROLL_DIR.glob("*.csv")) if ENROLL_DIR.exists() else True,
    reason="raw enrollment files not archived",
)
def test_real_enrollment_and_flows_are_consistent():
    from phillyschools.enrollment import build_enrollment, validate_enrollment
    from phillyschools.identity import load_registry

    t = build_enrollment(load_registry())
    assert validate_enrollment(t) == []
    e = t["enrollment"][t["enrollment"]["student_group"] == "all"]
    # Old files suppress small grade rows, so compare only school-years with no withheld rows.
    withheld = e[e["status"] != "reported"].groupby(["school_id", "sy"]).size()
    e = e[~e.set_index(["school_id", "sy"]).index.isin(withheld.index)]
    by_grade = e[e["grade"] != "ALL"].groupby(["school_id", "sy"])["count"].sum()
    totals = e[e["grade"] == "ALL"].groupby(["school_id", "sy"])["count"].sum()
    assert (by_grade - totals).abs().max() < 1  # school totals equal the sum of grades
    assert (
        t["catchment_flow"]["enrolled_school_id"].notna().all()
    )  # placeholders cover every destination
