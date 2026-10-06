"""Wide tables for people, dashboards, and agents, plus the generated data dictionary.

marts/school_year     one row per school and school year (sy): who the school was that year,
                      and every school-level measure with an `all students` value that year
marts/school_profile  one row per school: identity, and for each measure the most recent
                      reported value and the school year (`<measure>_sy`) it is from

Only `reported` values are filled in; suppressed, waived, and other statuses are blank here, and
the long table core/school_metric keeps them with their status. Years differ by measure (a
facility score from 2022 sits beside attendance from 2025), so always read the `_sy` column
before comparing schools. These are facts, not rankings: there is no composite score.

Every column is described in schema/*.json and in the Parquet file metadata, generated from
registry/measures.csv (one source of truth), and docs/DATA_DICTIONARY.md lists them all.
"""

import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import CORE, ROOT
from .metrics import MEASURES

MARTS = ROOT / "marts"
SCHEMA = ROOT / "schema"
DOCS = ROOT / "docs"

COLUMN_DOCS = {
    "school_id": "Permanent minted school ID (sch_NNNNN); never reused. Outside codes are in school_id_xwalk.",
    "sy": "Spring year of the school year: 2025 means 2024-25 (fiscal year 2025, July to June).",
    "current_name": "Name in the most recent year the school appears in the district's lists.",
    "name": "School name in this school year.",
    "ulcs": "District Universal Location Code (4 digits); the most recent code, see school_id_xwalk for history.",
    "governance": "District, Charter, Contracted, or other, as the district's school list gives it.",
    "level": "Elementary, Middle, High, or a combination, as the district's school list gives it.",
    "admission_type": "Catchment, Citywide, Special Admission, or similar, as the district's school list gives it.",
    "category": "The district's school reporting category.",
    "council_district": "City Council district of the school's location.",
    "first_sy_in_data": "First school year the school appears in any district list.",
    "last_sy_in_data": "Last school year the school appears in any district list (2027 means the 2026-27 list).",
    "year_opened": "Year the school opened, as the district reports it.",
    "year_closed_sy": "School year the school closed, as the district reports it; blank if still open.",
    "record_kind": "school for schools on the district's lists; otherwise a placeholder for a program that appears only in state data (for example 'program outside the district list').",
    "listed_in_latest_year": "True if the school is on the most recent district school list.",
    "value": "The measured value; read it with the measure's unit and denominator.",
    "status": "reported, suppressed, not_applicable, not_reported, carried_forward, waived, blended, not_separately_measurable, invalid_in_source, derived, or partial. A non-reported status is not a zero.",
    "source_id": "Points to the source table: publisher, URL, file, download date, hash, license.",
    "measure_id": "Measure code; defined in the measure table.",
    "student_group": "all, a race or ethnicity group, gender, grade, disability, English learner, or economic status.",
}
TABLES = {
    "school": (
        "one row per school_id",
        "Every school that appears in a district list, 2002 to 2027.",
    ),
    "school_year_attr": ("school_id x sy", "Name, governance, level, and admission type by year."),
    "school_id_xwalk": (
        "school_id x outside code x valid years",
        "ULCS, AUN, NCES, and other codes with the years each applies.",
    ),
    "school_event": ("one row per event", "Name and level changes, openings, and closures."),
    "school_parcel": (
        "school_id x valid years",
        "The City parcel (OPA account) the school occupies.",
    ),
    "school_metric": (
        "school_id x sy x measure_id x student_group",
        "Every school-level measure, long, with status and source.",
    ),
    "measure": (
        "one row per measure_id",
        "The measure dictionary: definition, unit, denominator, breaks, usage notes.",
    ),
    "enrollment": (
        "school_id x sy x grade x student_group",
        "Enrolled students from the October 1 count.",
    ),
    "assessment_result": (
        "school_id x sy x subject x grade x student_group",
        "State test results by performance level.",
    ),
    "catchment": ("school_id x sy", "Catchment boundary for the school year."),
    "catchment_flow": (
        "school_id x sy x origin geography",
        "Students by the neighborhood unit they live in.",
    ),
    "assignment_zone": ("zone x sy", "Assignment zones."),
    "geo_unit": ("one row per geographic unit", "Census tracts and other units used for joins."),
    "geo_xwalk": ("geographic unit x neighborhood", "Population-weighted crosswalk between units."),
    "area_context": (
        "geographic unit x period",
        "American Community Survey context with margins of error.",
    ),
    "school_incident": (
        "school_id x sy x incident type",
        "Serious incidents as the district publishes them.",
    ),
    "school_state_attr": (
        "school_id x sy",
        "State designations (Title I, ESSA, career and technical programs).",
    ),
    "school_lead_paint": (
        "one row per lead-safe file",
        "Lead paint assessments (XRF), summarized per file.",
    ),
    "school_water_lead": (
        "one row per outlet sample",
        "Lead in drinking water by outlet, with follow-up retests.",
    ),
    "building_asbestos": (
        "one row per building and AHERA report",
        "Asbestos management totals from the room-by-room logs.",
    ),
    "building_asbestos_item": (
        "one row per confirmed or assumed asbestos material",
        "Materials, spaces, amounts, and damage from each building's latest report.",
    ),
    "school_placeholder": (
        "one row per program",
        "Programs that appear only in state data (cyber charters, non-public special education, programs outside the district list), with their own school_id.",
    ),
    "building": (
        "one row per building_id",
        "One physical building: name, kind, address, year built, and the City parcel (OPA account) when known.",
    ),
    "building_xwalk": (
        "building_id x outside key",
        "Asbestos code, assessment part code, and lead and water folder keys, with how each link was made.",
    ),
    "school_building": (
        "school_id x building_id x years",
        "Which schools were in which buildings, from the street address in each year's district list, plus annex links.",
    ),
    "facility_condition": (
        "one row per assessed site",
        "Facility condition index, costs, and scores (2020 cycle).",
    ),
    "facility_condition_part": (
        "site x building or grounds",
        "Buildings and grounds within a site.",
    ),
    "facility_condition_system": (
        "site x building system",
        "Condition index and costs by major system.",
    ),
    "source": ("one row per downloaded source file", "Publisher, URL, file, hash, and license."),
}


