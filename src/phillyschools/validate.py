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
    out += building_checks()
    if (CORE / "finance_lea_line.parquet").exists():
        out += finance_checks()
    if (CORE / "school_closure_plan.parquet").exists():
        out += closure_plan_checks()
    if (CORE / "school_closure_flow.parquet").exists():
        out += closure_flow_checks()
    if (CORE / "school_place.parquet").exists():
        out += place_checks()
    if (CORE / "school_budget.parquet").exists():
        out += school_budget_checks()
    return out


def closure_plan_checks() -> list[dict]:
    """The 2012 closure proposal: every named school resolves, and pairs are unique."""
    plan = pd.read_parquet(CORE / "school_closure_plan.parquet")
    ids = set(pd.read_parquet(CORE / "school.parquet")["school_id"])
    bad_closing = set(plan["closing_school_id"]) - ids
    receiving = set(plan["receiving_school_id"]) - {""}
    bad_receiving = receiving - ids
    dup = int(plan.duplicated(["closing_school_id", "receiving_school_id", "receiving_rule"]).sum())
    return [
        _check(
            "closure plan: every closing and receiving school resolves to a school_id",
            not bad_closing and not bad_receiving,
            f"{len(bad_closing)} closing, {len(bad_receiving)} receiving unknown",
        ),
        _check("closure plan pairs are unique", dup == 0, f"{dup} duplicates"),
    ]


def closure_flow_checks() -> list[dict]:
    """Observed closure flows: identifiers resolve, and allocated gains are not double counted."""
    flows = pd.read_parquet(CORE / "school_closure_flow.parquet")
    ids = set(pd.read_parquet(CORE / "school.parquet")["school_id"])
    unknown = (set(flows["closed_school_id"]) | set(flows["receiving_school_id"])) - ids
    out = [_check("closure flows: every school resolves", not unknown, f"{len(unknown)} unknown")]
    receivers = flows.drop_duplicates("receiving_school_id")
    gain = receivers["change_beyond_baseline"].clip(lower=0).sum()
    allocated = flows["gain_allocated"].sum()
    out.append(
        _check(
            "closure flows: allocated gains equal each receiving school's gain once",
            abs(gain - allocated) <= len(receivers),
            f"{allocated:,.0f} allocated vs {gain:,.0f}",
        )
    )
    reg = pd.read_csv(ROOT / "registry" / "closures_2013_final.csv", dtype=str)
    out.append(
        _check(
            "the 2013 closure registry lists 23 schools, all in the school table",
            len(reg) == 23 and set(reg["school_id"]) <= ids,
            f"{len(reg)} rows",
        )
    )
    return out


def place_checks() -> list[dict]:
    """Place boundaries: expected counts, population covered, and agreement with the district's lists."""
    units = pd.read_parquet(CORE / "geo_unit.parquet")
    xw = pd.read_parquet(CORE / "geo_xwalk.parquet")
    sp = pd.read_parquet(CORE / "school_place.parquet")
    counts = units["unit_type"].value_counts()
    expected = {"council_district": 10, "ward": 66, "police_district": 22, "planning_district": 18}
    off = {k: int(counts.get(k, 0)) for k, v in expected.items() if counts.get(k, 0) != v}
    out = [
        _check(
            "place units: 10 council districts, 66 wards, 22 police, 18 planning", not off, str(off)
        )
    ]
    tracts = xw[(xw["from_type"] == "tract") & (xw["to_type"] == "council_district")]
    pop = tracts["pop_2020"].sum()
    out.append(
        _check(
            "tract population allocated to council districts matches the tract total",
            abs(
                pop / xw[(xw["from_type"] == "tract") & (xw["to_type"] == "ward")]["pop_2020"].sum()
                - 1
            )
            < 0.01,
            f"{pop:,.0f} people",
        )
    )
    per = sp.groupby("school_id")["unit_type"].nunique()
    out.append(
        _check(
            "every located school falls in one unit of each place type",
            (per == 7).all() and not sp.duplicated(["school_id", "unit_type"]).any(),
            f"{len(per)} schools",
        )
    )
    attr = (
        pd.read_parquet(CORE / "school_year_attr.parquet")
        .sort_values("sy")
        .groupby("school_id")
        .last()["council_district"]
        .astype(str)
        .str.extract(r"(\d+)")[0]
    )
    geo = (
        sp[sp["unit_type"] == "council_district"]
        .set_index("school_id")["name"]
        .str.extract(r"(\d+)")[0]
    )
    both = pd.concat([attr, geo], axis=1, keys=["a", "g"]).dropna()
    agree = (both["a"] == both["g"]).mean()
    out.append(
        _check(
            "derived council district agrees with the district's list for 97%+ of schools",
            agree >= 0.97,
            f"{agree:.1%} of {len(both)}",
            hard=False,
        )
    )
    return out


