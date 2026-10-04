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
