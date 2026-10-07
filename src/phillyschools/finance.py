"""School finance from the state (and later the district): sources, catalog, and tables.

pde_afr: the Pennsylvania Department of Education's Annual Financial Report data, one row per
local education agency (school district, charter school, career and technology center) and
fiscal year. Excel files, free to download. Philadelphia is "Philadelphia City SD"; each
charter school is its own LEA. See docs/FINANCE.md for what each table is and how to read it.
"""

import re
from datetime import UTC, datetime

import pandas as pd

from . import CORE, RAW
from .discover import file_row, read_files_catalog, write_files_catalog

AFR_BASE = (
    "https://www.pa.gov/content/dam/copapwp-pagov/en/education/documents/schools/"
    "grants-and-funding/school-finances/summary-of-afr-data/afr-data-detailed/"
)
AFR_FILES = [
    "finances afr localrev 1516-2425.xlsx",
    "finances afr staterev 1516-2425.xlsx",
    "finances afr federalrev 1516-2425.xlsx",
    "finances afr otherrev 1516-2425.xlsx",
    "finances afr expdetail 1516-2425.xlsx",
    "finances afr majorobject 1516-2425.xlsx",
    "finances afr supportsvcs 1516-2425.xlsx",
    "finances aie 0809-2324.xlsx",
    "finances afr tuitionsched 1516-2425.xlsx",
    "finances afr genfundbalance 1516-2425.xlsx",
    "finances afr localproptaxes 1415-2324.xlsx",
    "finances afr soin 1516-2425.xlsx",
]


BEFC_URL = "https://www.pahouse.com/files/Documents/2024-01-11_123718__Report2.pdf"


def catalog_afr() -> list[dict]:
    """Catalog the AFR files and the Basic Education Funding Commission report."""
    today = datetime.now(UTC).date().isoformat()
    rows = [file_row("pde_afr", AFR_BASE + f.replace(" ", "%20"), today) for f in AFR_FILES]
    for r in rows:
        r["filename"] = r["filename"].replace("%20", " ")
    befc = file_row("befc_report", BEFC_URL, today)
    befc["filename"] = "BEFC Report 2024-01-11.pdf"
    rows.append(befc)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in rows:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())
    return rows


# ---------------------------------------------------------------------------------------------
# Tables


AFR_DIR = RAW / "pde_afr"
LEA_TYPES = {1: "school_district", 3: "career_technology_center", 4: "charter_school", 6: "other"}
ACCOUNT_FILES = {
    "localrev": "revenue_local",
    "staterev": "revenue_state",
    "federalrev": "revenue_federal",
    "otherrev": "revenue_other",
    "expdetail": "expenditure_function",
    "majorobject": "expenditure_object",
    "supportsvcs": "expenditure_support_detail",
}
TUITION_COLUMNS = {
    "Tuition to Other SDs in the State": "other_school_districts",
    "Tuition to Brick & Mortar Charter Schools: Nonspecial": "charter_brick_and_mortar_regular",
    "Tuition to Cyber Charter Schools: Nonspecial": "charter_cyber_regular",
    "Tuition to Brick & Mortar Charter Schools: Special": "charter_brick_and_mortar_special_ed",
    "Tuition to Cyber Charter Schools: Special": "charter_cyber_special_ed",
    "Tuition to Nonpublic Schools": "nonpublic_schools",
    "Tuition to CTCs": "career_technology_centers",
    "Tuition to Higher Ed and Technical Institutes": "higher_ed_technical",
    "Tuition to Approved Private Schools": "approved_private_schools",
    "Tuition to PRRIs and Detention Centers": "detention_centers",
    "Tuition to Other LEAs": "other_leas",
}


def _clean(label) -> str:
    return re.sub(r"\s+", " ", str(label)).strip()


def _fy_to_sy(sheet: str) -> int:
    return int(sheet[:2] + sheet[-2:]) if re.fullmatch(r"\d{4}-\d{2}", sheet) else int(sheet[-4:])


def _aun(v) -> str | None:
    return None if pd.isna(v) else str(int(float(v))).zfill(9)


def _account_code(label: str, group: str) -> str:
    if group == "expenditure_object":
        m = re.match(r"Object (\d{3})", label)
        return f"obj_{m.group(1)}" if m else "obj_total"
    m = re.search(r"(\d{4})$", label)
    if m:
        return m.group(1)
    return (
        "total_expenditures" if label.startswith("Total Exp") else label.lower().replace(" ", "_")
    )


def _level(code: str) -> int | None:
    if not code.isdigit():
        return None
    return (
        1 if code.endswith("000") else 2 if code.endswith("00") else 3 if code.endswith("0") else 4
    )