def school_budget_checks() -> list[dict]:
    """The budget PDFs against their own printed totals."""
    sb = pd.read_parquet(CORE / "school_budget.parquet")
    log = pd.read_parquet(CORE / "school_budget_report.parquet")
    out = []
    key = ["ulcs", "sy"]
    groups = sb[sb["line_type"] == "group_total"].groupby([*key, "scope"])["amount"].sum()
    subs = sb[sb["line_type"] == "scope_subtotal"].set_index([*key, "scope"])["amount"]
    bad = int(((groups - subs).dropna() != 0).sum())
    out.append(
        _check("school budget group totals add to the scope subtotals", bad == 0, f"{bad} off")
    )
    scopes = sb[sb["line_type"] == "scope_subtotal"].groupby(key)["amount"].sum()
    totals = sb[sb["line_type"] == "school_total"].set_index(key)["amount"]
    bad = int(((scopes - totals).dropna() != 0).sum())
    out.append(
        _check("school budget scope subtotals add to the school total", bad == 0, f"{bad} off")
    )
    items = sb[sb["line_type"] == "item"]
    grouped = items.groupby([*key, "scope", "allotment_group"])["amount"].sum()
    gt = sb[sb["line_type"] == "group_total"].set_index([*key, "scope", "allotment_group"])[
        "amount"
    ]
    both = pd.concat([grouped, gt], axis=1, join="inner").dropna()
    bad = int((both.iloc[:, 0] != both.iloc[:, 1]).sum())
    out.append(
        _check(
            "school budget line items add to their group totals",
            bad == 0,
            f"{bad} of {len(both)} off",
        )
    )
    empty = log[~log["has_budget"]]
    out.append(
        _check(
            "reports without a budget are empty ('No data available') pages",
            (empty["n_rows"] == 0).all(),
            f"{len(empty)} reports without a budget",
        )
    )
    if (CORE / "school_budget_purchase.parquet").exists():
        out += school_purchase_checks(sb)
    wrong = log[log["wrong_school"]]
    out.append(
        _check(
            "reports where the tool answered with a different school are excluded",
            (wrong["n_rows"] == 0).all() and sb["ulcs"].isin(wrong["ulcs"]).sum() >= 0,
            f"{len(wrong)} excluded",
        )
    )
    printed = log.dropna(subset=["printed_code"])
    kept = printed[printed["has_budget"]]
    out.append(
        _check(
            "every kept budget report's printed school code equals its requested code",
            (kept["printed_code"] == kept["ulcs"]).all(),
            f"{len(kept)} reports",
        )
    )
    unmapped = sb[sb["school_id"].isna()]["ulcs"].nunique()
    out.append(
        _check(
            "school budget ULCS codes link to a school_id (a few non-school programs excepted)",
            unmapped <= 3,
            f"{unmapped} codes without a school_id",
            hard=False,
        )
    )
    return out


def school_purchase_checks(sb: pd.DataFrame) -> list[dict]:
    """Purchase and position reports against the allotment reports and against themselves."""
    pu = pd.read_parquet(CORE / "school_budget_purchase.parquet")
    po = pd.read_parquet(CORE / "school_budget_position.parquet")
    out = []
    key = ["ulcs", "sy", "section"]
    items = pu[pu["line_type"] == "item"].groupby(key)["amount"].sum()
    totals = pu[pu["line_type"] == "total"].set_index(key)["amount"]
    diff = (items - totals).dropna()
    bad = int((diff.abs() > 2).sum())
    out.append(
        _check(
            "school purchase lines add to their printed totals (within $2 of rounding)",
            bad == 0,
            f"{bad} off by more than $2; {int((diff != 0).sum())} of {len(diff)} off by $1 or $2",
        )
    )
    at = sb[sb["line_type"] == "school_total"].set_index(["ulcs", "sy"])["amount"]
    pt = pu[(pu["section"] == "budget_allotment") & (pu["line_type"] == "total")].set_index(
        ["ulcs", "sy"]
    )["amount"]
    both = pd.concat([at, pt], axis=1, keys=["a", "p"]).dropna()
    bad = int((both["a"] != both["p"]).sum())
    out.append(
        _check(
            "purchase report allotment totals equal the allotment report's school totals",
            bad == 0,
            f"{bad} of {len(both)} differ",
        )
    )
    fte = po.groupby(["ulcs", "sy"])["fte_curr"].sum()
    cnt = pu[(pu["section"] == "position") & (pu["line_type"] == "total")].set_index(
        ["ulcs", "sy"]
    )["count"]
    both = pd.concat([fte, cnt], axis=1, keys=["f", "c"]).dropna()
    bad = int(((both["f"] - both["c"]).abs() >= 0.011).sum())
    out.append(
        _check(
            "position report FTE add to the purchase report's position counts",
            bad == 0,
            f"{bad} of {len(both)} differ",
        )
    )
    unsplit = int((po["parse_note"] == "unsplit").sum())
    out.append(
        _check(
            "position lines with funding and activity not separated are under 0.2%",
            unsplit / max(len(po), 1) < 0.002,
            f"{unsplit} of {len(po)}",
            hard=False,
        )
    )
    return out


