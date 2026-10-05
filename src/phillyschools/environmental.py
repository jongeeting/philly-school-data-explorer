"""Pick the most recent environmental report per school from the cataloged Drive files.

The district's environmental Drive (source `sdp_environmental`) holds about 7,400 files. The
current-state set, one per school and report type, is much smaller:

  ahera   per building code (the 4-digit prefix; annexes such as 7301 are separate buildings):
          the management plan ("16 <code> ..."), the latest 6-month periodic surveillance
          report, the latest 3-year reinspection, and the latest plaster status letter
  water   current lead-in-water results for each site (files outside Archive folders)
  lead    the lead-safe assessment and certification files for each school (undated, one set)

Project records (bulk sampling, abatement, water projects) are not school-level reports and are
left out; they stay in the catalog for a later download.
"""

import re

from .discover import read_files_catalog

SOURCE = "sdp_environmental"
AHERA_KINDS = {
    "plaster-letter": r"plaster status",
    "6-month": r"6\s*-?\s*month",
    "3-year": r"3[\s_-]*year|three year|\d{4}[\s_-]\d{4}_AHERA_(report|inspection)",
}
CODE = re.compile(r"\D{0,3}(\d{4})(?!\d)")
PLAN = re.compile(r"16 (\d{4})(?!\d)")


def report_date(name: str) -> tuple[int, int] | None:
    """(year, month) from names like 7300-Hopkinson_11-2025_6-Month or ..._2018_2019_3_Year."""
    code = CODE.match(name)
    rest = name[code.end() :] if code else name  # a building code like 2050 is not a year
    m = re.search(r"(?<!\d)(\d{1,2})-(20\d\d)(?!\d\d)", rest)
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(2)), int(m.group(1))
    years = [int(y) for y in re.findall(r"(?<!\d)(20\d\d)", rest)]
    return (max(years), 0) if years else None


def ahera_key(name: str) -> tuple[str, str] | None:
    code = CODE.match(name)
    if not code:
        return None
    for kind, pattern in AHERA_KINDS.items():
        if re.search(pattern, name, re.IGNORECASE):
            return code.group(1), kind
    return None


def select_latest(rows: list[dict]) -> list[dict]:
    out, latest = [], {}
    for r in rows:
        if r["source_key"] != SOURCE:
            continue
        sub = r.get("subdir") or ""
        current_water = sub.startswith("water/") and not re.search(r"Archives?$", sub)
        if sub.startswith("lead/") or current_water:
            out.append(r)
        elif sub.startswith("ahera/") and sub.endswith("AHERA Management Plan Archive"):
            plan = PLAN.match(r["filename"])
            if plan:
                key, when = (plan.group(1), "plan"), (0, 0)
            else:
                key, when = ahera_key(r["filename"]), report_date(r["filename"])
            if key and when and (key not in latest or when > latest[key][0]):
                latest[key] = (when, r)
    return out + [r for _, r in latest.values()]


def latest_environmental() -> list[dict]:
    return select_latest(read_files_catalog())
