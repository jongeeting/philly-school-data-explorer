"""The December 2012 closure proposal: which schools the district proposed to close and where
their students might go, as reported by the press. This is a proposal, not the outcome.

The March 7, 2013 School Reform Commission resolution, which set the final closures, is not
archived (GAP-038). Several proposed closures were dropped, and receiving schools offered as
choices ("either") do not say where students went. So these rows are plans, never lineage:
`school_lineage` stays limited to links a source states as having happened.
"""

import pandas as pd

from . import CORE, ROOT

PLAN_CSV = ROOT / "registry" / "closure_plan_2012.csv"
SOURCE_ID = "press_closure_proposal_2012-12"


def build_closure_plan() -> pd.DataFrame:
    plan = pd.read_csv(PLAN_CSV, dtype=str).fillna("")
    school = pd.read_parquet(CORE / "school.parquet").set_index("school_id")
    events = pd.read_parquet(CORE / "school_event.parquet")
    closed = events[events["event_type"] == "closed"].groupby("school_id")["sy"].min()
    plan["closing_name_in_list"] = plan["closing_school_id"].map(school["current_name"])
    plan["receiving_name_in_list"] = plan["receiving_school_id"].map(school["current_name"])
    plan["closing_school_closed_sy"] = plan["closing_school_id"].map(closed).astype("Int64")
    plan["closed_in_2013_wave"] = plan["closing_school_closed_sy"].isin([2013, 2014])
    plan["receiving_school_closed_sy"] = plan["receiving_school_id"].map(closed).astype("Int64")
    plan["stage"] = "proposed_2012-12"
    plan["status"] = "reported"
    plan["source_id"] = SOURCE_ID
    plan.insert(0, "plan_id", [f"cpl_{i:03d}" for i in range(1, len(plan) + 1)])
    return plan.drop(columns=["closing_name", "receiving_name"])


def write_closure_plan() -> pd.DataFrame:
    plan = build_closure_plan()
    plan.to_parquet(CORE / "school_closure_plan.parquet", index=False)
    plan.to_csv(CORE / "school_closure_plan.csv", index=False)
    return plan