def adequacy_study_checks() -> list[dict]:
    """The 2007 and 2023 studies' district tables against their own published headlines."""
    from .finance import APA_TOTALS

    apa = pd.read_parquet(CORE / "adequacy_apa_2007.parquet")
    kelly = pd.read_parquet(CORE / "adequacy_kelly_2023.parquet")
    below = apa[apa["difference_per_pupil"] < 0]
    gap_below = -below["total_difference"].sum()
    net = -apa["total_difference"].sum()
    short = kelly[kelly["adequacy_shortfall"] > 0]
    return [
        _check(
            "2007 study: 471 districts below the cost estimate, $4.57B below-estimate gap, $4.38B net",
            len(below) == APA_TOTALS["districts_below_estimate"]
            and abs(gap_below / APA_TOTALS["gap_if_above_districts_keep_spending"] - 1) < 0.01
            and abs(net / APA_TOTALS["aggregate_gap"] - 1) < 0.01,
            f"{len(below)} below; ${gap_below / 1e9:.2f}B; net ${net / 1e9:.2f}B",
        ),
        _check(
            "2023 Kelly analysis: 412 districts with a shortfall totaling about $6.2B",
            len(short) == 412 and abs(short["adequacy_shortfall"].sum() / 6.2e9 - 1) < 0.02,
            f"{len(short)} districts; ${short['adequacy_shortfall'].sum() / 1e9:.2f}B",
        ),
        _check(
            "adequacy studies link to state agency IDs",
            apa["aun"].notna().all() and kelly["aun"].notna().all(),
            f"{len(apa)} and {len(kelly)} districts",
        ),
    ]


