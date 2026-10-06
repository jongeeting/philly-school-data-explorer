"""School budget allotments: parse the district's per-school budget PDFs into one long table.

Each PDF (one school, one fiscal year) lists allotments in two scopes (school managed, centrally
managed), each with groups of line items, group totals, a scope subtotal, and a school total.
These are budgets set in spring or summer, not actual spending.
"""

import re
import subprocess

import pandas as pd

from . import CORE, RAW

BUDGET_DIR = RAW / "sdp_school_budgets"
SOURCE_ID = "sdp_school_budgets"
AMOUNT = re.compile(r"^(?P<label>.+?)\s{2,}\(?(?P<amt>-?[\d,]+)\)?\s*$")
HEADER = re.compile(r"^\s*(\d{4})-(\d{4}) School Budget Allotment Detail")
SCOPE = re.compile(r"^(School Managed|Centrally Managed) Allotments\s*$")
SUBTOTAL = re.compile(r"^(School Managed|Centrally Managed) Allotments Sub-total:\s+(-?[\d,]+)")
SCHOOL_TOTAL = re.compile(r"^(?P<name>.+\((?P<code>[^)]+)\))(?: Total:)?\s+(?P<amt>-?[\d,]+)\s*$")
NOISE = re.compile(
    r"School District of Philadelphia|www\.philasd\.org|Page \d+ of \d+|FY\d\d School Budgets"
)


def _num(text: str) -> int:
    return int(text.replace(",", ""))


def parse_budget_text(text: str) -> dict:
    """{sy, name, rows} from one report's text; rows are dicts without school identifiers."""
    rows, scope, group, sy, name = [], None, None, None, None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = HEADER.match(raw_line)
        if m:
            sy = int(m.group(2))
            continue
        if NOISE.search(line) or re.match(r"^[A-Z][a-z]{2} \d{1,2} \d{4}", line):
            continue
        m = SCHOOL_TOTAL.match(line)
        if m:
            name = m.group("name")
            rows.append(("school_total", None, None, None, _num(m.group("amt"))))
            continue
        m = SUBTOTAL.match(line)
        if m:
            rows.append(("scope_subtotal", m.group(1), None, None, _num(m.group(2))))
            continue
        m = SCOPE.match(line)
        if m:
            scope, group = m.group(1), None
            continue
        m = AMOUNT.match(line)
        if m and rows and rows[-1][0] == "scope_subtotal" and rows[-1][1] == "Centrally Managed":
            name = m.group("label").strip()  # a school total printed without its code
            rows.append(("school_total", None, None, None, _num(m.group("amt"))))
            continue
        if m and scope:
            label = m.group("label").strip()
            if label.endswith(" Total"):
                rows.append(
                    ("group_total", scope, label[: -len(" Total")], None, _num(m.group("amt")))
                )
                group = None
            elif group:
                rows.append(("item", scope, group, label, _num(m.group("amt"))))
            else:
                rows.append(("item", scope, label, label, _num(m.group("amt"))))
        elif scope and not m:
            group = line
    if name is None and sy is None:
        return {"sy": sy, "name": name, "rows": []}
    out = []
    for kind, scope, grp, item, amt in rows:
        out.append(
            {"line_type": kind, "scope": scope, "allotment_group": grp, "line": item, "amount": amt}
        )
    return {"sy": sy, "name": name, "rows": out}


def read_budget_pdf(path) -> dict:
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True
    ).stdout
    return parse_budget_text(text)


def build_school_budget() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(school_budget rows, report log with one row per PDF and any problem)."""
    xwalk = pd.read_parquet(CORE / "school_id_xwalk.parquet")
    xwalk = xwalk[xwalk["id_type"] == "ulcs"]
    ids = dict(zip(xwalk["id_value"].astype(str), xwalk["school_id"], strict=True))
    parts, log = [], []
    for path in sorted(BUDGET_DIR.glob("FY*/*_allotment.pdf")):
        ulcs = path.name.split("_")[0]
        fy = int(path.parent.name[2:])
        res = read_budget_pdf(path)
        rows = res["rows"]
        total = next((r["amount"] for r in rows if r["line_type"] == "school_total"), None)
        items = sum(r["amount"] for r in rows if r["line_type"] == "item")
        log.append(
            {
                "ulcs": ulcs,
                "sy": 2000 + fy,
                "pdf_sy": res["sy"],
                "n_rows": len(rows),
                "school_total": total,
                "items_sum": items,
                "has_budget": total is not None,
            }
        )
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df.insert(0, "sy", 2000 + fy)
        df.insert(0, "ulcs", ulcs)
        parts.append(df)
    sb = pd.concat(parts, ignore_index=True)
    sb.insert(0, "school_id", sb["ulcs"].map(ids))
    sb["status"] = "reported"
    sb["source_id"] = SOURCE_ID
    return sb, pd.DataFrame(log)


def write_school_budget() -> tuple[pd.DataFrame, pd.DataFrame]:
    sb, log = build_school_budget()
    for name, df in (("school_budget", sb), ("school_budget_report", log)):
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    return sb, log