def read_account_file(stem: str, group: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = AFR_DIR / f"finances afr {stem} 1516-2425.xlsx"
    book = pd.ExcelFile(path, engine="calamine")
    lines, accounts = [], []
    for sheet in book.sheet_names:
        d = book.parse(sheet)
        d.columns = ["category", "aun", "lea_name", "county", *[_clean(c) for c in d.columns[4:]]]
        d["aun"] = d["aun"].map(_aun)
        d = d.dropna(subset=["aun"])
        value_cols = list(d.columns[4:])
        long = d.melt(
            ["category", "aun", "lea_name", "county"], value_cols, "label", "value"
        ).dropna(subset=["value"])
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long = long.dropna(subset=["value"])
        long["account_code"] = [_account_code(lb, group) for lb in long["label"]]
        long["sy"] = _fy_to_sy(sheet)
        long["table_group"] = group
        lines.append(long)
        accounts.append(long[["table_group", "account_code", "label", "sy"]].drop_duplicates())
    out = pd.concat(lines, ignore_index=True)
    acc = (
        pd.concat(accounts, ignore_index=True)
        .sort_values("sy")
        .drop_duplicates(["table_group", "account_code"], keep="last")
    )
    return out, acc


def _strip_code(label: str) -> str:
    return re.sub(
        r"\s*(Object \d{3}\s*)?\d{0,4}$", "", re.sub(r"^Object \d{3} ", "", label)
    ).strip()


def read_tuition() -> pd.DataFrame:
    book = pd.ExcelFile(AFR_DIR / "finances afr tuitionsched 1516-2425.xlsx", engine="calamine")
    out = []
    for sheet in book.sheet_names:
        d = book.parse(sheet)
        d.columns = ["aun", "lea_name", "county", *[_clean(c) for c in d.columns[3:]]]
        d["aun"] = d["aun"].map(_aun)
        d = d.dropna(subset=["aun"])
        long = d.melt(["aun", "lea_name", "county"], list(d.columns[3:]), "label", "value")
        long = long.dropna(subset=["value"])
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long["tuition_type"] = long["label"].map(TUITION_COLUMNS)
        long["sy"] = _fy_to_sy(sheet)
        out.append(long.dropna(subset=["value", "tuition_type"]))
    return pd.concat(out, ignore_index=True)


def read_instruction_expense() -> pd.DataFrame:
    d = pd.ExcelFile(AFR_DIR / "finances aie 0809-2324.xlsx", engine="calamine").parse(0)
    d = d.rename(columns={"School District": "lea_name", "AUN": "aun", "County": "county"})
    d["aun"] = d["aun"].map(_aun)
    d = d.dropna(subset=["aun"])
    years = [c for c in d.columns if re.fullmatch(r"\d{4}-\d{2}", str(c))]
    long = d.melt(["aun", "lea_name", "county"], years, "fy", "value").dropna(subset=["value"])
    long["sy"] = long["fy"].map(_fy_to_sy)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    return long.dropna(subset=["value"]).drop(columns="fy")


def read_fund_balance() -> pd.DataFrame:
    book = pd.ExcelFile(AFR_DIR / "finances afr genfundbalance 1516-2425.xlsx", engine="calamine")
    out = []
    for sheet in book.sheet_names:
        d = book.parse(sheet)
        d.columns = ["category", "aun", "lea_name", "county", *[_clean(c) for c in d.columns[4:]]]
        d["aun"] = d["aun"].map(_aun)
        d = d.dropna(subset=["aun"])
        long = d.melt(
            ["category", "aun", "lea_name", "county"], list(d.columns[4:]), "label", "value"
        )
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long["fund_balance_type"] = long["label"].str.extract(r"^(\w+)")[0].str.lower()
        long["sy"] = _fy_to_sy(sheet)
        out.append(long.dropna(subset=["value"]))
    return pd.concat(out, ignore_index=True)


def build_finance() -> dict:
    lines, accounts = [], []
    for stem, group in ACCOUNT_FILES.items():
        long, acc = read_account_file(stem, group)
        long["source_id"] = f"pde_afr:{stem}"
        lines.append(long)
        accounts.append(acc)
    line = pd.concat(lines, ignore_index=True)
    account = pd.concat(accounts, ignore_index=True)
    account["label"] = account["label"].map(_strip_code)
    account["level"] = account["account_code"].map(_level)
    tuition = read_tuition().assign(source_id="pde_afr:tuitionsched")
    aie = read_instruction_expense().assign(source_id="pde_afr:aie")
    fund = read_fund_balance().assign(source_id="pde_afr:genfundbalance")
    directory = (
        pd.concat(
            [
                line[["aun", "lea_name", "county", "category", "sy"]],
                fund[["aun", "lea_name", "county", "category", "sy"]],
            ]
        )
        .sort_values("sy")
        .groupby("aun", as_index=False)
        .agg(
            lea_name=("lea_name", "last"),
            county=("county", "last"),
            category=("category", "last"),
            first_sy=("sy", "min"),
            last_sy=("sy", "max"),
        )
    )
    directory["lea_type"] = directory["category"].map(lambda c: LEA_TYPES.get(int(c), "other"))
    directory = directory.drop(columns="category")
    bef = read_bef_workbooks()
    bef_alloc = bef[bef["sheet_role"] == "allocation"].drop(columns="sheet_role")
    bef_input = bef[bef["sheet_role"] != "allocation"]
    enrollment = build_bef_enrollment(bef)
    line = line.drop(columns=["category", "lea_name", "county", "label"])
    line["status"] = "reported"
    line = line[["aun", "sy", "table_group", "account_code", "value", "status", "source_id"]]
    return {
        "finance_lea": directory,
        "finance_lea_line": line,
        "finance_account": account[["table_group", "account_code", "label", "level"]],
        "finance_lea_tuition": tuition[["aun", "sy", "tuition_type", "value", "source_id"]],
        "finance_lea_instruction": aie[["aun", "sy", "value", "source_id"]],
        "finance_lea_fund_balance": fund[["aun", "sy", "fund_balance_type", "value", "source_id"]],
        "finance_bef_allocation": bef_alloc,
        "finance_bef_input": bef_input,
        "finance_district_enrollment": enrollment,
        "finance_rtl_allocation": read_rtl(),
    }


MART_DOCS = {
    "aun": "State agency ID (9 digits) for the school district, charter school, or career center.",
    "lea_name": "Agency name as in the state's files.",
    "county": "County.",
    "lea_type": "school_district, charter_school, career_technology_center, or other.",
    "sy": "Spring year of the fiscal year (2024 = FY 2023-24, July to June).",
    "total_expenditures": "All expenditures reported, including facilities and other financing uses (debt service and refunding), in nominal dollars.",
    "current_expenditures_approx": "Instruction + support services + noninstructional services (1000 + 2000 + 3000). Approximates the commission's 'current expenditures', which also nets out tuition-for-patrons revenue, so this runs slightly high. Derived.",
    "instruction_1000": "Instruction (function 1000).",
    "support_services_2000": "Support services (function 2000).",
    "noninstructional_services_3000": "Operation of noninstructional services (function 3000).",
    "facilities_construction_4000": "Facilities acquisition, construction, and improvement (function 4000).",
    "other_expenditures_financing_5000": "Other expenditures and financing uses (function 5000), including debt service and refunding.",
    "local_revenue_6000": "Total local revenue (6000).",
    "current_real_estate_taxes_6111": "Current real estate taxes (6111).",
    "state_revenue_7000": "Total state revenue (7000).",
    "basic_education_funding_7110": "State Basic Education Funding (7110).",
    "federal_revenue_8000": "Total federal revenue (8000).",
    "other_revenue_9000": "Other revenue (9000): bond and note proceeds, transfers, and similar. Not operating revenue.",
    "salaries_obj_100": "Salaries (object 100).",
    "benefits_obj_200": "Employee benefits (object 200).",
    "charter_tuition_paid": "Tuition a school district paid to charter schools (brick-and-mortar and cyber, regular and special education). Blank for charter schools and career centers.",
    "tuition_paid_total": "All tuition a school district paid, to any recipient.",
    "actual_instruction_expense": "The state's actual instruction expense for the school district (2008-09 to 2023-24).",
    "general_fund_balance": "Committed + assigned + unassigned general fund balance.",
    "rtl_total_allocation": "The state's Ready to Learn Block Grant allocation for the school district (payable year = this fiscal year), as allocated, not as booked. School districts only.",
    "rtl_adequacy_supplement_allocation": "The adequacy supplement within the Ready to Learn Block Grant (enacted from 2024-25): the state's adequacy investment for this district that year. It is new money added in that year and rolls into the next year's foundation, so do not add years without noting that.",
    "rtl_tax_equity_supplement_allocation": "The tax equity supplement within the Ready to Learn Block Grant (enacted from 2024-25).",
    "adj_adm": "Adjusted average daily membership: the enrollment base the state uses in the Basic Education Funding formula (school districts only), from the state's BEF workbooks.",
    "current_expenditures_net_of_patron_tuition": "The state's current expenditures minus tuition from patrons revenue (the definition in the funding law and the commission's adequacy calculation), from the BEF workbooks. School districts only; 2016-17 to 2022-23.",
    "current_exp_per_weighted_student": "The state's current expenditures per weighted student in the BEF formula. Its weighted-student count is not the same as the commission's or Kelly's, so do not compare it with their adequacy targets per student.",
    "pde_enrollment": "October 1 enrollment of the agency's own schools, from PDE's public school enrollment file (2016 on). For a school district it excludes students it pays to attend charter schools; a charter school's row is its own enrollment.",
    "pde_low_income_students": "Low-income students counted on October 1 (PDE).",
    "pde_low_income_share": "pde_low_income_students divided by pde_enrollment.",
    "current_expenditures_per_pde_enrollment": "current_expenditures_approx divided by pde_enrollment. Derived. Left empty for school districts, whose spending includes tuition paid for students they do not enroll; for charter schools and career and technical centers it is spending per enrolled student.",
    "essa_adm": "Average daily membership in the state's ESSA per-pupil expenditure report (2018-19 on), the sum over the agency's school buildings.",
    "essa_expenditures_total": "Personnel and non-personnel expenditures from local, state and federal funds charged to the agency's school buildings in the ESSA report (2018-19 on). Not the same as total expenditures: it leaves out most central, debt and transfer costs.",
    "essa_expenditure_per_adm": "essa_expenditures_total divided by essa_adm. Derived.",
    "current_expenditures_per_adj_adm": "current_expenditures_approx divided by adj_adm. Derived; dollars per adjusted ADM, nominal.",
}
MART_LINES = {
    "total_expenditures": ("expenditure_function", "total_expenditures"),
    "instruction_1000": ("expenditure_function", "1000"),
    "support_services_2000": ("expenditure_function", "2000"),
    "noninstructional_services_3000": ("expenditure_function", "3000"),
    "facilities_construction_4000": ("expenditure_function", "4000"),
    "other_expenditures_financing_5000": ("expenditure_function", "5000"),
    "local_revenue_6000": ("revenue_local", "6000"),
    "current_real_estate_taxes_6111": ("revenue_local", "6111"),
    "state_revenue_7000": ("revenue_state", "7000"),
    "basic_education_funding_7110": ("revenue_state", "7110"),
    "federal_revenue_8000": ("revenue_federal", "8000"),
    "other_revenue_9000": ("revenue_other", "9000"),
    "salaries_obj_100": ("expenditure_object", "obj_100"),
    "benefits_obj_200": ("expenditure_object", "obj_200"),
}
CHARTER_TUITION = [
    "charter_brick_and_mortar_regular",
    "charter_brick_and_mortar_special_ed",
    "charter_cyber_regular",
    "charter_cyber_special_ed",
]


def build_district_finance(t: dict) -> pd.DataFrame:
    """One row per agency and school year with the headline lines, wide, in nominal dollars.

    Revenue and expenditure are as the agency reported them to the state, not adjusted for
    inflation, enrollment, or fund type. Charter tuition is what a school district paid to
    charter schools (a payer's expense); a charter school's own revenue is on its own row."""
    line = t["finance_lea_line"]
    parts = []
    for name, (group, code) in MART_LINES.items():
        s = line[(line["table_group"] == group) & (line["account_code"] == code)]
        parts.append(s.set_index(["aun", "sy"])["value"].rename(name))
    tu = t["finance_lea_tuition"]
    charter = tu[tu["tuition_type"].isin(CHARTER_TUITION)].groupby(["aun", "sy"])["value"].sum()
    parts.append(charter.rename("charter_tuition_paid"))
    parts.append(tu.groupby(["aun", "sy"])["value"].sum().rename("tuition_paid_total"))
    parts.append(
        t["finance_lea_instruction"]
        .set_index(["aun", "sy"])["value"]
        .rename("actual_instruction_expense")
    )
    fb = (
        t["finance_lea_fund_balance"]
        .groupby(["aun", "sy"])["value"]
        .sum()
        .rename("general_fund_balance")
    )
    parts.append(fb)
    wide = pd.concat(parts, axis=1).reset_index()
    wide["current_expenditures_approx"] = wide[
        ["instruction_1000", "support_services_2000", "noninstructional_services_3000"]
    ].sum(axis=1, min_count=1)
    enr = t["finance_district_enrollment"].drop(columns="source_id")
    wide = wide.merge(enr, on=["aun", "sy"], how="left")
    rtl = t["finance_rtl_allocation"]
    for comp in ["total", "adequacy_supplement", "tax_equity_supplement"]:
        r = rtl[(rtl["component"] == comp) & (rtl["program"] == "Ready to Learn Block Grant")]
        r = (
            r.groupby(["aun", "payable_sy"])["value"]
            .sum()
            .rename(f"rtl_{comp}_allocation")
            .reset_index()
        )
        wide = wide.merge(r.rename(columns={"payable_sy": "sy"}), on=["aun", "sy"], how="left")
    wide["current_expenditures_per_adj_adm"] = (
        wide["current_expenditures_approx"] / wide["adj_adm"]
    ).where(wide["adj_adm"].notna())
    out = t["finance_lea"][["aun", "lea_name", "county", "lea_type"]].merge(
        wide, on="aun", how="right"
    )
    enroll_path = CORE / "finance_lea_enrollment.parquet"
    if enroll_path.exists():
        e = pd.read_parquet(enroll_path)[
            ["aun", "sy", "enrollment", "low_income_students", "low_income_share"]
        ].rename(
            columns={
                "enrollment": "pde_enrollment",
                "low_income_students": "pde_low_income_students",
                "low_income_share": "pde_low_income_share",
            }
        )
        out = out.merge(e, on=["aun", "sy"], how="left")
        out["current_expenditures_per_pde_enrollment"] = (
            out["current_expenditures_approx"] / out["pde_enrollment"]
        ).round(2)
        # a district's spending includes tuition for students it does not enroll
        out.loc[out["lea_type"] == "school_district", "current_expenditures_per_pde_enrollment"] = (
            None
        )
    ppe_path = CORE / "finance_lea_ppe.parquet"
    if ppe_path.exists():
        ppe = pd.read_parquet(ppe_path)[
            ["aun", "sy", "adm", "total_expenditures", "expenditure_per_adm"]
        ].rename(
            columns={
                "adm": "essa_adm",
                "total_expenditures": "essa_expenditures_total",
                "expenditure_per_adm": "essa_expenditure_per_adm",
            }
        )
        out = out.merge(ppe, on=["aun", "sy"], how="left")
    return out.sort_values(["aun", "sy"]).reset_index(drop=True)


def write_finance(t: dict) -> pd.DataFrame:
    from .marts import MARTS

    mart = build_district_finance(t)
    write_adequacy(t)
    for name, df in t.items():
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    MARTS.mkdir(exist_ok=True)
    mart.to_parquet(MARTS / "district_finance.parquet", index=False)
    mart.to_csv(MARTS / "district_finance.csv", index=False)
    from .marts import write_schema_json

    write_schema_json(
        "district_finance", mart, "aun x sy", {c: {"description": d} for c, d in MART_DOCS.items()}
    )
    return mart


# ---------------------------------------------------------------------------------------------
# Adequacy: the Basic Education Funding Commission's calculation (Appendix B)

BEFC_PDF = RAW / "befc_report" / "BEFC Report 2024-01-11.pdf"
BEFC_ROW = re.compile(
    r"^(?P<name>.+?)\s{2,}(?P<county>[A-Za-z][A-Za-z .'\-]+?)\s+"
    r"\$(?P<gap>[\d,]+)\s+\$(?P<tax>[\d,]+)\s+(?P<pct>\d+)%\s+\$(?P<bef>[\d,]+)\s+"
    r"\$(?P<formula>[\d,]+)\s+\$(?P<year1>[\d,]+)\s+\$(?P<total>[\d,]+)\s*$"
)
BEFC_TOTALS = {  # printed on the first row of Appendix B, used as a reconciliation
    "state_share_of_adequacy_gap": 5_143_853_632,
    "tax_equity_supplement": 955_535_128,
    "bef_2023_24_base": 7_872_444_057,
    "year1_adequacy_and_equity_2024_25": 871_341_251,
    "total_bef_increase_2024_25": 1_071_341_251,
}


BEFC_NAME_FIXES = {"Charleroi SD": "Charleroi Area SD"}


def _dollars(s: str) -> int:
    return int(s.replace(",", ""))


def read_befc_appendix_b() -> pd.DataFrame:
    from .envresults import pdf_text

    text = pdf_text(BEFC_PDF)
    rows = []
    for line in text.splitlines():
        m = BEFC_ROW.match(line.replace("‐", "-").replace("‑", "-"))
        if not m:
            continue
        g = m.groupdict()
        rows.append(
            {
                "lea_name": " ".join(g["name"].split()),
                "county": g["county"].strip(),
                "state_share_of_adequacy_gap": _dollars(g["gap"]),
                "tax_equity_supplement": _dollars(g["tax"]),
                "target_pct_of_2021_22_current_expenditures": int(g["pct"]),
                "bef_2023_24_base": _dollars(g["bef"]),
                "formula_driven_funds_2024_25": _dollars(g["formula"]),
                "year1_adequacy_and_equity_2024_25": _dollars(g["year1"]),
                "total_bef_increase_2024_25": _dollars(g["total"]),
            }
        )
    return pd.DataFrame(rows)


def build_adequacy(t: dict) -> pd.DataFrame:
    """The commission's per-district calculation, linked to the state's agency IDs.

    Source: Basic Education Funding Commission final report, January 11, 2024, Appendix B.
    Method (the commission's): the median current spending per weighted student of districts
    that meet state performance standards ($13,704) times each district's weighted student
    count is its adequacy target; the gap is the target minus 2021-22 current expenditures.
    The columns are the state's share of that gap, the tax equity supplement, and the
    recommended 2024-25 increases. Other adequacy studies use other methods and are separate."""
    b = read_befc_appendix_b()
    b["lea_name"] = b["lea_name"].replace(BEFC_NAME_FIXES)  # the report's name for the state's
    lea = t["finance_lea"]
    lea = lea[lea["lea_type"] == "school_district"][["aun", "lea_name", "county"]]
    out = b.merge(lea, on=["lea_name", "county"], how="left")
    out.insert(0, "aun", out.pop("aun"))
    out["study"] = "befc_2024"
    out["source_id"] = "befc_report:appendix_b"
    out["status"] = "reported"
    return out


def write_adequacy(t: dict) -> pd.DataFrame:
    from .marts import MARTS

    a = build_adequacy(t)
    studies = build_adequacy_studies({**t, "adequacy_befc_2024": a})
    tables = {
        "adequacy_befc_2024": a,
        "adequacy_apa_2007": studies["adequacy_apa_2007"],
        "adequacy_kelly_2023": studies["adequacy_kelly_2023"],
    }
    for name, df in tables.items():
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    MARTS.mkdir(exist_ok=True)
    cmp = studies["adequacy_compare"]
    cmp.to_parquet(MARTS / "adequacy_compare.parquet", index=False)
    cmp.to_csv(MARTS / "adequacy_compare.csv", index=False)
    return a


# ---------------------------------------------------------------------------------------------
# District school budgets (the School Budgets tool's public report URLs)

BUDGET_PAGE = "https://apps1.philasd.org/school-budgets/"
BUDGET_SERVLET = BUDGET_PAGE + "servlet"
BUDGET_HANDLER = "org.philasd.SchoolBudgets.handler.BuildNoAuthReportHandler"
BUDGET_REPORTS = {
    "allotment": ("public_budget_allotment_report", "School Budget Allotment Detail"),
    "purchases": ("public_purchase_summary_report", "Summary of School Purchases"),
    "positions": ("public_allotment_report", "Position Summary of School Purchases"),
}


def budget_options() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(schools, snapshots) from the tool's own dropdowns: ULCS codes and fiscal-year snapshots."""
    import requests

    from . import USER_AGENT

    html = requests.get(BUDGET_PAGE, headers={"User-Agent": USER_AGENT}, timeout=60).text

    def options(name: str) -> list[tuple[str, str]]:
        block = re.search(rf'<select name="{name}".*?</select>', html, re.DOTALL).group(0)
        found = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', block)
        return [(v, re.sub(r"&nbsp;|\s+", " ", t).strip()) for v, t in found if v]

    return options("ulcsCode"), options("snapshotId")


def catalog_school_budgets(kinds: tuple[str, ...] = ("allotment",)) -> list[dict]:
    """One catalog row per school, fiscal year, and report kind, using the tool's public URLs."""
    from urllib.parse import urlencode

    schools, snaps = budget_options()
    today = datetime.now(UTC).date().isoformat()
    rows = []
    for snap_id, label in snaps:
        m = re.match(r"FY(\d{2}) School Budgets", label)
        if not m:
            continue
        fy = f"FY{m.group(1)}"
        sy = 2000 + int(m.group(1))
        for ulcs, _name in schools:
            for kind in kinds:
                report, title = BUDGET_REPORTS[kind]
                url = (
                    BUDGET_SERVLET
                    + "?"
                    + urlencode(
                        {
                            "handler": BUDGET_HANDLER,
                            "PARAM_EOS_CODE": ulcs,
                            "PARAM_SNAPSHOT_ID": snap_id,
                            "PARAM_REPORT_NAME": report,
                            "PARAM_REPORT_TITLE": title,
                        }
                    )
                )
                r = file_row("sdp_school_budgets", url, today)
                r.update(filename=f"{ulcs}_{kind}.pdf", subdir=fy, ext=".pdf", sy=str(sy))
                rows.append(r)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in rows:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())
    return rows


