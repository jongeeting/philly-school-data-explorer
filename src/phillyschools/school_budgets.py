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
AMOUNT = re.compile(r"^(?P<label>.+?)\s{2,}(?P<amt>\(?-?[\d,]+\)?)\s*$")
HEADER = re.compile(r"^\s*(\d{4})-(\d{4}) School Budget Allotment Detail")
SCOPE = re.compile(r"^(School Managed|Centrally Managed) Allotments\s*$")
SUBTOTAL = re.compile(r"^(School Managed|Centrally Managed) Allotments Sub-total:\s+(-?[\d,]+)")
SCHOOL_TOTAL = re.compile(
    r"^(?P<name>.+\((?P<code>[^)]+)\))(?: Total:)?\s+(?P<amt>\(?-?[\d,]+\)?)\s*$"
)
NOISE = re.compile(
    r"School District of Philadelphia|www\.philasd\.org|Page \d+ of \d+|FY\d\d School Budgets"
)


def _fnum(text: str) -> float:
    text = text.strip()
    value = float(text.strip("()-"))
    return -value if text.startswith(("(", "-")) else value


def header_code(text: str) -> str | None:
    """The school code printed under the report title, e.g. 1010 from 'Bartram, John High School (1010)'."""
    for line in text.splitlines()[:8]:
        m = re.match(r"^\s*.+\((\w+)\)\s*$", line)
        if m:
            return m.group(1)
    return None


def _num(text: str) -> int:
    """An amount as printed: commas, and parentheses for a negative."""
    text = text.strip()
    negative = text.startswith("(") or text.startswith("-")
    value = int(text.strip("()-").replace(",", ""))
    return -value if negative else value


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
    res = parse_budget_text(text)
    res["code"] = header_code(text)
    return res


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
        mismatch = bool(res["code"]) and res["code"] != ulcs
        if mismatch:  # the tool answered with a different school's report
            rows = []
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
                "printed_code": res["code"],
                "wrong_school": mismatch,
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


# ---------------------------------------------------------------------------------------------
# Summary of School Purchases (what the allotments buy) and Position Summary (positions by fund)

FUNDING = r"(?:School|Centrally) Managed Allotment"
PURCHASE_SECTIONS = {
    "Budget Allotments": "budget_allotment",
    "School Based Positions": "position",
    "Discretionary Spending": "discretionary",
}
P_ALLOT = re.compile(
    r"^(?P<item>School Managed Allotments|Centrally Managed Allotments|Total)\s+(?P<amt>\(?-?[\d,]+\)?)$"
)
P_POS = re.compile(
    rf"^(?P<item>.+?)\s+(?P<fund>{FUNDING})\s+(?P<count>\(?-?[\d.]+\)?)\s+(?P<amt>\(?-?[\d,]+\)?)$"
)
P_POS_TOTAL = re.compile(r"^Total\s+(?P<count>\(?-?[\d.]+\)?)\s+(?P<amt>\(?-?[\d,]+\)?)$")
P_DISC = re.compile(rf"^(?P<item>.+?)\s+(?P<fund>{FUNDING})\s+(?P<amt>\(?-?[\d,]+\)?)$")
P_DISC_TOTAL = re.compile(r"^Total\s+(?P<amt>\(?-?[\d,]+\)?)$")
HEADER_ROWS = re.compile(r"^(Funding Type|Position\s+Funding Type|Expenditure Area\s+Funding Type)")


