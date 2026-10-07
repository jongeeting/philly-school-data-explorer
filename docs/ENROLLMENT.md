# Enrollment and catchment flows

Built by `uv run psd build-enrollment` into `core/`. Measures are defined in [registry/measures.csv](../registry/measures.csv) (published as `core/measure`); the build fails if a measure is used without a definition.

| Table | Grain | Years |
| --- | --- | --- |
| `enrollment` | school x sy x grade (K, 01-12, ALL) x student group | 2009-10 to 2025-26 (October 1 counts) |
| `catchment_flow` | sy x catchment school (where students live) x enrolled school | 2016-17 to 2025-26 |
| `school_metric` | school x sy x measure | CEP rate 2014-15 on; capacity and catchment figures 2016-17 on |
| `school_placeholder` | school code outside the district's school lists | 50 codes |

## What to know

- **Coverage break at 2014-15.** 2009-10 to 2013-14 files cover district schools only (156,361 students in 2009-10, 131,894 in 2013-14). From 2014-15 the files include charter and alternative schools (197,694 in 2014-15, 181,340 in 2025-26). Label this break on any trend.
- **2009-10 to 2013-14 workbooks** have one sheet per group, two header rows, SRC school IDs, and whole rows suppressed when a grade has 20 or fewer students. Economically disadvantaged counts exist only for 2012-13 and 2013-14.
- **2010-11 race counts are withheld.** The source reports zero Black, Hispanic, American Indian, and multiracial students in every school; `corrections/enrollment.csv` withholds them with status `invalid_in_source`.
- **Grade ALL is a school total.** It equals the sum of grade rows in every year; never add the two.
- **Status beside every value.** `reported`, `suppressed` (the district's `.` or "Data is Private"), or `not_reported` (blank in the source).
- **Placeholders keep flows whole.** About 11,500 Philadelphia students a year enroll in cyber charters or charters outside the city; they and short-lived programs and non-public special education placements get placeholder `school_id`s (`school_placeholder.kind`).
- **Catchment not available.** About 6,000 students a year have an address the district could not place; their flows carry `catchment_status = not_available`, never a blank school.
- **SRC IDs** key 2009-10 to 2013-14 and 2019-20. They are translated to ULCS through the identity crosswalk, falling back to other years when a year's list omits a program and the SRC ID has only ever meant one school. One program (Ombudsman South Transition, 2010-12) has no ULCS; see `core/enrollment_issues.csv`.

## A first finding

The share of students attending their own catchment school fell from about 47% in 2016-17 to about 38% from 2021-22 on (sum of catchment students attending divided by sum of catchment sizes; the flow table gives the same answer). The denominator is students who live in catchments, not school enrollment.


## Neighborhood rollup (derived)

`uv run psd neighborhood-flows` writes `derived/neighborhood_flow` (neighborhood x enrolled school x year) and `derived/neighborhood_metric` (neighborhood x year x measure: resident students, share attending their catchment school, and students by sector of the school they attend). Method `catchment_flow_to_neighborhood_v1`:

- Each catchment's students are spread over neighborhoods by where the catchment's 2020 population lives (census-block crosswalk), rescaled so every student is counted once.
- The district's flow file does not say whether a student counts toward a school's elementary, middle, or high catchment; K-8 schools are weighted 6/9 elementary and 3/9 middle, 6-12 schools 4/7 high and 3/7 middle.
- Students with unplaced addresses, or whose catchment school has no boundary that year, are reported citywide, never dropped. Allocated plus unplaced equals the district's total in every year (checked on every build).
- Estimates under 20 students are suppressed, and so is any percentage whose numerator is suppressed. Most neighborhood-to-school pairs are suppressed; neighborhood totals mostly are not.
- Early years undercount: 15,735 (2016-17) and 27,911 (2017-18) students have addresses the district could not place, against about 2,000 a year recently.

Neighborhoods are for display only. In 2025-26, Northeast neighborhoods such as Somerton and Bustleton have about 64% of public school students in their catchment school; parts of West, Southwest, and Northwest Philadelphia (Germantown-Morton, Carroll Park, Haddington) are at 14% to 20%. Describe these as family choices and seat availability together, not as school quality.

## State demographics (School Fast Facts)

`uv run psd build-fast-facts` loads PDE's School Fast Facts (2017-18 to 2024-25, district and charter schools on one state definition):

- `school_metric` part `fast_facts`: `state_enrollment` and `state_pct_of_enrollment` by student group (economically disadvantaged, English learner, special education, gifted, homeless, foster care, military-connected, female, male, and race and ethnicity groups).
- `school_state_attr` (school x year): Title I, ESSA school designation (as coded by PDE; CSI, TSI, ATSI, ACSI, DFLT), grades offered, career and technical programs.
- State enrollment matches the district's October 1 counts closely (r = 0.999, median difference 0.4% per school).
- Use the state's economically disadvantaged share only with other state measures; the district's CEP rate is a different method. Its rise from a median of 69.5% to 84.9% (2017-18 to 2024-25) is unexplained so far (see DATA_GAPS.md).

## Observed enrollment change around the 2013 closures

`school_closure_flow` and `school_closure_flow_summary` (`psd build-closure-flows`) show what happened at schools near the 23 schools closed after 2012-13 (`registry/closures_2013_final.csv`, from press reports of the March 7, 2013 vote). For each closed school with a neighborhood catchment, the table lists the 2013-14 catchments that cover its 2012-13 catchment (census-block population weights, same school level, at least 5% of the closed catchment's population), each receiving school's enrollment in 2012-13 and 2013-14, and the change beyond the district-wide change at schools that overlap no closure (+1.1%). A school that overlaps several closed catchments has its gain split among them by shared population, so no gain is counted twice (`gain_allocated`).

What this does not show: where individual students went. Totals cannot separate students from the closed school from those who arrived for other reasons, charter shifts, or grade changes, and enrollment by residence is not available before 2016-17 (GAP-031). The share of closed enrollment that reappears in neighboring schools runs from 0 to about 1.3; values at or above 1 (Reynolds, Pratt) mean the nearby schools gained at least as many students as the closed school had, so some gains came from elsewhere. Eighteen of the 23 are covered; five admission-based schools have no neighborhood catchment (GAP-080). The `named_in_2012_proposal` flag marks overlaps that were also in the December 2012 proposal (`school_closure_plan`). Treat the table as evidence to read with the closure plan and local reporting, not as lineage.

