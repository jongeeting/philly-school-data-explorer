import pandas as pd

from phillyschools.neighborhoods import allocate


def test_allocation_splits_by_population_and_level_and_keeps_unplaced():
    shares = pd.DataFrame(
        [
            # elementary catchment of school A: 75% of people in N1, 25% in N2
            {
                "school_id": "A",
                "level": "ES",
                "vintage": 2025,
                "neighborhood_id": "N1",
                "share": 0.75,
            },
            {
                "school_id": "A",
                "level": "ES",
                "vintage": 2025,
                "neighborhood_id": "N2",
                "share": 0.25,
            },
            # middle catchment of A: all in N2
            {
                "school_id": "A",
                "level": "MS",
                "vintage": 2025,
                "neighborhood_id": "N2",
                "share": 1.0,
            },
        ]
    )
    flows = pd.DataFrame(
        [
            {
                "sy": 2026,
                "catchment_school_id": "A",
                "catchment_status": "reported",
                "enrolled_school_id": "A",
                "count": 90.0,
            },
            {
                "sy": 2026,
                "catchment_school_id": None,
                "catchment_status": "not_available",
                "enrolled_school_id": "A",
                "count": 10.0,
            },
        ]
    )
    placed, unplaced = allocate(flows, shares, latest_vintage=2025)
    by_n = placed.groupby("neighborhood_id")["students_est"].sum()
    # K-8 weighting: 6/9 of 90 = 60 to ES (45 N1, 15 N2); 3/9 = 30 to MS (all N2)
    assert round(by_n["N1"], 6) == 45 and round(by_n["N2"], 6) == 45
    assert unplaced["count"].sum() == 10  # never dropped
    assert round(placed["students_est"].sum() + unplaced["count"].sum(), 6) == 100
