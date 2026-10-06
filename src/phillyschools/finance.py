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
    out = t["finance_lea"][["aun", "lea_name", "county", "lea_type"]].merge(
        wide, on="aun", how="right"
    )
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
    a = build_adequacy(t)
    a.to_parquet(CORE / "adequacy_target.parquet", index=False)
    a.to_csv(CORE / "adequacy_target.csv", index=False)
    return a
