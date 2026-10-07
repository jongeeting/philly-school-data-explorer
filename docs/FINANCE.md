# School finance

`uv run psd catalog-afr`, `uv run psd fetch --source pde_afr befc_report`, then `uv run psd build-finance` builds the finance tables from the Pennsylvania Department of Education's Annual Financial Report (AFR) files and the Basic Education Funding Commission's 2024 report. All dollars are nominal (not adjusted for inflation), by fiscal year; `sy` is the spring year (2024 = FY 2023-24, July to June).

## Tables

- `finance_lea`: 779 agencies: 500 school districts, 209 charter schools, 68 career and technology centers, and 2 others. Each charter school is its own agency; Philadelphia's district is "Philadelphia City SD" (AUN 126515001).
- `finance_lea_line` (1.07 million rows): each agency's reported revenue (local, state, federal, other) and expenditure (by function, by object, and support-service detail) by state account code, 2015-16 to 2024-25 (2014-15 for "other revenue" and objects). `finance_account` is the dictionary of the 458 account codes with a level (1 = broadest). **Accounts are hierarchical and the groups overlap** (a function total contains its detail lines, and the support-service detail repeats part of function 2000): never add across levels or groups. A blank means no amount reported, which is not necessarily zero.
- `finance_lea_tuition`: what each school district paid in tuition, by recipient: other districts, brick-and-mortar and cyber charter schools (regular and special education separately), career centers, private schools.
- `finance_lea_instruction`: actual instruction expense by school district, **2008-09 to 2023-24**, the state's measure used in charter tuition rates.
- `finance_lea_fund_balance`: general fund balance (committed, assigned, unassigned).
- `adequacy_befc_2024`: the Basic Education Funding Commission's per-district calculation (Appendix B of its January 11, 2024 report): each district's state share of the adequacy gap, tax equity supplement, 2023-24 funding base, and the recommended 2024-25 increases.
- `marts/district_finance` (11,215 rows): one row per agency and year with the headline lines wide: spending by function, revenue by source, Basic Education Funding, charter tuition paid, instruction expense, fund balance, adjusted ADM, spending per adjusted ADM, and the Ready to Learn allocations. `marts/adequacy_compare`: the three studies and the enacted supplements side by side.

## What the adequacy numbers are (and are not)

Adequacy studies in Pennsylvania disagree because they define "adequate" differently. This release holds all three, from the primary documents, each in its own table and side by side in `marts/adequacy_compare` (every study keeps its own columns and units):

| Study | Who | Method | Statewide | Philadelphia |
| --- | --- | --- | --- | --- |
| 2007 Costing-Out Study (`adequacy_apa_2007`) | Augenblick, Palaich and Associates, for the State Board of Education | What it costs for every student to reach state proficiency standards by 2014, built from professional-judgment panels and evidence-based analysis; 2005-06 dollars | $21.63 billion needed against $17.25 billion spent: a $4.38 billion gap ($4.57 billion if districts already above the estimate keep spending); 471 of 501 districts below | $9,947 spent per pupil against a $14,131 estimate: $4,184 per pupil, about $870 million (207,893 students) |
| 2023 analysis (`adequacy_kelly_2023`) | Matthew Kelly, Penn State, for the lawsuit plaintiffs (testimony to the commission) | Spending per weighted student of 74 districts meeting graduation and test benchmarks, outliers removed, times each district's weighted students; 2021-22 spending | $6.26 billion shortfall; 412 of 500 districts below | $1.57 billion shortfall ($7,926 per weighted student; 383,792 weighted students) |
| 2024 final report (`adequacy_befc_2024`) | The bipartisan Basic Education Funding Commission | Median current spending per weighted student of districts meeting state standards ($13,704) times each district's weighted students; target year 2021-22 | $5.4 billion total gap, of which $5.14 billion is the state's share; 387 of 500 districts below | State share $1.42 billion (27.6% of the statewide state share); 7-year target equal to 37% of 2021-22 current spending |