# ---------------------------------------------------------------------------------------------
# State funding distributions and the adequacy studies' primary documents

PDE_FUNDING = (
    "https://www.pa.gov/content/dam/copapwp-pagov/en/education/documents/schools/"
    "grants-and-funding/school-finances/historical-files-and-reports/"
)
PAYABLE_YEARS = [f"{y}-{str(y + 1)[-2:]}" for y in range(2016, 2026)]
ADEQUACY_DOCS = [
    (
        "kelly_adequacy_2023",
        "https://pubintlaw.org/wp-content/uploads/2023/09/Kelly-BEF-written-testimony-final.pdf",
        "Kelly BEF written testimony 2023-09.pdf",
    ),
    (
        "kelly_adequacy_2023",
        "https://pubintlaw.org/wp-content/uploads/2023/09/Kelly_StudentTotalsandShortfalls.xlsx",
        "Kelly Student Totals and Shortfalls 2023-09.xlsx",
    ),
    (
        "apa_costing_out_2007",
        "https://phlcouncil.com/wp-content/uploads/2016/01/Part-2-Appendix-1-PACostStudy-APA-07-1.pdf",
        "APA Costing Out Pennsylvania 2007.pdf",
    ),
]


def catalog_state_funding() -> list[dict]:
    """Catalog the state's BEF/SEF/Ready-to-Learn files and the two adequacy studies' documents."""
    today = datetime.now(UTC).date().isoformat()
    rows = []
    for kind, folder in [("bef", "basic-education"), ("sef", "special-education")]:
        for yr in PAYABLE_YEARS:
            url = f"{PDE_FUNDING}{folder}/finances%20{kind}%20{yr}.xlsx"
            r = file_row("pde_subsidies", url, today)
            r["filename"] = f"finances {kind} {yr}.xlsx"
            rows.append(r)
    rtl = (
        PDE_FUNDING
        + "ready-to-learn-block-grant---pa-accountability-grants/rtl-pag%202004-05%20to%202025-26.xlsx"
    )
    r = file_row("pde_subsidies", rtl, today)
    r["filename"] = "rtl-pag 2004-05 to 2025-26.xlsx"
    rows.append(r)
    for key, url, name in ADEQUACY_DOCS:
        r = file_row(key, url, today)
        r["filename"] = name
        rows.append(r)
    catalog = {(r["source_key"], r["url"]): r for r in read_files_catalog()}
    for r in rows:
        catalog.setdefault((r["source_key"], r["url"]), r)
    write_files_catalog(catalog.values())
    return rows


