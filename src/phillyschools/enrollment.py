"""Enrollment (October 1 counts) and catchment flows from the district's open data.

Tables (grain in one line each):
  enrollment         school x sy x grade x student group: student count with status
  catchment_flow     sy x catchment school (where students live) x enrolled school: count
  school_metric      school x sy x measure: per-school catchment and capacity figures
  school_placeholder one row per destination outside the district's school list
                     (cyber and out-of-city charters), so flows add up

Source quirks handled here:
  - three header schemes across 2014-15 to 2025-26; 2019-20 keys schools by SRC ID, not ULCS
  - grade codes 0/00/K and 1/01 mixed; an "All Grades" row per school (kept as grade ALL,
    never summed with the grade rows)
  - "." means suppressed; "Data is Private" means suppressed; "Data Not Available" as a
    catchment means the student's address could not be placed
  - one "CSV" (2016-17 retention details) is really an Excel file
"""

import re

import pandas as pd

from . import CORE, RAW, ROOT, spring_year
from .identity import mint_ids

ENROLL_DIR = RAW / "sdp_enrollment"
FLOW_DIR = RAW / "sdp_catchment_retention"
MEASURES = ROOT / "registry" / "measures.csv"

# canonical group name -> header names used in different years
GROUP_COLUMNS = {
    "all": ["allstudents", "studentenrollment"],
    "english_learner": ["ell", "elcount"],
    "not_english_learner": ["notell", "notelcount"],
    "iep": ["iep", "iepcount"],
    "not_iep": ["notiep", "notiepcount"],
    "female": ["female", "femalecount"],
    "male": ["male", "malecount"],
    "american_indian": ["indian", "americanindiancount"],
    "asian": ["asian", "asiancount"],
    "black": ["black", "blackafricanamericancount"],
    "hispanic": ["hispanic", "hispaniccount"],
    "multiracial": ["mult", "multiracecount"],
    "pacific_islander": ["hawaiian", "pacificislandercount"],
    "white": ["white", "whitecount"],
}
CEP_COLUMNS = ["ceppct", "cepeconomicallydisadvantagedrate"]
CYBER = re.compile(
    r"cyber|virtual|connections|distance|leadership|achievement house|insight|digital",
    re.IGNORECASE,
)


def placeholder_kind(name) -> str:
    n = str(name)
    if CYBER.search(n):
        return "cyber charter"
    if re.search(r"non.?public special", n, re.IGNORECASE):
        return "non-public special education"
    if re.search(r"charter|\bCS\b|collegium|ketterer", n, re.IGNORECASE):
        return "charter outside the district list"
    return "program outside the district list"


