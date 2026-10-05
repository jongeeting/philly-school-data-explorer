# Upstream terms that limit what we can publish

Checked 2026-10-04. Not legal advice. Summaries are in our words; read the originals in `raw/` (archived, hashed in `sources/downloads.csv`).

## School District of Philadelphia: Terms of Use of School District Data (Feb 2013)

Applies to every dataset on philasd.org/research and its OpenDataPhilly mirrors (OpenDataPhilly itself lists their license as "Not Specified").

| Section | What it says | What it means for us |
| --- | --- | --- |
| 1 Grant | A personal, non-exclusive, revocable, **non-transferable** license, for **governmental, accountability, and evaluative purposes** | This is not a general open-data license. It is unclear that a public site and redistributed files fit |
| 2 Ownership | District keeps all rights; **copying the data sets or the data in them is prohibited** except as the terms allow | Redistributing district files, or near-copies, is the main risk. Facts are generally not copyrightable, but these terms are a contract on users |
| 4 No endorsement | No district marks or statements implying endorsement | No SDP logo or "approved by" language |
| 6, 7 | District may remove data or change terms at any time without notice | Archive everything; re-check the terms each release |
| 11 FERPA | Use must not violate FERPA, including through successive releases | Reinforces the small-cell rule (suppress groups under 20) and no individual-level data |

Other sections disclaim warranties and put indemnity and sole responsibility on the user.

## U.S. Department of Education: Civil Rights Data Collection

Public-use files with a short usage agreement: make no use of the identity of any person discovered inadvertently (and report it to OCR), and do not link the data with individually identifiable data from other datasets. Our use (school-level aggregates joined to school-level data) is consistent; never join CRDC to any individual-level file.

## What follows

1. **`LICENSE-DATA` (CC BY 4.0) can only cover what is ours.** It cannot relicense district data, and may not be appropriate for tables that are mostly district data. Treat SDP-derived tables as unreleased until the district agrees in writing.
2. **Ask the district.** Contact: `opendata@philasd.org` (listed as maintainer on OpenDataPhilly) and the research office contact. Ask for written confirmation that a public, open-licensed compilation with attribution is permitted, or a short data-sharing agreement. This was already on the list of questions for the district contact.
3. **Until then:** `raw/`, `staging/`, and `core/` stay out of git (already ignored). Release nothing derived from district files. Identifiers and facts that the district publishes openly are the lowest-risk part, but the ask should cover them too.
4. **Other sources need the same check** before release: PDE and Future Ready terms, SEDA's data use agreement, Census (public domain), City data (OpenDataPhilly licenses vary).

## Already published in this repo (to decide)

`prototype/data/` (committed Oct 4, 2026) contains district-derived tables, for example `school_years.csv` (per-year school names, codes, and locations from the master lists) and the catchment GeoJSON. Options: leave as is, remove from the current tree, or remove from history too. Removing from history requires a force-push and a decision from the repo owner.