# ---------------------------------------------------------------------------------------------
# The other two adequacy studies (primary documents)

APA_PDF = RAW / "apa_costing_out_2007" / "2016" / "01" / "APA Costing Out Pennsylvania 2007.pdf"
KELLY_XLSX = (
    RAW / "kelly_adequacy_2023" / "2023" / "09" / "Kelly Student Totals and Shortfalls 2023-09.xlsx"
)
APA_RECORD = re.compile(
    r"(?P<aun>\d{9})\s+(?P<name>[A-Z][^$\n]*?(?:SD|CS|CHS))\s+(?P<county>[A-Z][A-Za-z .'\-]+?)\s+"
    r"(?P<adm>[\d,]+)\s+\$(?P<spend>[\d,]+)\s+\$(?P<est>[\d,]+)\s+(?P<diff>-?\$?-?[\d,]+)"
)
APA_TOTALS = {  # the report's headline figures (2005-06 dollars), used as reconciliations
    "statewide_estimate": 21.63e9,
    "aggregate_gap": 4.38e9,
    "gap_if_above_districts_keep_spending": 4.57e9,
    "districts_below_estimate": 471,
}


def read_apa_appendix_f() -> pd.DataFrame:
    """Appendix F of the 2007 Costing-Out Study: spending against the cost estimate by district."""
    from .envresults import pdf_text

    text = pdf_text(APA_PDF)
    at = text.find(
        "Comparing Actual Spending With Costing Out Estimates", text.find("Appendix F", 20000)
    )
    rows = []
    for line in text[at:].splitlines():
        for m in APA_RECORD.finditer(line):
            g = m.groupdict()
            diff = int(re.sub(r"[^\d]", "", g["diff"]))
            if "-" in g["diff"]:
                diff = -diff
            rows.append(
                {
                    "aun": g["aun"],
                    "lea_name": " ".join(g["name"].split()),
                    "county": g["county"].strip(),
                    "adm_2005_06": _dollars(g["adm"]),
                    "spending_per_pupil_2005_06": _dollars(g["spend"]),
                    "costing_out_per_pupil": _dollars(g["est"]),
                    "difference_per_pupil": diff,
                }
            )
    out = pd.DataFrame(rows).drop_duplicates("aun")
    out["total_difference"] = out["difference_per_pupil"] * out["adm_2005_06"]
    return out


