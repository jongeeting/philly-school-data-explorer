"""Identity layer: minted school IDs, dated outside-code crosswalk, per-year attributes, events.

Design rules (see CONTRIBUTING.md): the minted `school_id` is the only primary key; district
and state codes live in `school_id_xwalk` with valid-from/valid-to years. A "school" is a
program with its own district code (ULCS), so one building can hold several, and a school can
change building, name, or governance without changing its `school_id`.

Input is the staged SDP master-school-list table (one row per listed school per school year).
"""

import re
from datetime import UTC, datetime

import pandas as pd

from . import CORE, REGISTRY, ROOT

REGISTRY_FILE = REGISTRY / "school_id_registry.csv"
STAGED_COLUMNS = [
    "year",
    "aun",
    "schl",
    "ulcs",
    "src_id",
    "nces",
    "name",
    "governance",
    "category",
    "level",
    "admission",
    "council_district",
    "gps",
    "school_key",
]
PLACEHOLDER_STATE_NUMBERS = {"0", "9999"}  # state codes shared by many alternative programs
ID_TYPES = ["ulcs", "state_key", "src_id", "nces"]


# --- minted IDs ---------------------------------------------------------------------------


def load_registry() -> pd.DataFrame:
    if REGISTRY_FILE.exists():
        return pd.read_csv(REGISTRY_FILE, dtype=str)
    return pd.DataFrame(columns=["school_id", "ulcs", "minted_on"])


def mint_ids(
    ulcs_codes: list[str], registry: pd.DataFrame, today: str | None = None
) -> pd.DataFrame:
    """Append-only: existing ULCS keep their ID forever; new codes get the next number."""
    today = today or datetime.now(UTC).date().isoformat()
    known = set(registry["ulcs"])
    new = sorted((c for c in set(ulcs_codes) if c not in known), key=lambda c: (len(c), c))
    if not new:
        return registry
    top = max((int(s.split("_")[1]) for s in registry["school_id"]), default=0)
    added = pd.DataFrame(
        {
            "school_id": [f"sch_{top + i:05d}" for i, _ in enumerate(new, start=1)],
            "ulcs": new,
            "minted_on": today,
        }
    )
    return pd.concat([registry, added], ignore_index=True)


# --- helpers ------------------------------------------------------------------------------


def _runs(years: list[int]) -> list[tuple[int, int]]:
    """Collapse years into (first, last) runs of consecutive years."""
    out: list[tuple[int, int]] = []
    for y in sorted(set(years)):
        if out and y == out[-1][1] + 1:
            out[-1] = (out[-1][0], y)
        else:
            out.append((y, y))
    return out


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).casefold())


def _latlon(gps) -> tuple[float | None, float | None]:
    try:
        lat, lon = (float(p) for p in str(gps).split(","))
        return lat, lon
    except ValueError:
        return None, None


LONGITUDINAL_SOURCE_ID = "sdp_longitudinal_school_list"
OPTIONAL_COLUMNS = ["nces_source", "year_opened", "year_closed_sy"]


def source_id_for(sy: int) -> str:
    """Lists before 2017-18 come from the single Longitudinal School List file."""
    return LONGITUDINAL_SOURCE_ID if sy <= 2017 else f"sdp_master_school_list:sy{sy}"


# --- build --------------------------------------------------------------------------------


LINEAGE_COLUMNS = [
    "predecessor_school_id",
    "successor_school_id",
    "sy",
    "lineage_type",
    "evidence",
    "source_id",
]


def read_lineage_corrections() -> pd.DataFrame:
    """Hand-set predecessor and successor links, each with its evidence; never inferred."""
    path = ROOT / "corrections" / "school_lineage.csv"
    if not path.exists():
        return pd.DataFrame(columns=LINEAGE_COLUMNS)
    df = pd.read_csv(path, dtype={"sy": "Int64"})
    return df[LINEAGE_COLUMNS]


