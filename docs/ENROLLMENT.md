# Enrollment and catchment flows

Built by `uv run psd build-enrollment` into `core/`. Measures are defined in [registry/measures.csv](../registry/measures.csv) (published as `core/measure`); the build fails if a measure is used without a definition.

| Table | Grain | Years |
| --- | --- | --- |
| `enrollment` | school x sy x grade (K, 01-12, ALL) x student group | 2014-15 to 2025-26 (October 1 counts) |
| `catchment_flow` | sy x catchment school (where students live) x enrolled school | 2016-17 to 2025-26 |
| `school_metric` | school x sy x measure | CEP rate 2014-15 on; capacity and catchment figures 2016-17 on |
| `school_placeholder` | school code outside the district's school lists | 50 codes |

## What to know

- **Sector-complete from 2014-15.** The reposted 2014-15 to 2018-19 files include district, charter, and alternative schools. Totals: 197,185 students in 2014-15, 181,340 in 2025-26.
- **Grade ALL is a school total.** It equals the sum of grade rows in every year; never add the two.
- **Status beside every value.** `reported`, `suppressed` (the district's `.` or "Data is Private"), or `not_reported` (blank in the source).
- **Placeholders keep flows whole.** About 11,500 Philadelphia students a year enroll in cyber charters or charters outside the city; they and short-lived programs and non-public special education placements get placeholder `school_id`s (`school_placeholder.kind`).
- **Catchment not available.** About 6,000 students a year have an address the district could not place; their flows carry `catchment_status = not_available`, never a blank school.
- **2019-20 enrollment is keyed by SRC ID,** translated to ULCS through the identity crosswalk. One program (Camelot Academy) could not be translated; see `core/enrollment_issues.csv`.

## A first finding

The share of students attending their own catchment school fell from about 47% in 2016-17 to about 38% from 2021-22 on (sum of catchment students attending divided by sum of catchment sizes; the flow table gives the same answer). The denominator is students who live in catchments, not school enrollment.

## Not yet loaded

Enrollment for 2009-10 to 2013-14 (Excel workbooks with a different layout, one sheet per student group).