def read_table(path) -> pd.DataFrame:
    """Read by content, not extension (the district posted one xlsx named .csv)."""
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"PK":
        d = pd.read_excel(path, dtype=str)
    else:
        d = pd.read_csv(path, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    d.columns = [str(c).strip().lstrip("﻿") for c in d.columns]
    return d


def grade_code(value) -> str:
    v = str(value).strip()
    if v.lower().startswith("all"):
        return "ALL"
    if v.upper() in {"K", "0", "00"}:
        return "K"
    return f"{int(v):02d}" if v.isdigit() else v


def to_count(value) -> tuple[float | None, str]:
    v = str(value).strip() if value is not None else ""
    if v in {"", "nan", "None"}:
        return None, "not_reported"
    if v in {".", "s", "*"} or v.lower().startswith("data is private"):
        return None, "suppressed"
    try:
        return float(v), "reported"
    except ValueError:
        return None, "not_reported"


class SrcToUlcs:
    """SRC ID -> ULCS for a given year, from the identity crosswalk.

    Some years' district lists omit programs (alternative schools were left off the 2020-2025
    lists), so when the exact year is missing we fall back to the SRC ID's ULCS from other
    years, but only if that SRC ID has only ever meant one ULCS.
    """

    def __init__(self) -> None:
        xw = pd.read_parquet(CORE / "school_id_xwalk.parquet")
        ulcs = (
            xw[xw["id_type"] == "ulcs"]
            .drop_duplicates("school_id", keep="last")
            .set_index("school_id")["id_value"]
        )
        src = xw[xw["id_type"] == "src_id"]
        self.by_year: dict[tuple[str, int], str] = {}
        seen: dict[str, set] = {}
        for r in src.itertuples():
            code = ulcs.get(r.school_id)
            seen.setdefault(r.id_value, set()).add(code)
            last = r.valid_to_sy if pd.notna(r.valid_to_sy) else 2100
            for sy in range(int(r.valid_from_sy), int(last) + 1):
                self.by_year[(r.id_value, sy)] = code
        self.unique = {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}

    def get(self, key: tuple[str, int]) -> str | None:
        return self.by_year.get(key) or self.unique.get(key[0])


def _src_to_ulcs() -> SrcToUlcs:
    return SrcToUlcs()


def stage_enrollment() -> pd.DataFrame:
    frames = []
    src_map = _src_to_ulcs()
    for path in sorted(ENROLL_DIR.glob("*.csv")):
        sy = spring_year(path.name)
        d = read_table(path)
        d.columns = [c.lower() for c in d.columns]
        if "ulcscode" in d:
            ulcs = d["ulcscode"].str.strip()
        else:  # 2019-20: SRC school IDs
            ulcs = d["srcschoolid"].str.strip().map(lambda s, sy=sy: src_map.get((s, sy)))
        cep = next((c for c in CEP_COLUMNS if c in d), None)
        base = pd.DataFrame(
            {
                "sy": sy,
                "ulcs": ulcs,
                "source_name": d["schoolname"],
                "sector": d["sector"],
                "grade": d["gradelevel"].map(grade_code),
                "cep_rate": d[cep] if cep else None,
                "source_file": path.name,
            }
        )
        for group, names in GROUP_COLUMNS.items():
            col = next((n for n in names if n in d), None)
            if col is None:
                continue
            parsed = d[col].map(to_count)
            frames.append(
                base.assign(
                    student_group=group,
                    count=[p[0] for p in parsed],
                    status=[p[1] for p in parsed],
                )
            )
    frames += stage_enrollment_legacy(src_map)
    return pd.concat(frames, ignore_index=True)


LEGACY_SHEETS = {
    "Gender": {"male": "male", "female": "female"},
    "ELL": {"not ell": "not_english_learner", "ell": "english_learner"},
    "IEP": {"not iep": "not_iep", "iep": "iep"},
    "Ethnicity": {
        "american indian": "american_indian",
        "asian": "asian",
        "black": "black",
        "hispanic": "hispanic",
        "multi-race": "multiracial",
        "native hawaiian": "pacific_islander",
        "white": "white",
    },
    "Econ. Disadv.": {"economically": "economically_disadvantaged"},
}


def _legacy_group(label: str, mapping: dict[str, str]) -> str | None:
    text = re.sub(r"\s+", " ", str(label)).strip().lower()
    # Match the start of the label only: "Female" contains "male", and every race label
    # contains "(not Hispanic)".
    for key, group in mapping.items():
        if text.startswith(key):
            return group
    return None


def stage_enrollment_legacy(src_map: dict) -> list[pd.DataFrame]:
    """2009-10 to 2013-14 workbooks: one sheet per group, SRC school IDs, two header rows.

    Rows with 20 or fewer students are suppressed in the source ("s"); those rows carry
    status `suppressed` for every group. These files cover district schools only.
    """
    frames = []
    for path in sorted(ENROLL_DIR.glob("20*-20* Enrollment & Demographics.xlsx")):
        sy = spring_year(path.name)
        book = pd.ExcelFile(path)
        for sheet, mapping in LEGACY_SHEETS.items():
            if sheet not in book.sheet_names:
                continue
            d = book.parse(sheet, header=None, dtype=str)
            head = next(i for i, row in d.iterrows() if "School ID" in row.astype(str).tolist())
            cols = d.iloc[head].astype(str).tolist()
            labels = d.iloc[head - 1].astype(str).tolist()
            body = d.iloc[head + 1 :]
            body = body[body[cols.index("School ID")].notna()]
            src = body[cols.index("School ID")].str.strip().str.replace(r"\.0$", "", regex=True)
            base = pd.DataFrame(
                {
                    "sy": sy,
                    "ulcs": [src_map.get((v, sy)) for v in src],
                    "source_name": body[cols.index("School Name")].str.strip(),
                    "sector": "District",
                    "grade": body[cols.index("Grade")].map(grade_code),
                    "cep_rate": None,
                    "source_file": path.name,
                    "src_id": src,
                }
            )
            groups = [(j, _legacy_group(lab, mapping)) for j, lab in enumerate(labels)]
            if sheet == "Gender":
                groups.append((cols.index("Total Enrolled"), "all"))
            for j, group in groups:
                if group is None:
                    continue
                parsed = body[j].map(to_count)
                frames.append(
                    base.assign(
                        student_group=group,
                        count=[p[0] for p in parsed],
                        status=[p[1] for p in parsed],
                    )
                )
    return frames


def stage_flows() -> pd.DataFrame:
    frames = []
    for path in sorted(FLOW_DIR.glob("Catchment_Retention_Counts_by_School_*.csv")):
        d = read_table(path)
        parsed = d["Student Counts"].map(to_count)
        catch = d["Catchment School ID"].str.strip()
        frames.append(
            pd.DataFrame(
                {
                    "sy": d["School Year"].map(spring_year),
                    "catchment_ulcs": catch.where(~catch.str.lower().str.startswith("data")),
                    "catchment_status": catch.str.lower().map(
                        lambda v: (
                            "not_available"
                            if "not available" in v
                            else "private"
                            if "private" in v
                            else "reported"
                        )
                    ),
                    "enrolled_ulcs": d["Enrolled School ID"].str.strip(),
                    "enrolled_name": d["Enrolled School Name"].str.strip(),
                    "count": [p[0] for p in parsed],
                    "status": [p[1] for p in parsed],
                    "source_file": path.name,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


RETENTION_MEASURES = {
    "Building Capacity": "building_capacity",
    "Total Enrollment": "retention_total_enrollment",
    "Total Catchment Size": "catchment_size",
    "# Students Attending Neighborhood School": "students_attending_neighborhood_school",
    "Enrollment:Catchment Ratio": "enrollment_catchment_ratio",
    "% Staying in Catchment (of Catchment)": "pct_catchment_students_attending",
    "% From Within Neighborhood (of Enrollment)": "pct_enrollment_from_catchment",
}


def stage_retention_details() -> pd.DataFrame:
    frames = []
    for path in sorted(FLOW_DIR.glob("Catchment_Retention_Details_Schools_*.csv")):
        d = read_table(path)
        d = d.loc[:, ~d.columns.duplicated()]
        sy = spring_year(path.name)
        for col, measure in RETENTION_MEASURES.items():
            if col not in d:
                continue
            raw = d[col].astype(str).str.replace("%", "", regex=False).str.replace(",", "")
            parsed = raw.map(to_count)
            frames.append(
                pd.DataFrame(
                    {
                        "sy": sy,
                        "ulcs": d["Enrolled School ID"].str.strip(),
                        "name": d["Enrolled School Name"].str.strip(),
                        "measure_id": measure,
                        "value": [p[0] for p in parsed],
                        "status": [p[1] for p in parsed],
                        "source_file": path.name,
                    }
                )
            )
    return pd.concat(frames, ignore_index=True)


ENROLLMENT_CORRECTIONS = ROOT / "corrections" / "enrollment.csv"


def apply_enrollment_corrections(enrollment: pd.DataFrame) -> pd.DataFrame:
    """Withhold values the source publishes in error (status `invalid_in_source`)."""
    if not ENROLLMENT_CORRECTIONS.exists():
        return enrollment.assign(correction_id=None)
    out = enrollment.copy()
    out["correction_id"] = None
    for c in pd.read_csv(ENROLLMENT_CORRECTIONS, dtype=str).itertuples():
        hit = (out["sy"] == int(c.sy)) & (out["student_group"] == c.student_group)
        if not hit.any():
            raise ValueError(f"correction {c.correction_id} matches no enrollment rows")
        if c.action != "withhold":
            raise ValueError(f"unknown enrollment correction action {c.action}")
        out.loc[hit, "count"] = None
        out.loc[hit, "status"] = "invalid_in_source"
        out.loc[hit, "correction_id"] = c.correction_id
    return out


def build_enrollment(registry: pd.DataFrame) -> dict:
    enroll = stage_enrollment()
    flows = stage_flows()
    details = stage_retention_details()
    issues = []

    # Placeholders: any school code in these files that is not on a district school list
    # (cyber and out-of-city charters, non-public special education, short-lived programs),
    # so every student lands on a school_id and flows add up.
    # "Outside" means not on any district school list (core/school), not "not yet minted":
    # placeholders keep their registry IDs across rebuilds.
    known = set(pd.read_parquet(CORE / "school.parquet")["ulcs"])
    seen = pd.concat(
        [
            flows[["enrolled_ulcs", "enrolled_name", "sy"]].set_axis(
                ["ulcs", "name", "sy"], axis=1
            ),
            enroll[["ulcs", "source_name", "sy"]].set_axis(["ulcs", "name", "sy"], axis=1),
            details[["ulcs", "name", "sy"]],
        ]
    )
    seen = seen[seen["ulcs"].notna() & ~seen["ulcs"].str.lower().str.startswith("data")]
    outside = (
        seen[~seen["ulcs"].isin(known)]
        .sort_values("sy")
        .groupby("ulcs")
        .agg(name=("name", "last"), first_sy=("sy", "min"), last_sy=("sy", "max"))
        .reset_index()
    )
    registry = mint_ids(list(outside["ulcs"]), registry)
    ulcs_to_id = registry.set_index("ulcs")["school_id"]
    placeholder = outside.assign(
        school_id=outside["ulcs"].map(ulcs_to_id),
        # 3-digit codes are non-public special education placements (the retention files
        # give their sector as "Non Public Special Education")
        kind=[
            "non-public special education" if len(u) == 3 else placeholder_kind(n)
            for u, n in zip(outside["ulcs"], outside["name"], strict=True)
        ],
        status="derived",
    )[["school_id", "ulcs", "name", "kind", "first_sy", "last_sy", "status"]]

    enroll["school_id"] = enroll["ulcs"].map(ulcs_to_id)
    missing = enroll[enroll["school_id"].isna()].drop_duplicates(["sy", "source_name"])
    for r in missing.itertuples():
        issues.append(
            {
                "type": "enrollment school not in registry",
                "id": r.ulcs,
                "sy": r.sy,
                "detail": r.source_name,
            }
        )
    enrollment = enroll.dropna(subset=["school_id"])[
        ["school_id", "sy", "grade", "student_group", "count", "status", "sector", "source_file"]
    ].copy()
    enrollment = apply_enrollment_corrections(enrollment)
    enrollment["source_id"] = "sdp_enrollment:sy" + enrollment["sy"].astype(str)
    enrollment["snapshot_date"] = (enrollment["sy"] - 1).astype(str) + "-10-01"

    cep = enroll.dropna(subset=["school_id"]).drop_duplicates(["school_id", "sy"])
    cep_parsed = cep["cep_rate"].map(to_count)
    cep_rows = pd.DataFrame(
        {
            "school_id": cep["school_id"],
            "sy": cep["sy"],
            "measure_id": "cep_econ_disadvantaged_rate",
            "value": [p[0] for p in cep_parsed],
            "status": [p[1] for p in cep_parsed],
            "source_id": "sdp_enrollment:sy" + cep["sy"].astype(str),
        }
    )

    flows["catchment_school_id"] = flows["catchment_ulcs"].map(ulcs_to_id)
    flows["enrolled_school_id"] = flows["enrolled_ulcs"].map(ulcs_to_id)
    unknown_catch = flows[flows["catchment_ulcs"].notna() & flows["catchment_school_id"].isna()]
    for v in unknown_catch["catchment_ulcs"].unique():
        issues.append(
            {"type": "catchment school not in registry", "id": v, "sy": None, "detail": ""}
        )
    catchment_flow = flows[
        [
            "sy",
            "catchment_school_id",
            "catchment_status",
            "enrolled_school_id",
            "count",
            "status",
            "source_file",
        ]
    ].copy()
    catchment_flow["source_id"] = "sdp_catchment_retention:sy" + catchment_flow["sy"].astype(str)

    details["school_id"] = details["ulcs"].map(ulcs_to_id)
    for v in details[details["school_id"].isna()]["ulcs"].unique():
        issues.append(
            {"type": "retention school not in registry", "id": v, "sy": None, "detail": ""}
        )
    det = details.dropna(subset=["school_id"]).assign(
        source_id=lambda t: "sdp_catchment_retention:sy" + t["sy"].astype(str)
    )[["school_id", "sy", "measure_id", "value", "status", "source_id"]]
    school_metric = pd.concat([cep_rows, det], ignore_index=True)

    return {
        "enrollment": enrollment.reset_index(drop=True),
        "catchment_flow": catchment_flow.reset_index(drop=True),
        "school_metric": school_metric.reset_index(drop=True),
        "school_placeholder": placeholder,
        "enrollment_issues": pd.DataFrame(issues, columns=["type", "id", "sy", "detail"]),
        "_registry": registry,
    }


def validate_enrollment(t: dict) -> list[str]:
    bad = []
    e = t["enrollment"]
    if e.duplicated(["school_id", "sy", "grade", "student_group"]).any():
        bad.append("enrollment grain violated (school_id, sy, grade, student_group)")
    if e["status"].isna().any():
        bad.append("enrollment rows without status")
    f = t["catchment_flow"]
    if f["enrolled_school_id"].isna().any():
        bad.append("flow destination without a school_id (placeholder missing)")
    m = t["school_metric"]
    if m.duplicated(["school_id", "sy", "measure_id"]).any():
        bad.append("school_metric grain violated (school_id, sy, measure_id)")
    measures = set(pd.read_csv(MEASURES)["measure_id"]) if MEASURES.exists() else set()
    undefined = set(m["measure_id"]) - measures
    if undefined:
        bad.append(f"measures used but not defined in registry/measures.csv: {sorted(undefined)}")
    return bad


def write_enrollment(t: dict) -> None:
    from .identity import REGISTRY_FILE

    t["_registry"].to_csv(REGISTRY_FILE, index=False)
    for name in [
        "enrollment",
        "catchment_flow",
        "school_metric",
        "school_placeholder",
        "enrollment_issues",
    ]:
        t[name].to_parquet(CORE / f"{name}.parquet", index=False)
        t[name].to_csv(CORE / f"{name}.csv", index=False)
    if MEASURES.exists():
        pd.read_csv(MEASURES).to_csv(CORE / "measure.csv", index=False)
        pd.read_csv(MEASURES).to_parquet(CORE / "measure.parquet", index=False)