def build_identity(staged: pd.DataFrame, registry: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Returns the identity tables plus `issues` (data-quality notes, not a core table)."""
    d = staged.reindex(columns=STAGED_COLUMNS + OPTIONAL_COLUMNS).copy()
    d["year"] = d["year"].astype(int)
    issues: list[dict] = []

    dup = d.duplicated(["ulcs", "year"], keep="first")
    for _, r in d[dup].iterrows():
        issues.append(
            {
                "type": "duplicate ulcs-year, first row kept",
                "id": r["ulcs"],
                "sy": r["year"],
                "detail": r["name"],
            }
        )
    d = d[~dup]

    registry = mint_ids(list(d["ulcs"].unique()), registry)
    d = d.merge(registry[["school_id", "ulcs"]], on="ulcs", how="left")
    max_sy = int(d["year"].max())

    # school
    last = d.sort_values("year").groupby("school_id").last()
    span = d.groupby("school_id")["year"].agg(first_sy_in_data="min", last_sy_in_data="max")
    reported = (
        d.sort_values("year")
        .groupby("school_id")[["year_opened", "year_closed_sy"]]
        .agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else pd.NA)
        .astype("Int64")
    )
    school = (
        last[["ulcs", "name"]]
        .rename(columns={"name": "current_name"})
        .join(span)
        .join(reported)
        .assign(listed_in_latest_year=lambda t: t["last_sy_in_data"] == max_sy)
        .reset_index()
    )

    # school_year_attr
    coords = d["gps"].map(_latlon)
    attr = (
        pd.DataFrame(
            {
                "school_id": d["school_id"],
                "sy": d["year"],
                "name": d["name"],
                "governance": d["governance"],
                "category": d["category"],
                "level": d["level"],
                "admission_type": d["admission"],
                "council_district": pd.to_numeric(d["council_district"], errors="coerce").astype(
                    "Int64"
                ),
                "lat": coords.map(lambda t: t[0]),
                "lon": coords.map(lambda t: t[1]),
                "status": "reported",
                "source_id": d["year"].map(source_id_for),
            }
        )
        .sort_values(["school_id", "sy"])
        .reset_index(drop=True)
    )

    # school_id_xwalk: one row per school x code x run of consecutive years
    d["state_key"] = d["school_key"]
    n_schools_per_value: dict[str, pd.Series] = {}
    for t in ID_TYPES:
        n_schools_per_value[t] = d.dropna(subset=[t]).groupby(t)["school_id"].nunique()
    xrows = []
    for t in ID_TYPES:
        sub = d.dropna(subset=[t])
        for (sid, value), g in sub.groupby(["school_id", t]):
            shared = n_schools_per_value[t][value] > 1
            if t == "state_key" and str(value).split("-")[-1] in PLACEHOLDER_STATE_NUMBERS:
                shared = True
            for first, last_y in _runs(g["year"].tolist()):
                xrows.append(
                    {
                        "school_id": sid,
                        "id_type": t,
                        "id_value": value,
                        "valid_from_sy": first,
                        "valid_to_sy": None if last_y == max_sy else last_y,
                        "shared_across_schools": bool(shared),
                        "evidence": (
                            "includes_bridged_years"
                            if t == "nces" and (g["nces_source"] == "bridged").any()
                            else "reported"
                        ),
                        "source_id": source_id_for(last_y),
                    }
                )
    xwalk = (
        pd.DataFrame(xrows)
        .sort_values(["school_id", "id_type", "valid_from_sy"])
        .reset_index(drop=True)
    )
    xwalk["valid_to_sy"] = xwalk["valid_to_sy"].astype("Int64")

    # events derived from changes between listed years (not the same as real-world dates)
    events = []
    for sid, g in attr.groupby("school_id"):
        g = g.sort_values("sy")
        for prev, cur in zip(g.itertuples(), g.iloc[1:].itertuples()):
            if cur.sy != prev.sy + 1:
                issues.append(
                    {
                        "type": "listing gap (list coverage, not necessarily closure)",
                        "id": sid,
                        "sy": cur.sy,
                        "detail": f"{cur.category}: not listed {prev.sy + 1} to {cur.sy - 1}",
                    }
                )
                continue
            if cur.governance != prev.governance:
                events.append(
                    (sid, "governance_change", cur.sy, f"{prev.governance} -> {cur.governance}")
                )
            if _norm(cur.name) != _norm(prev.name):
                events.append((sid, "name_change", cur.sy, f"{prev.name} -> {cur.name}"))
            if cur.level != prev.level:
                events.append((sid, "level_change", cur.sy, f"{prev.level} -> {cur.level}"))
    # Event `sy` is the first school year the change is in effect. Closures the district
    # reports (Year Closed) are status=reported; absence from a list alone stays derived.
    for r in school.itertuples():
        if pd.notna(r.year_closed_sy):
            y = int(r.year_closed_sy)
            events.append((r.school_id, "closed", y + 1, f"closed at end of SY {y - 1}-{y}"))
        elif not r.listed_in_latest_year:
            events.append(
                (
                    r.school_id,
                    "no_longer_listed",
                    int(r.last_sy_in_data) + 1,
                    f"last listed {r.last_sy_in_data}",
                )
            )
    school_event = pd.DataFrame(events, columns=["school_id", "event_type", "sy", "detail"])
    school_event = school_event.sort_values(["school_id", "sy", "event_type"]).reset_index(
        drop=True
    )
    school_event.insert(0, "event_id", [f"evt_{i:05d}" for i in range(1, len(school_event) + 1)])
    school_event["status"] = school_event["event_type"].map(
        lambda k: "reported" if k == "closed" else "derived"
    )
    school_event["source_id"] = [
        LONGITUDINAL_SOURCE_ID if k == "closed" else source_id_for(min(y, max_sy))
        for k, y in zip(school_event["event_type"], school_event["sy"], strict=True)
    ]

    # data-quality notes that deserve a person's eyes
    for t in ["ulcs", "src_id", "nces"]:
        multi = d.dropna(subset=[t]).groupby("school_id")[t].nunique()
        for sid in multi[multi > 1].index:
            vals = sorted(d.loc[(d["school_id"] == sid) & d[t].notna(), t].unique())
            issues.append(
                {
                    "type": f"school has several {t} values",
                    "id": sid,
                    "sy": None,
                    "detail": "|".join(vals),
                }
            )
    for t in ["src_id", "nces"]:
        multi = n_schools_per_value[t]
        for v in multi[multi > 1].index:
            issues.append(
                {
                    "type": f"{t} shared by several schools",
                    "id": v,
                    "sy": None,
                    "detail": "|".join(sorted(d.loc[d[t] == v, "school_id"].unique())),
                }
            )

    school_lineage = read_lineage_corrections()
    correction = pd.DataFrame(
        columns=[
            "correction_id",
            "table",
            "key",
            "field",
            "old_value",
            "new_value",
            "reason",
            "source_id",
            "corrected_on",
            "corrected_by",
        ]
    )

    return {
        "school": school,
        "school_year_attr": attr,
        "school_id_xwalk": xwalk,
        "school_event": school_event,
        "school_lineage": school_lineage,
        "correction": correction,
        "issues": pd.DataFrame(issues, columns=["type", "id", "sy", "detail"]),
        "_registry": registry,
    }


# --- validation ---------------------------------------------------------------------------


def validate(t: dict[str, pd.DataFrame]) -> list[str]:
    """Hard rules; an empty list means the identity tables are consistent."""
    bad = []
    school, attr, xw = t["school"], t["school_year_attr"], t["school_id_xwalk"]
    if not school["school_id"].is_unique:
        bad.append("school_id not unique in school")
    if not school["ulcs"].is_unique:
        bad.append("ulcs not unique in school")
    if attr.duplicated(["school_id", "sy"]).any():
        bad.append("school_year_attr grain violated (school_id, sy)")
    if set(attr["school_id"]) != set(school["school_id"]):
        bad.append("school and school_year_attr disagree on school_ids")
    if (xw["valid_to_sy"].notna() & (xw["valid_to_sy"] < xw["valid_from_sy"])).any():
        bad.append("xwalk valid_to_sy before valid_from_sy")
    ulcs_rows = xw[xw["id_type"] == "ulcs"]
    if ulcs_rows.groupby("id_value")["school_id"].nunique().gt(1).any():
        bad.append("a ULCS code maps to more than one school_id")
    reg = t["_registry"]
    if not reg["school_id"].is_unique or not reg["ulcs"].is_unique:
        bad.append("registry has duplicate IDs or codes")
    if not set(school["ulcs"]) <= set(reg["ulcs"]):
        bad.append("registry missing a ULCS")
    if attr["status"].isna().any() or attr["source_id"].isna().any():
        bad.append("status or source_id missing in school_year_attr")
    return bad


def write_core(t: dict[str, pd.DataFrame]) -> None:
    CORE.mkdir(exist_ok=True)
    REGISTRY.mkdir(exist_ok=True)
    t["_registry"].to_csv(REGISTRY_FILE, index=False)
    for name, df in t.items():
        if name.startswith("_"):
            continue
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