def parse_purchase_text(text: str) -> dict:
    """{sy, rows} from a Summary of School Purchases report."""
    if "No data available" in text:
        return {"sy": None, "rows": []}
    sy, section, rows = None, None, []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^(\d{4})-(\d{4}) Summary of School Purchases", line)
        if m:
            sy = int(m.group(2))
            continue
        if NOISE.search(line) or re.match(r"^[A-Z][a-z]{2} \d{1,2} \d{4}", line):
            continue
        if line in PURCHASE_SECTIONS:
            section = PURCHASE_SECTIONS[line]
            continue
        if HEADER_ROWS.match(line) or re.search(r"\(\d+\)$", line):
            continue
        if line == "Total":  # a section with nothing in it
            continue
        rec = None
        if section == "budget_allotment" and (m := P_ALLOT.match(line)):
            kind = "total" if m["item"] == "Total" else "item"
            rec = (kind, m["item"], None, None, _num(m["amt"]))
        elif section == "position":
            if m := P_POS_TOTAL.match(line):
                rec = ("total", "Total", None, _fnum(m["count"]), _num(m["amt"]))
            elif m := P_POS.match(line):
                rec = ("item", m["item"].strip(), m["fund"], _fnum(m["count"]), _num(m["amt"]))
        elif section == "discretionary":
            if m := P_DISC_TOTAL.match(line):
                rec = ("total", "Total", None, None, _num(m["amt"]))
            elif m := P_DISC.match(line):
                rec = ("item", m["item"].strip(), m["fund"], None, _num(m["amt"]))
        if rec is None:
            rows.append({"section": "unparsed", "line_type": "unparsed", "item": line})
            continue
        rows.append(
            {
                "section": section,
                "line_type": rec[0],
                "item": rec[1],
                "funding_type": rec[2],
                "count": rec[3],
                "amount": rec[4],
            }
        )
    return {"sy": sy, "rows": rows}


POS_ROW = re.compile(
    r"^(?P<pidn>[A-Z0-9]{5,8})\s+(?P<mid>.+?)\s+(?P<prev>-?\d+\.\d{2})\s+(?P<curr>-?\d+\.\d{2})\s*$"
)


def parse_positions_text(text: str) -> dict:
    """{sy, rows} from a Position Summary report: one row per position line, with FTE in the
    previous and current budget; wrapped Subject/Skill lines are joined to their row."""
    sy, rows = None, []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        m = re.match(r"^\s*(\d{4})-(\d{4}) Position Summary", line)
        if m:
            sy = int(m.group(2))
            continue
        s = line.strip()
        if NOISE.search(s) or re.match(r"^[A-Z][a-z]{2} \d{1,2} \d{4}", s) or s.startswith("PIDN"):
            continue
        if re.search(r"\(\d+\)$", s):
            continue
        m = POS_ROW.match(s)
        if m:
            parts = re.split(r"\s{2,}", m["mid"].strip())
            rows.append(
                {
                    "pidn": m["pidn"],
                    "parts": parts,
                    "fte_prev": float(m["prev"]),
                    "fte_curr": float(m["curr"]),
                }
            )
        elif rows and rows[-1].get("parts") and raw_line.startswith(" " * 10):
            rows[-1]["parts"][-3 if len(rows[-1]["parts"]) >= 4 else 1] += " " + s
        else:
            rows.append({"pidn": None, "unparsed": s})
    return {"sy": sy, "rows": rows}


def position_vocab(rows: list[dict], allotment_groups=()) -> tuple[list[str], list[str]]:
    """Funding and activity names seen in cleanly split rows (plus the allotment group names)."""
    good = [r["parts"] for r in rows if r.get("parts") and len(r["parts"]) == 4]
    fundings = {p[2] for p in good} | set(allotment_groups)
    activities = {p[3] for p in good}
    return sorted(fundings, key=len, reverse=True), sorted(activities, key=len, reverse=True)


