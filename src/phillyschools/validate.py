"""Validation: hard checks that fail the build, and reconciliations against independent figures.

`uv run psd validate` writes docs/VALIDATION.md and exits nonzero if any hard check fails, so
it can run on every refresh. Reconciliations compare two sources that should agree (the
district's counts against the state's, federal discipline against the district's) and report
the correlation and ratio; a reconciliation fails only below a stated floor.
"""

from datetime import UTC, datetime

import pandas as pd

from . import CORE, ROOT
from .marts import DOCS, MARTS

STATUSES = {
    "reported",
    "suppressed",
    "not_applicable",
    "not_reported",
    "carried_forward",
    "waived",
    "blended",
    "not_separately_measurable",
    "invalid_in_source",
    "derived",
    "partial",
}
PERCENT_UNITS = {"percent"}
# percent measures that can exceed 100 by design (system condition indexes, ratios)
PERCENT_EXEMPT = {"fca_fci_pct"}


def _check(name: str, ok: bool, detail: str, hard: bool = True) -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail, "hard": hard}


def hard_checks() -> list[dict]:
    m = pd.read_parquet(CORE / "school_metric.parquet")
    reg = pd.read_csv(ROOT / "registry" / "school_id_registry.csv", dtype=str)
    measures = pd.read_csv(ROOT / "registry" / "measures.csv")
    out = []
    dups = m.duplicated(["school_id", "sy", "measure_id", "student_group"]).sum()
    out.append(_check("school_metric grain is unique", dups == 0, f"{dups} duplicate keys"))
    orphans = set(m["school_id"]) - set(reg["school_id"])
    out.append(
        _check("every metric school_id is in the registry", not orphans, f"{len(orphans)} unknown")
    )
    undefined = set(m["measure_id"]) - set(measures["measure_id"])
    out.append(
        _check("every measure is in the dictionary", not undefined, f"{sorted(undefined)[:5]}")
    )
    bad_status = set(m["status"].dropna()) - STATUSES
    out.append(
        _check(
            "statuses are from the allowed set",
            not bad_status and m["status"].notna().all(),
            f"{sorted(bad_status)}",
        )
    )
    reported = m[m["status"] == "reported"]
    out.append(
        _check(
            "reported rows have a value",
            reported["value"].notna().all(),
            f"{reported['value'].isna().sum()} blank",
        )
    )
    out.append(
        _check(
            "every row has a source_id",
            m["source_id"].notna().all(),
            f"{m['source_id'].isna().sum()} blank",
        )
    )
    out.append(
        _check(
            "sy is within 2000 to 2027",
            m["sy"].between(2000, 2027).all(),
            f"range {m['sy'].min()} to {m['sy'].max()}",
        )
    )
    units = measures.set_index("measure_id")["unit"]
    r = reported.assign(unit=reported["measure_id"].map(units))
    neg = r[
        (r["unit"].isin(["students", "outlets", "items", "components", "incidents"]))
        & (r["value"] < 0)
    ]
    out.append(_check("count measures are not negative", neg.empty, f"{len(neg)} negative"))
    pct = r[r["unit"].isin(PERCENT_UNITS) & ~r["measure_id"].isin(PERCENT_EXEMPT)]
    over = pct[(pct["value"] < 0) | (pct["value"] > 100.0001)]
    out.append(
        _check(
            "percent measures are between 0 and 100",
            over.empty,
            f"{len(over)} outside; {sorted(over['measure_id'].unique())[:4]}",
        )
    )
    marts = pd.read_parquet(MARTS / "school_year.parquet")
    out.append(
        _check(
            "school_year is unique by school and sy",
            not marts.duplicated(["school_id", "sy"]).any(),
            f"{len(marts)} rows",
        )
    )
    prof = pd.read_parquet(MARTS / "school_profile.parquet")
    out.append(
        _check(
            "school_profile has one row per school",
            prof["school_id"].is_unique,
            f"{len(prof)} rows",
        )
    )
    out.append(
        _check(
            "marts cover every metric school",
            not (set(m["school_id"]) - set(prof["school_id"])),
            "",
        )
    )
    fcp = pd.read_parquet(CORE / "facility_condition_part.parquet")
    fc = pd.read_parquet(CORE / "facility_condition.parquet")
    sums = (
        fcp.groupby("file")[["repair_cost", "replacement_value"]]
        .sum()
        .join(fc.set_index("file")[["repair_cost", "replacement_value"]], rsuffix="_site")
    )
    off = ((sums["repair_cost"] - sums["repair_cost_site"]).abs() > 1000).sum()
    out.append(
        _check(
            "facility parts add up to site totals",
            off == 0,
            f"{off} sites differ by more than $1,000",
        )
    )
    ok_levels = pd.read_parquet(CORE / "enrollment.parquet")
    gradesum = ok_levels[
        (ok_levels["student_group"] == "all")
        & (ok_levels["status"] == "reported")
        & ok_levels["count"].notna()
    ]
    tot = gradesum[gradesum["grade"] == "ALL"].set_index(["school_id", "sy"])["count"]
    by_grade = gradesum[gradesum["grade"] != "ALL"].groupby(["school_id", "sy"])["count"].sum()
    j = pd.concat([tot, by_grade], axis=1, keys=["all", "grades"]).dropna()
    ratio = j["grades"].sum() / j["all"].sum()
    out.append(
        _check(
            "enrollment grades add to the all-grades row (within 1%)",
            abs(ratio - 1) < 0.01,
            f"grades/all = {ratio:.4f} over {len(j)} school-years",
        )
    )
    return out


