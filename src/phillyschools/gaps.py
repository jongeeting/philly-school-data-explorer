"""Data gaps: sources/gaps.csv is the single source of truth; docs/DATA_GAPS.md is generated."""

import csv

from . import ROOT, SOURCES

GAPS_CSV = SOURCES / "gaps.csv"
GAPS_MD = ROOT / "docs" / "DATA_GAPS.md"
QUESTIONS_MD = ROOT / "docs" / "DISTRICT_QUESTIONS.md"
OPEN_QUESTIONS_CSV = SOURCES / "open_questions.csv"
OPEN_QUESTIONS_MD = ROOT / "docs" / "OPEN_QUESTIONS.md"
OWNERS = {"us", "district", "state", "other", "owner decision"}
AREA_ORDER = ["identity", "geography", "measures", "operations", "finance", "workforce", "legal"]
AREA_TITLES = {
    "identity": "Schools and identity",
    "geography": "Geography",
    "measures": "Measures and facts",
    "operations": "District operations and buildings",
    "finance": "School finance",
    "workforce": "Workforce",
    "legal": "Legal and licensing",
}
KINDS = {
    "not-in-any-list": "no source we know of records it",
    "not-collected-by-district": "the publisher does not collect or publish it, or changed it",
    "not-public": "exists or likely exists, but is not public",
    "not-yet-ingested": "public, but we have not captured or loaded it yet",
    "invalid-in-source": "published, but the published values look wrong or incomplete",
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
        (
            "Owner: who can close it (`us`, `district`, `state`, `other`, or `owner decision`). "
            "Open questions for the district are collected in "
            "[DISTRICT_QUESTIONS.md](DISTRICT_QUESTIONS.md)."
        ),
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
            "| ID | Gap | Kind | Priority | Status | Owner | How to close |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for g in group:
            note = f" *({g['notes']})*" if g["notes"] else ""
            lines.append(
                f"| {g['gap_id']} | {g['gap']}{note} | `{g['kind']}` | {g['priority']} | "
                f"{g['status']} | {g.get('who_can_close', '')} | {g['how_to_close']} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_questions(gaps: list[dict]) -> str:
    """The open questions only the district can answer, in priority order, for handoff."""
    open_q = sorted(
        (
            g
            for g in gaps
            if g["status"] != "closed"
            and g.get("district_question")
            and g.get("who_can_close") == "district"
        ),
        key=lambda g: (PRIORITY_RANK[g["priority"]], g["gap_id"]),
    )
    lines = [
        "# Questions for the School District",
        "",
        (
            "Open data gaps that someone at the district could close. Generated from "
            "[sources/gaps.csv](../sources/gaps.csv) (`district_question`); full entries are in "
            "[DATA_GAPS.md](DATA_GAPS.md)."
        ),
        "",
    ]
    for i, g in enumerate(open_q, start=1):
        lines.append(f"{i}. **{g['district_question']}** ({g['gap_id']}, {g['priority']} priority)")
        lines.append(f"   - Context: {g['gap']}")
    lines.append("")
    return "\n".join(lines)


def read_open_questions() -> list[dict]:
    with open(OPEN_QUESTIONS_CSV, newline="") as f:
        return list(csv.DictReader(f))


def render_open_questions(questions: list[dict]) -> str:
    lines = [
        "# Open questions for journalists and researchers",
        "",
        (
            "Questions this data cannot answer yet, with what we have and how someone could "
            "pursue them. Generated from [sources/open_questions.csv](../sources/open_questions.csv); "
            "the questions only the district can answer are in "
            "[DISTRICT_QUESTIONS.md](DISTRICT_QUESTIONS.md), and every gap is in "
            "[DATA_GAPS.md](DATA_GAPS.md). Tell us if you find an answer, and we will add it "
            "with the source."
        ),
        "",
    ]
    for q in questions:
        lines += [
            f"## {q['question_id']}. {q['question']}",
            "",
            f"*Who might pursue it:* {q['audience']}",
            "",
            f"- **Why it matters:** {q['why_it_matters']}",
            f"- **What we have:** {q['what_we_have']}",
            f"- **How to pursue it:** {q['how_to_pursue']}",
            f"- **Related gaps:** {q['related_gaps']}",
            "",
        ]
    return "\n".join(lines)


def write_markdown() -> str:
    gaps = read_gaps()
    text = render_markdown(gaps)
    GAPS_MD.write_text(text)
    QUESTIONS_MD.write_text(render_questions(gaps))
    OPEN_QUESTIONS_MD.write_text(render_open_questions(read_open_questions()))
    return text