def split_position_parts(rows: list[dict], vocab: tuple[list[str], list[str]]) -> list[dict]:
    """Assign position, subject, funding and activity from column splits, repairing rows where
    a long Subject/Skill ran into the Funding column using the names seen elsewhere."""
    fundings, activities = vocab
    out = []
    for r in rows:
        if not r.get("parts"):
            out.append({**r, "position_name": None, "note": "unparsed"})
            continue
        parts = r["parts"]
        note = None
        if len(parts) == 4:
            pos, subj, fund, act = parts
        else:
            pos, tail = parts[0], " ".join(parts[1:])
            found = None
            for f in fundings:
                i = tail.find(f)
                if i < 0:
                    continue
                before, after = tail[:i].strip(), tail[i + len(f) :].strip()
                for a in activities:
                    if after == a:
                        found = (before, f, a)
                    elif after.endswith(" " + a):
                        found = ((before + " " + after[: -len(a)]).strip(), f, a)
                    if found:
                        break
                if found:
                    break
            if found:
                subj, fund, act = found
                note = "repaired"
            else:
                subj, fund, act, note = tail, None, None, "unsplit"
        out.append(
            {
                "pidn": r["pidn"],
                "position_name": pos,
                "subject_skill": subj,
                "funding": fund,
                "activity": act,
                "fte_prev": r["fte_prev"],
                "fte_curr": r["fte_curr"],
                "note": note,
            }
        )
    return out


def _read_text(path) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True
    ).stdout


def _school_ids() -> dict:
    xwalk = pd.read_parquet(CORE / "school_id_xwalk.parquet")
    xwalk = xwalk[xwalk["id_type"] == "ulcs"]
    return dict(zip(xwalk["id_value"].astype(str), xwalk["school_id"], strict=True))


def build_school_purchases() -> pd.DataFrame:
    """Summary of School Purchases lines: allotment totals, positions bought, discretionary spending."""
    ids = _school_ids()
    parts = []
    for path in sorted(BUDGET_DIR.glob("FY*/*_purchases.pdf")):
        ulcs, fy = path.name.split("_")[0], int(path.parent.name[2:])
        text = _read_text(path)
        res = parse_purchase_text(text)
        if not res["rows"] or header_code(text) not in (None, ulcs):
            continue
        df = pd.DataFrame(res["rows"])
        df.insert(0, "sy", 2000 + fy)
        df.insert(0, "ulcs", ulcs)
        parts.append(df)
    sp = pd.concat(parts, ignore_index=True)
    for col in ("funding_type", "count", "amount"):
        if col not in sp:
            sp[col] = None
    sp.insert(0, "school_id", sp["ulcs"].map(ids))
    sp["status"] = "reported"
    sp["source_id"] = SOURCE_ID
    return sp


def build_school_positions() -> pd.DataFrame:
    """Position Summary lines: one row per position line with FTE in the previous and current budget."""
    ids = _school_ids()
    groups = []
    if (CORE / "school_budget.parquet").exists():
        groups = (
            pd.read_parquet(CORE / "school_budget.parquet")["allotment_group"].dropna().unique()
        )
    raw, meta = [], []
    for path in sorted(BUDGET_DIR.glob("FY*/*_positions.pdf")):
        ulcs, fy = path.name.split("_")[0], int(path.parent.name[2:])
        text = _read_text(path)
        res = parse_positions_text(text)
        if header_code(text) not in (None, ulcs):
            continue
        for r in res["rows"]:
            if r.get("pidn"):
                raw.append(r)
                meta.append((ulcs, 2000 + fy))
    vocab = position_vocab(raw, groups)
    df = pd.DataFrame(split_position_parts(raw, vocab))
    df.insert(0, "sy", [m[1] for m in meta])
    df.insert(0, "ulcs", [m[0] for m in meta])
    df.insert(0, "school_id", df["ulcs"].map(ids))
    df["status"] = "reported"
    df["source_id"] = SOURCE_ID
    return df.rename(columns={"note": "parse_note"})


def write_school_purchases_positions() -> tuple[pd.DataFrame, pd.DataFrame]:
    purchases, positions = build_school_purchases(), build_school_positions()
    for name, df in (("school_budget_purchase", purchases), ("school_budget_position", positions)):
        df.to_parquet(CORE / f"{name}.parquet", index=False)
        df.to_csv(CORE / f"{name}.csv", index=False)
    return purchases, positions