def read_kelly_2023() -> pd.DataFrame:
    d = pd.ExcelFile(KELLY_XLSX, engine="calamine").parse(0)
    d = d.iloc[:, :7]
    d.columns = [
        "aun",
        "lea_name",
        "county",
        "weighted_adm_sped_poverty_adjusted",
        "adequacy_target",
        "adequacy_shortfall",
        "adequacy_shortfall_per_adm",
    ]
    d["aun"] = d["aun"].map(_aun)
    return d.dropna(subset=["aun"]).reset_index(drop=True)


def build_adequacy_studies(t: dict) -> dict:
    apa = read_apa_appendix_f().assign(
        study="apa_2007", source_id="apa_costing_out_2007:appendix_f"
    )
    kelly = read_kelly_2023().assign(
        study="kelly_2023", source_id="kelly_adequacy_2023:totals_and_shortfalls"
    )
    befc = t["adequacy_befc_2024"] if "adequacy_befc_2024" in t else build_adequacy(t)
    wide = (
        befc[
            [
                "aun",
                "lea_name",
                "county",
                "state_share_of_adequacy_gap",
                "target_pct_of_2021_22_current_expenditures",
                "year1_adequacy_and_equity_2024_25",
            ]
        ]
        .rename(
            columns={
                "state_share_of_adequacy_gap": "befc_2024_state_share_of_gap",
                "target_pct_of_2021_22_current_expenditures": "befc_2024_target_pct_of_2021_22_spending",
                "year1_adequacy_and_equity_2024_25": "befc_2024_recommended_year1_adequacy_and_equity",
            }
        )
        .merge(
            kelly[["aun", "adequacy_shortfall", "adequacy_shortfall_per_adm"]].rename(
                columns={
                    "adequacy_shortfall": "kelly_2023_shortfall",
                    "adequacy_shortfall_per_adm": "kelly_2023_shortfall_per_weighted_adm",
                }
            ),
            on="aun",
            how="outer",
        )
        .merge(
            apa[["aun", "difference_per_pupil", "total_difference"]].rename(
                columns={
                    "difference_per_pupil": "apa_2007_difference_per_pupil_2005_06",
                    "total_difference": "apa_2007_total_difference_2005_06",
                }
            ),
            on="aun",
            how="outer",
        )
    )
    rtl = t["finance_rtl_allocation"]
    for sy, label in [(2025, "2024_25"), (2026, "2025_26")]:
        for comp in ["adequacy_supplement", "tax_equity_supplement"]:
            r = rtl[(rtl["payable_sy"] == sy) & (rtl["component"] == comp)].set_index("aun")[
                "value"
            ]
            wide = wide.merge(
                r.rename(f"enacted_{comp}_{label}"), left_on="aun", right_index=True, how="left"
            )
    wide["enacted_adequacy_and_equity_2024_25"] = wide[
        ["enacted_adequacy_supplement_2024_25", "enacted_tax_equity_supplement_2024_25"]
    ].sum(axis=1, min_count=1)
    names = t["finance_lea"][["aun", "lea_name", "county"]]
    wide = wide.drop(columns=["lea_name", "county"]).merge(names, on="aun", how="left")
    cols = ["aun", "lea_name", "county"] + [
        c for c in wide.columns if c not in {"aun", "lea_name", "county"}
    ]
    return {"adequacy_apa_2007": apa, "adequacy_kelly_2023": kelly, "adequacy_compare": wide[cols]}