def refresh_measure_table() -> pd.DataFrame:
    m = pd.read_csv(MEASURES)
    m.to_csv(CORE / "measure.csv", index=False)
    m.to_parquet(CORE / "measure.parquet", index=False)
    return m


def _wide(metric: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    ok = metric[(metric["student_group"] == "all") & (metric["status"] == "reported")]
    ok = ok.dropna(subset=["value"])
    return ok.pivot_table(index=keys, columns="measure_id", values="value", aggfunc="first")


def _enrollment_measure() -> pd.DataFrame:
    e = pd.read_parquet(CORE / "enrollment.parquet")
    e = e[(e["grade"] == "ALL") & (e["student_group"] == "all") & (e["status"] == "reported")]
    e = e.dropna(subset=["count"]).drop_duplicates(["school_id", "sy"])
    return e[["school_id", "sy", "count"]].rename(columns={"count": "enrollment_count"})


def _all_schools() -> pd.DataFrame:
    """Listed schools plus placeholder records (programs that appear only in state data)."""
    school = pd.read_parquet(CORE / "school.parquet").assign(record_kind="school")
    ph = pd.read_parquet(CORE / "school_placeholder.parquet")
    ph = ph.rename(
        columns={
            "name": "current_name",
            "first_sy": "first_sy_in_data",
            "last_sy": "last_sy_in_data",
        }
    ).assign(record_kind=ph["kind"], listed_in_latest_year=False)
    return pd.concat(
        [school, ph[[c for c in ph.columns if c in school.columns]]], ignore_index=True
    )


def build_school_year() -> pd.DataFrame:
    metric = pd.read_parquet(CORE / "school_metric.parquet")
    wide = _wide(metric, ["school_id", "sy"]).reset_index()
    wide = wide.merge(_enrollment_measure(), on=["school_id", "sy"], how="outer")
    attrs = pd.read_parquet(CORE / "school_year_attr.parquet")[
        ["school_id", "sy", "name", "governance", "level", "admission_type", "council_district"]
    ]
    out = attrs.merge(wide, on=["school_id", "sy"], how="outer")
    school = _all_schools()[["school_id", "current_name"]]
    out = out.merge(school, on="school_id", how="left")
    out["name"] = out["name"].fillna(out["current_name"])
    out = out.drop(columns="current_name")
    first = ["school_id", "sy", "name", "governance", "level", "admission_type", "council_district"]
    measures = sorted(c for c in out.columns if c not in first)
    return out[first + measures].sort_values(["school_id", "sy"]).reset_index(drop=True)


def build_school_profile(school_year: pd.DataFrame) -> pd.DataFrame:
    school = _all_schools()
    attrs = (
        pd.read_parquet(CORE / "school_year_attr.parquet")
        .sort_values("sy")
        .groupby("school_id")
        .last()[["governance", "level", "admission_type", "council_district"]]
        .reset_index()
    )
    out = school.merge(attrs, on="school_id", how="left")
    measures = [
        c
        for c in school_year.columns
        if c
        not in {
            "school_id",
            "sy",
            "name",
            "governance",
            "level",
            "admission_type",
            "council_district",
        }
    ]
    latest = {}
    for m in measures:
        d = school_year.dropna(subset=[m]).sort_values("sy").groupby("school_id").last()
        latest[m] = d[m]
        latest[f"{m}_sy"] = d["sy"]
    wide = pd.DataFrame(latest).reset_index()
    out = out.merge(wide, on="school_id", how="left")
    for m in measures:
        out[f"{m}_sy"] = out[f"{m}_sy"].astype("Int64")
    ordered = [
        c
        for c in out.columns
        if not c.endswith("_sy") or c in {"first_sy_in_data", "last_sy_in_data"}
    ]
    ids = [c for c in ordered if c not in measures]
    cols = ids + [x for m in sorted(measures) for x in (m, f"{m}_sy")]
    return out[cols].sort_values("school_id").reset_index(drop=True)


def column_docs(measures: pd.DataFrame) -> dict[str, dict]:
    docs = {c: {"description": d} for c, d in COLUMN_DOCS.items()}
    for r in measures.itertuples():
        docs[r.measure_id] = {
            "description": f"{r.name}. {r.definition}.",
            "unit": r.unit,
            "denominator": r.denominator,
            "usage_notes": r.usage_notes if isinstance(r.usage_notes, str) else "",
            "breaks": r.breaks if isinstance(r.breaks, str) else "",
            "source_key": r.source_key,
        }
        docs[f"{r.measure_id}_sy"] = {
            "description": f"School year (sy) the {r.measure_id} value is from."
        }
    return docs


def write_documented(df: pd.DataFrame, path, docs: dict[str, dict]) -> None:
    """Parquet with each column's description in the file's own metadata, plus a CSV copy."""
    table = pa.Table.from_pandas(df, preserve_index=False)
    fields = []
    for f in table.schema:
        meta = {k.encode(): str(v).encode() for k, v in docs.get(f.name, {}).items() if v}
        fields.append(f.with_metadata(meta))
    schema = pa.schema(fields, metadata={b"generated_by": b"philly-school-data-explorer"})
    pq.write_table(table.cast(schema), path)
    df.to_csv(path.with_suffix(".csv"), index=False)


def write_schema_json(name: str, df: pd.DataFrame, grain: str, docs: dict[str, dict]) -> None:
    SCHEMA.mkdir(exist_ok=True)
    cols = [{"name": c, "type": str(df[c].dtype), **docs.get(c, {})} for c in df.columns]
    body = {"table": name, "grain": grain, "rows": len(df), "columns": cols}
    (SCHEMA / f"{name}.json").write_text(json.dumps(body, indent=1, default=str) + "\n")


def build_marts() -> dict:
    MARTS.mkdir(exist_ok=True)
    measures = refresh_measure_table()
    docs = column_docs(measures)
    sy = build_school_year()
    profile = build_school_profile(sy)
    write_documented(sy, MARTS / "school_year.parquet", docs)
    write_documented(profile, MARTS / "school_profile.parquet", docs)
    write_schema_json("school_year", sy, "school_id x sy", docs)
    write_schema_json("school_profile", profile, "one row per school_id", docs)
    (SCHEMA / "measures.json").write_text(
        json.dumps(measures.fillna("").to_dict("records"), indent=1) + "\n"
    )
    write_dictionary(measures)
    return {"school_year": sy, "school_profile": profile, "measures": measures}


def _md(s) -> str:
    return "" if pd.isna(s) else str(s).replace("|", "/").replace("\n", " ")


def write_dictionary(measures: pd.DataFrame) -> None:
    """docs/DATA_DICTIONARY.md, generated from registry/measures.csv and the core tables."""
    out = [
        "# Data dictionary",
        "",
        (
            "Generated by `uv run psd build-marts` from `registry/measures.csv` and the tables "
            "in `core/`. Do not edit by hand: change the registry and rebuild."
        ),
        "",
        "## Tables",
        "",
        "| Table | Grain | What it holds | Rows | Columns |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, (grain, what) in TABLES.items():
        p = CORE / f"{name}.parquet"
        if not p.exists():
            continue
        cols = pq.read_schema(p).names
        rows = pq.ParquetFile(p).metadata.num_rows
        out.append(
            f"| `{name}` | {grain} | {what} | {rows:,} | {', '.join(f'`{c}`' for c in cols)} |"
        )
    out += [
        "| `marts/school_year` | school_id x sy | One row per school and school year, wide: name, governance, level, and every measure with an `all students` value | see schema | see `schema/school_year.json` |",
        "| `marts/building` | one row per building_id | One row per building with its latest asbestos, lead-paint, water, and facility-condition results and the schools there now | see schema | see `schema/building.json` |",
        "| `marts/school_profile` | one row per school_id | Most recent reported value of each measure and its year (`<measure>_sy`) | see schema | see `schema/school_profile.json` |",
        "",
        "## Reading a value",
        "",
        "- `sy` is the spring year: 2025 is the 2024-25 school year.",
        "- Look at `status` before `value`: only `reported` is a measurement. Suppressed, waived, and not-applicable values are not zeros.",
        "- Read the measure's `denominator` and `usage_notes`; some measures (facility, lead, asbestos, water) are point-in-time records from one inspection, not yearly series.",
        "- Groups under 20 students are suppressed at the source; never rebuild them by subtraction.",
        "- These are facts for fair comparison, not rankings. No composite score exists.",
        (
            "- The wide marts carry each measure's `all students` value only. Measures by student "
            "group, and measures kept in their own tables (enrollment by grade, test results by "
            "level, catchment flows, area context), are read from the table named in `Lives in`."
        ),
        "",
        "## Measures",
        "",
        f"{len(measures)} measures. Student groups: `all` unless a measure's notes list others.",
        "",
    ]
    for source, group in measures.groupby("source_key", sort=True):
        out += [
            f"### {source}",
            "",
            "| Measure | Name | Definition | Unit | Denominator | Lives in | First sy | Breaks and notes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in group.itertuples():
            notes = " ".join(x for x in [_md(r.breaks), _md(r.usage_notes)] if x)
            out.append(
                f"| `{r.measure_id}` | {_md(r.name)} | {_md(r.definition)} | {_md(r.unit)} | {_md(r.denominator)} | `{_md(r.table)}` | {_md(r.first_sy)} | {notes} |"
            )
        out.append("")
    (DOCS / "DATA_DICTIONARY.md").write_text("\n".join(out))