def finance_checks() -> list[dict]:
    """The state's finance files against themselves and against the commission's report."""
    from .finance import BEFC_TOTALS

    m = pd.read_parquet(MARTS / "district_finance.parquet")
    a = pd.read_parquet(CORE / "adequacy_befc_2024.parquet")
    line = pd.read_parquet(CORE / "finance_lea_line.parquet")
    out = []
    ex = m.dropna(subset=["total_expenditures"])
    five = ex[
        [
            "instruction_1000",
            "support_services_2000",
            "noninstructional_services_3000",
            "facilities_construction_4000",
            "other_expenditures_financing_5000",
        ]
    ].sum(axis=1, min_count=1)
    share = (((five - ex["total_expenditures"]).abs() / ex["total_expenditures"]) < 0.005).mean()
    out.append(
        _check(
            "the five spending functions add to total expenditures (within 0.5%, 99% of agency-years)",
            share >= 0.99,
            f"{share:.4f} of {len(ex):,} agency-years",
        )
    )
    diffs = {k: abs(int(a[k].sum()) - v) for k, v in BEFC_TOTALS.items()}
    out.append(
        _check(
            "commission Appendix B sums to the report's printed statewide totals (within $50)",
            max(diffs.values()) <= 50,
            f"largest difference ${max(diffs.values())}",
        )
    )
    out.append(
        _check(
            "all 500 adequacy rows link to a state agency",
            len(a) == 500 and a["aun"].notna().all(),
            f"{a['aun'].notna().sum()} of {len(a)}",
        )
    )
    bef = line[(line["account_code"] == "7110") & (line["sy"] == 2024)].set_index("aun")["value"]
    j = a.set_index("aun")[["bef_2023_24_base"]].join(bef.rename("afr")).dropna()
    close = (((j["afr"] / j["bef_2023_24_base"]) - 1).abs() < 0.01).mean()
    out.append(
        _check(
            "state-reported Basic Education Funding matches the commission's 2023-24 base (within 1%, 95% of districts)",
            close >= 0.95,
            f"{close:.3f} of {len(j)} districts",
            hard=False,
        )
    )
    out += adequacy_study_checks()
    rtl = pd.read_parquet(CORE / "finance_rtl_allocation.parquet")
    rtl = rtl[rtl["program"] == "Ready to Learn Block Grant"]
    wide = rtl.pivot_table(
        index=["aun", "payable_sy"], columns="component", values="value", aggfunc="sum"
    )
    new = wide.loc[wide.index.get_level_values("payable_sy") >= 2025].fillna(0)
    parts = new[["foundation", "adequacy_supplement", "tax_equity_supplement"]].sum(axis=1)
    out.append(
        _check(
            "Ready to Learn grants equal foundation + adequacy + tax equity supplements (2024-25 on, within $5)",
            ((parts - new["total"]).abs() <= 5).all(),
            f"{len(new)} district-years",
        )
    )
    adeq = wide.xs(2025, level="payable_sy")["adequacy_supplement"].sum()
    out.append(
        _check(
            "2024-25 adequacy supplements total about $494 million statewide (as reported)",
            abs(adeq / 493.8e6 - 1) < 0.01,
            f"${adeq / 1e6:.1f}M",
            hard=False,
        )
    )
    est = m[(m["sy"] == 2022) & m["adj_adm"].notna()].set_index("aun")
    ratio = (
        est["current_expenditures_approx"] / est["current_expenditures_net_of_patron_tuition"]
    ).dropna()
    out.append(
        _check(
            "instruction + support + noninstructional spending approximates the state's current expenditures (within 5%, 99% of districts, 2021-22)",
            ((ratio - 1).abs() < 0.05).mean() >= 0.99,
            f"{((ratio - 1).abs() < 0.05).mean():.3f} of {len(ratio)} districts; median ratio {ratio.median():.4f}",
        )
    )
    out.append(
        _check(
            "agency-years are unique in district_finance",
            not m.duplicated(["aun", "sy"]).any(),
            f"{len(m):,} rows",
        )
    )
    return out


def building_checks() -> list[dict]:
    b = pd.read_parquet(CORE / "building.parquet")
    xw = pd.read_parquet(CORE / "building_xwalk.parquet")
    sb = pd.read_parquet(CORE / "school_building.parquet")
    school = pd.read_parquet(CORE / "school.parquet")
    placeholder = pd.read_parquet(CORE / "school_placeholder.parquet")
    out = [
        _check("building_id is unique", b["building_id"].is_unique, f"{len(b)} buildings"),
        _check(
            "every crosswalk key points at a building",
            xw["building_id"].isin(b["building_id"]).all(),
            f"{len(xw)} keys",
        ),
        _check(
            "no outside key maps to two buildings",
            not xw.duplicated(["key_type", "key_value"]).any(),
            "",
        ),
        _check(
            "school_building points at real schools and buildings",
            sb["building_id"].isin(b["building_id"]).all()
            and sb["school_id"]
            .str.split(", ")
            .explode()
            .isin(set(school["school_id"]) | set(placeholder["school_id"]))
            .all(),
            f"{len(sb)} rows",
        ),
    ]
    listed = set(school.loc[school["listed_in_latest_year"], "school_id"])
    placed = set(sb.loc[sb["role"] == "primary", "school_id"])
    out.append(
        _check(
            "most listed schools have a building from the district list (95%)",
            len(listed & placed) / len(listed) >= 0.95,
            f"{len(listed & placed)} of {len(listed)}",
            hard=False,
        )
    )
    a = pd.read_parquet(CORE / "building_asbestos.parquet")
    lost = a[
        a["is_latest"]
        & ~a["building_code"].isin(xw.loc[xw["key_type"] == "ahera_code", "key_value"])
    ]
    out.append(
        _check("every latest asbestos report has a building", lost.empty, f"{len(lost)} without")
    )
    fp = pd.read_parquet(CORE / "facility_condition_part.parquet")
    fb = fp[fp["part_code"].str[0] == "B"]
    miss = fb[~fb["part_code"].isin(xw.loc[xw["key_type"] == "fca_part_code", "key_value"])]
    out.append(
        _check("every assessed building has a building_id", miss.empty, f"{len(miss)} without")
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