These are different answers to different definitions, not versions of one number: they differ in standards, base year, dollars, how weights count students, and whether a local share is assigned. The 2007 figures are in 2005-06 dollars and are not comparable with the others without adjustment. The commission's weighted students are about 385,000 for Philadelphia, the BEF formula's own count is 303,000, so spending per weighted student under the formula (`current_exp_per_weighted_student`) must not be compared with the commission's $13,704. Kelly's target minus his shortfall equals the state's 2021-22 current expenditures within 2% for 83% of districts (he finished before some data were final).

## What the state has enacted

The commission recommended closing its gap over seven years, starting in 2024-25 with $871 million for adequacy and equity plus $200 million through the regular formula. As of the state's files (August 2026):

- **Basic Education Funding** rose $285 million in 2024-25 (a $60 million hold-harmless supplement and a $225 million student-weighted distribution), from $7.87 billion to $8.16 billion; Philadelphia's rose $51.6 million, to $1.538 billion.
- **The adequacy and tax equity supplements are paid through the Ready to Learn Block Grant** (`finance_rtl_allocation`), not through the Basic Education Funding line: $493.8 million of adequacy supplements and $32.2 million of tax equity supplements in 2024-25, and $532.9 million and $32.2 million in 2025-26, to 348 districts in 2024-25. Each year's supplement is new money that rolls into the next year's foundation.
- Philadelphia's adequacy supplement was $136.7 million in 2024-25 (67% of the commission's $202.6 million Year-1 recommendation for it; statewide the enacted $526.0 million is 60% of the recommended $871.3 million) and $136.7 million again in 2025-26, with no tax equity supplement.
- Counting both lines, Philadelphia's 2024-25 state increase ($51.6 million plus $136.7 million) was $188 million against a recommended $243 million.

Whether these amounts are adequate depends on which study and which definition one accepts; the data show what was recommended and what was enacted, not which is right. The Ready to Learn amounts are allocations as published, not revenue as booked.

## Facts (Philadelphia City SD, 2023-24, from the state's reports)

- Total expenditures $4.71 billion; instruction (function 1000) $3.08 billion; approximate current expenditures $4.19 billion (instruction, support, and noninstructional services).
- Revenue by source: local $1.97 billion (current real estate taxes $0.995 billion), state $2.13 billion (Basic Education Funding $1.486 billion), federal $0.74 billion.
- The district paid $1.36 billion in tuition to charter schools: 29% of total expenditures, 45% of the $3.0 billion all Pennsylvania school districts paid to charter schools that year. It was $0.71 billion in 2015-16 (up 91% in nominal dollars). Charter tuition pays for students who live in the district and attend a charter; they are not in the district's own enrollment.
- Actual instruction expense was $1.53 billion in 2008-09 and $2.57 billion in 2023-24 (up 68% in nominal dollars).