# ---------------------------------------------------------------------------------------------
# Basic Education Funding workbooks: allocations, enrollment base, and the formula's inputs

BEF_DIR = RAW / "pde_subsidies"
BEF_ROLES = {"allocation": None, "student_weighting": "weight", "local_effort": "local effort"}


def _bef_sheets(names: list[str]) -> dict[str, str]:
    """Map each workbook's sheets to a role: the allocation sheet, student weighting, local effort."""
    roles = {}
    for n in names:
        low = n.lower()
        if low == "narrative" or "sparsity" in low:
            continue
        if "weight" in low:
            roles["student_weighting"] = n
        elif "local effort" in low:
            roles["local_effort"] = n
        elif "allocation" not in roles:
            roles["allocation"] = n
    return roles


def read_bef_workbooks() -> pd.DataFrame:
    out = []
    for path in sorted(BEF_DIR.rglob("finances bef *.xlsx")):
        yr = re.search(r"(\d{4})-(\d{2})", path.name)
        payable_sy = int(yr.group(1)) + 1
        book = pd.ExcelFile(path, engine="calamine")
        for role, sheet in _bef_sheets(book.sheet_names).items():
            d = book.parse(sheet)
            d.columns = ["aun", "lea_name", "county", *[_clean(c) for c in d.columns[3:]]]
            d["aun"] = d["aun"].map(_aun)
            d = d.dropna(subset=["aun"])
            long = d.melt(["aun"], list(d.columns[3:]), "label", "value")
            long["value"] = pd.to_numeric(long["value"], errors="coerce")
            long = long.dropna(subset=["value"])
            long["payable_sy"] = payable_sy
            long["sheet_role"] = role
            out.append(long)
    df = pd.concat(out, ignore_index=True)
    df["source_id"] = "pde_subsidies:bef"
    return df[["aun", "payable_sy", "sheet_role", "label", "value", "source_id"]]


