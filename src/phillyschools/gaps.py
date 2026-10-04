"""Data gaps: sources/gaps.csv is the single source of truth; docs/DATA_GAPS.md is generated."""

import csv

from . import ROOT, SOURCES

GAPS_CSV = SOURCES / "gaps.csv"
GAPS_MD = ROOT / "docs" / "DATA_GAPS.md"
AREA_ORDER = ["identity", "geography", "measures", "operations", "workforce", "legal"]
AREA_TITLES = {
    "identity": "Schools and identity",
    "geography": "Geography",
    "measures": "Measures and facts",
    "operations": "District operations and buildings",
    "workforce": "Workforce",
    "legal": "Legal and licensing",
}
KINDS = {
    "not-in-any-list": "no source we know of records it",
    "not-collected-by-district": "the publisher does not collect or publish it, or changed it",
    "not-public": "exists or likely exists, but is not public",
    "not-yet-ingested": "public, but we have not captured or loaded it yet",
    "legal": "terms or permission issue",
    "decision": "needs a project decision",
    "unknown": "we do not know yet",
}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def read_gaps() -> list[dict]:
    with open(GAPS_CSV, newline="") as f:
        return list(csv.DictReader(f))


def render_markdown(gaps: list[dict]) -> str:
    open_gaps = [g for g in gaps if g["status"] != "closed"]
    lines = [
        "# Data gaps",
        "",
        (
            "What is missing, why, and how we plan to close it. Generated from "
            "[sources/gaps.csv](../sources/gaps.csv); edit the CSV, then run `uv run psd gaps`."
        ),
        "",
        (
            f"**{len(open_gaps)} unresolved** of {len(gaps)} tracked "
            f"({sum(g['priority'] == 'high' for g in open_gaps)} high priority)."
        ),
        "",
        "**Kinds of gap**",
        "",
    ]
    lines += [f"- `{k}`: {v}" for k, v in KINDS.items()]
    lines += [
        "",
        "Statuses: `open`, `in-progress`, `blocked`, `closed`. Closed gaps stay in the CSV with a note.",
        "",
    ]
    for area in AREA_ORDER:
        group = sorted(
            (g for g in gaps if g["area"] == area),
            key=lambda g: (PRIORITY_RANK[g["priority"]], g["gap_id"]),
        )
        if not group:
            continue
        lines += [
            f"## {AREA_TITLES[area]}",
            "",
            "| ID | Gap | Kind | Priority | Status | How to close |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for g in group:
            note = f" *({g['notes']})*" if g["notes"] else ""
            lines.append(
                f"| {g['gap_id']} | {g['gap']}{note} | `{g['kind']}` | {g['priority']} | "
                f"{g['status']} | {g['how_to_close']} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_markdown() -> str:
    text = render_markdown(read_gaps())
    GAPS_MD.write_text(text)
    return text