def _corr(a: pd.Series, b: pd.Series):
    j = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    return len(j), j["a"].corr(j["b"]), j["a"].sum() / j["b"].sum()


def reconciliations() -> list[dict]:
    sm = pd.read_parquet(CORE / "school_metric.parquet")
    rep = sm[(sm["status"] == "reported") & (sm["student_group"] == "all")]
    wide = rep.pivot_table(
        index=["school_id", "sy"], columns="measure_id", values="value", aggfunc="first"
    )
    enr = pd.read_parquet(CORE / "enrollment.parquet")
    enr = enr[
        (enr["grade"] == "ALL") & (enr["student_group"] == "all") & (enr["status"] == "reported")
    ]
    enr = enr.drop_duplicates(["school_id", "sy"]).set_index(["school_id", "sy"])["count"]
    out = []
    n, r, ratio = _corr(wide["state_enrollment"], enr)
    out.append(
        {
            "check": "state enrollment vs district October 1 count",
            "n": n,
            "r": r,
            "ratio": ratio,
            "floor": 0.98,
            "note": "two independent counts of the same students",
        }
    )
    sdp_any = wide["sdp_oss_students"] - wide["sdp_n_oss_0"]
    n, r, ratio = _corr(wide["crdc_n_oss"], sdp_any)
    out.append(
        {
            "check": "federal vs district students with an out-of-school suspension",
            "n": n,
            "r": r,
            "ratio": ratio,
            "floor": 0.93,
            "note": "same school-years, 2013-14 on; the sources count somewhat differently",
        }
    )
    n, r, ratio = _corr(wide["crdc_enrollment"], enr)
    out.append(
        {
            "check": "federal vs district enrollment",
            "n": n,
            "r": r,
            "ratio": ratio,
            "floor": 0.95,
            "note": "federal count date differs from October 1",
        }
    )
    fc = pd.read_parquet(CORE / "facility_condition.parquet")
    out.append(
        {
            "check": "facility FCI recomputed from costs",
            "n": len(fc),
            "r": 1.0
            if (
                (100 * fc["repair_cost"] / fc["replacement_value"] - fc["fci_pct"]).abs().max()
                < 0.01
            )
            else 0.0,
            "ratio": 1.0,
            "floor": 0.999,
            "note": "repair cost / replacement value equals the reported index",
        }
    )
    for r_ in out:
        r_["ok"] = bool(pd.notna(r_["r"]) and r_["r"] >= r_["floor"])
    return out


def coverage() -> pd.DataFrame:
    m = pd.read_parquet(CORE / "school_metric.parquet")
    rep = m[(m["status"] == "reported") & (m["student_group"] == "all")]
    t = rep.groupby(["measure_id", "sy"])["school_id"].nunique().unstack(fill_value=0)
    return t


def status_mix() -> pd.Series:
    m = pd.read_parquet(CORE / "school_metric.parquet")
    return m["status"].value_counts()


def write_report(hard: list[dict], recon: list[dict]) -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    lines = [
        "# Validation report",
        "",
        (
            f"Generated {now} by `uv run psd validate`. Hard checks fail the build; "
            "reconciliations compare independent sources and fail below a stated floor."
        ),
        "",
        "## Hard checks",
        "",
        "| Check | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for c in hard:
        lines.append(f"| {c['check']} | {'pass' if c['ok'] else '**FAIL**'} | {c['detail']} |")
    lines += [
        "",
        "## Reconciliations against independent sources",
        "",
        "| Comparison | School-years | Correlation | Total ratio | Floor | Result | Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in recon:
        lines.append(
            f"| {c['check']} | {c['n']:,} | {c['r']:.3f} | {c['ratio']:.3f} | {c['floor']} | {'pass' if c['ok'] else '**FAIL**'} | {c['note']} |"
        )
    mix = status_mix()
    lines += ["", "## Status mix in school_metric", "", "| Status | Rows |", "| --- | --- |"]
    lines += [f"| {k} | {v:,} |" for k, v in mix.items()]
    cov = coverage()
    lines += [
        "",
        "## Coverage: schools with a reported `all students` value, by measure and school year",
        "",
        "| Measure | " + " | ".join(str(c) for c in cov.columns) + " |",
        "| --- | " + " | ".join("---" for _ in cov.columns) + " |",
    ]
    for measure, row in cov.iterrows():
        lines.append(f"| `{measure}` | " + " | ".join(str(v) if v else "" for v in row) + " |")
    (DOCS / "VALIDATION.md").write_text("\n".join(lines) + "\n")


def run_validation() -> tuple[list[dict], list[dict]]:
    hard, recon = hard_checks(), reconciliations()
    write_report(hard, recon)
    return hard, recon