- Enrollment base: adjusted ADM (the state's formula count of resident students, which includes students enrolled in charter schools; 78,594 charter ADM in 2022-23) was 196,206 in 2023-24, 204,069 in 2016-17. Current expenditures per adjusted ADM rose from $13,729 to $21,358 (up 56% in nominal dollars). Because the numerator includes tuition paid for charter students and the denominator counts them, this is spending per resident student, not per student in district-run schools.

These facts are placed side by side so each side's question can be examined; they do not say whether spending is adequate, efficient, or well used.

## Checks

The five spending functions add to total expenditures for all 7,422 agency-years. Appendix B sums to the report's printed statewide totals within $8. The state-reported Basic Education Funding matches the commission's 2023-24 funding base within 1% for 99.4% of districts (Philadelphia: $1,485,989,116 against $1,486,042,268). See `docs/VALIDATION.md`.

## Limits

- Total expenditures include facilities and debt service/refunding (functions 4000 and 5000) and can jump from year to year; `current_expenditures_approx` is closer to the commission's definition but does not net out tuition-for-patrons revenue, so it runs slightly high.
- The current year (2024-25) is the state's unaudited data.
- Charter school finances come from each charter's own report; charter tuition paid by districts and charter revenue are different views of the same money, and they are not netted.
- Not yet loaded: enrollment by charter school (so per-pupil charter figures are not possible), school-level budgets (in progress), debt, and years before 2014-15 (older AFR files are on the state's FTP site).

## School budgets

`school_budget` holds the district's School Budget Allotment Detail for each school and fiscal year from FY16 to FY27: 2,759 school-years, about 74,000 lines, parsed from the public reports in the district's School Budgets tool (`psd build-school-budget`). Each report lists school-managed and centrally managed allotments by group (basic operating, Title I, special education, and so on). Rows carry `line_type` (`item`, `group_total`, `scope_subtotal`, `school_total`); sum only one type to avoid double counting. Every report reconciles exactly: items add to group totals, groups to scope subtotals, scopes to the school total.

These are budgets set in the spring or summer, not actual spending; principals decide purchases within the school-managed allotments, and centrally managed allotments are money the district spends on a school's behalf. The district's purchase-summary and position reports are not loaded yet, and 145 school-year requests returned "No data available". Two codes in the tool (Al-Aqsa Islamic School, Fox Chase Farm) are not in the district school list and have no `school_id`. FY26 and FY27 are plans for the current and coming year.

`school_budget_purchase` (Summary of School Purchases) and `school_budget_position` (Position Summary) come from the same tool. The purchase summary gives each school's allotment totals, the positions bought (count and amount by funding type), and discretionary spending by expenditure area. The position summary lists each position line (PIDN, position, subject or skill, funding source, activity) with full-time equivalents in the previous and current budget; `fte_curr` is the current year. School-based position FTE rose from 14,184 (FY16) to 19,177 (FY27 plan), including about 8,000 to 9,100 teacher FTE, in the roughly 230 schools with reports each year. These reports reconcile with each other: purchase lines add to printed totals (within $2 of rounding), position FTE add to the purchase report's position counts, and the purchase report's allotment total equals the allotment report's school total, in every school-year.

Two traps. For 13 school codes in FY16 the tool answered with Abraham Lincoln High School's report (code 8010) instead of the school requested; those reports are excluded and logged (`wrong_school` in `school_budget_report`), so no school gets Lincoln's budget. And 52 position lines (0.03%) have funding and activity run together in the printed layout; they are flagged `unsplit` in `parse_note`, and about 7,700 lines whose columns were separated using names seen elsewhere are flagged `repaired`.

## School-level per-pupil spending and enrollment by agency (PDE)

`finance_school_ppe` is the state's ESSA per-pupil expenditure report by school building, 2018-19 to 2023-24, for every public school in Pennsylvania including each charter: personnel and non-personnel expenditures from local, state and federal funds, average daily membership (ADM), and the derived expenditure per ADM. All 220 Philadelphia City SD buildings link to a `school_id` through the state key (AUN and building number). `finance_lea_ppe` is the same report by agency, and building ADM adds to it exactly in all 4,054 agency-years; 2023-24 statewide ADM equals the state's printed total (1,629,339).

`finance_lea_enrollment` has October 1 enrollment and low-income students by agency from 2015-16 to 2025-26. A charter school is its own agency, so this is enrollment by charter school (multi-campus charters are one row). It closes the missing enrollment base for per-pupil figures: `district_finance` now carries `pde_enrollment`, `pde_low_income_share`, `current_expenditures_per_pde_enrollment` (charter schools and career and technical centers only), and the ESSA columns.

Read these carefully. The ESSA report charges to a building only the costs the district assigns to buildings, so a school district's figure leaves out most central, debt and transfer costs, while a charter school's single building carries nearly all of its spending. Do not set a district building's expenditure per ADM beside a charter's as if they measured the same thing; compare charters with charters and district schools with district schools, or use agency-level totals. For Philadelphia City SD, ESSA expenditure per ADM was $12,759 in 2018-19 and $21,036 in 2023-24. District-level `current_expenditures_per_pde_enrollment` is left empty because a district's spending includes tuition for students it does not enroll.

