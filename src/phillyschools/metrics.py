"""school_metric is assembled from parts so separate builds never overwrite each other.

Grain: one row per school x sy x measure x student group. Each build writes its own part
(core/school_metric__<part>.parquet); every write rebuilds core/school_metric from all parts
and checks the grain and that every measure is defined in registry/measures.csv.
"""

import pandas as pd

from . import CORE, ROOT

MEASURES = ROOT / "registry" / "measures.csv"
COLUMNS = ["school_id", "sy", "measure_id", "student_group", "value", "status", "source_id"]


def write_metric_part(part: str, df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "student_group" not in df:
        df["student_group"] = "all"
    df = df[COLUMNS]
    df.to_parquet(CORE / f"school_metric__{part}.parquet", index=False)
    return rebuild_school_metric()


def rebuild_school_metric() -> pd.DataFrame:
    parts = sorted(CORE.glob("school_metric__*.parquet"))
    combined = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    problems = validate_metric(combined)
    if problems:
        raise ValueError("school_metric invalid: " + "; ".join(problems))
    combined.to_parquet(CORE / "school_metric.parquet", index=False)
    combined.to_csv(CORE / "school_metric.csv", index=False)
    return combined


def validate_metric(m: pd.DataFrame) -> list[str]:
    bad = []
    if m.duplicated(["school_id", "sy", "measure_id", "student_group"]).any():
        bad.append("grain violated (school_id, sy, measure_id, student_group)")
    if m["status"].isna().any():
        bad.append("rows without status")
    defined = set(pd.read_csv(MEASURES)["measure_id"]) if MEASURES.exists() else set()
    undefined = set(m["measure_id"]) - defined
    if undefined:
        bad.append(f"measures not defined in registry/measures.csv: {sorted(undefined)}")
    return bad