def build_bef_enrollment(bef: pd.DataFrame) -> pd.DataFrame:
    """Adjusted ADM and the commission-style current expenditures, by data year, from BEF files.

    Each BEF workbook names the years its inputs come from ("2022-23 adj ADM"); the same
    district-year can appear in several workbooks and the latest file wins."""
    pats = {
        "adj_adm": r"^(\d{4})-(\d{2}) adj ADM$",
        "current_expenditures_net_of_patron_tuition": r"^(\d{4})-(\d{2}) Current Expenditures minus Tuition from Patrons rev$",
        "current_exp_per_weighted_student": r"^(\d{4})-(\d{2}) Current Exp per Weighted Student$",
    }
    parts = []
    for measure, pat in pats.items():
        m = bef["label"].str.extract(pat)
        sel = bef[m[0].notna()].copy()
        sel["sy"] = m.loc[sel.index, 0].astype(int) + 1
        sel["measure"] = measure
        parts.append(sel[["aun", "sy", "measure", "value", "payable_sy"]])
    long = pd.concat(parts, ignore_index=True).sort_values("payable_sy")
    long = long.drop_duplicates(["aun", "sy", "measure"], keep="last")
    wide = long.pivot(index=["aun", "sy"], columns="measure", values="value").reset_index()
    wide["source_id"] = "pde_subsidies:bef"
    return wide


# ---------------------------------------------------------------------------------------------
# Ready to Learn Block Grant (where the enacted adequacy and tax equity supplements are paid)

RTL_COMPONENTS = {
    "total rtlbg": "total",
    "rtlbg-fdn": "foundation",
    "rtlbg-adeqsupp": "adequacy_supplement",
    "rtlbg-taxeqsupp": "tax_equity_supplement",
}


def read_rtl() -> pd.DataFrame:
    """Ready to Learn Block Grant (and earlier PA Accountability / Accountability Block Grant)
    allocations by school district. From 2024-25 the file splits each district's grant into a
    foundation amount and the adequacy and tax equity supplements enacted that year."""
    path = next(BEF_DIR.rglob("rtl-pag*.xlsx"))
    d = pd.ExcelFile(path, engine="calamine").parse(0)
    d.columns = [_clean(c) for c in d.columns]
    d = d.rename(columns={d.columns[0]: "category", "AUN": "aun", "LEA Name": "lea_name"})
    d["aun"] = d["aun"].map(_aun)
    d = d[(d["category"] == 1) & d["aun"].notna()]
    rows = []
    for c in d.columns:
        m = re.match(r"^(\d{4})-(\d{2}) (.+)$", c)
        if not m:
            continue
        what = m.group(3).strip()
        component = RTL_COMPONENTS.get(what.lower(), "total")
        part = d[["aun", c]].rename(columns={c: "value"})
        part["value"] = pd.to_numeric(part["value"], errors="coerce")
        part = part.dropna(subset=["value"])
        part["payable_sy"] = int(m.group(1)) + 1
        part["component"] = component
        part["program"] = "Ready to Learn Block Grant" if "RTLBG" in what.upper() else what
        rows.append(part)
    out = pd.concat(rows, ignore_index=True)
    out["source_id"] = "pde_subsidies:rtl"
    return out[["aun", "payable_sy", "program", "component", "value", "source_id"]]
