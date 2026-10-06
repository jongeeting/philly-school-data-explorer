# School finance

`uv run psd catalog-afr`, `uv run psd fetch --source pde_afr befc_report`, then `uv run psd build-finance` builds the finance tables from the Pennsylvania Department of Education's Annual Financial Report (AFR) files and the Basic Education Funding Commission's 2024 report. All dollars are nominal (not adjusted for inflation), by fiscal year; `sy` is the spring year (2024 = FY 2023-24, July to June).

## Tables

- `finance_lea`: 779 agencies: 500 school districts, 209 charter schools, 68 career and technology centers, and 2 others. Each charter school is its own agency; Philadelphia's district is "Philadelphia City SD" (AUN 126515001).
- `finance_lea_line` (1.07 million rows): each agency's reported revenue (local, state, federal, other) and expenditure (by function, by object, and support-service detail) by state account code, 2015-16 to 2024-25 (2014-15 for "other revenue" and objects). `finance_account` is the dictionary of the 458 account codes with a level (1 = broadest). **Accounts are hierarchical and the groups overlap** (a function total contains its detail lines, and the support-service detail repeats part of function 2000): never add across levels or groups. A blank means no amount reported, which is not necessarily zero.
- `finance_lea_tuition`: what each school district paid in tuition, by recipient: other districts, brick-and-mortar and cyber charter schools (regular and special education separately), career centers, private schools.
- `finance_lea_instruction`: actual instruction expense by school district, **2008-09 to 2023-24**, the state's measure used in charter tuition rates.
- `finance_lea_fund_balance`: general fund balance (committed, assigned, unassigned).
- `adequacy_target`: the Basic Education Funding Commission's per-district calculation (Appendix B of its January 11, 2024 report): each district's state share of the adequacy gap, tax equity supplement, 2023-24 funding base, and the recommended 2024-25 increases.
- `marts/district_finance` (11,215 rows): one row per agency and year with the headline lines wide: spending by function, revenue by source, Basic Education Funding, charter tuition paid, instruction expense, fund balance.

## What the adequacy numbers are (and are not)

Adequacy studies in Pennsylvania disagree because they define "adequate" differently. This release holds one:

| Estimate | Who | Method | Statewide | Loaded |
| --- | --- | --- | --- | --- |
| 2007 Costing-Out Study | Commissioned by the state; basis of the 2008 formula | Cost of reaching state performance standards | about $4.4 billion a year (about $1 billion for Philadelphia), per press reports | not yet (primary document to read) |
| 2023 update | Penn State's Matthew Kelly, for the lawsuit plaintiffs and the commission | Updates the 2007 targets | $6.2 billion, per press reports | not yet |
| 2024 final report | The bipartisan Basic Education Funding Commission | Median current spending per weighted student of districts meeting state performance standards ($13,704) times each district's weighted students | $5.4 billion total; $5.14 billion the state's share | yes: `adequacy_target` |

In the commission's table, 371 districts have a positive state share of the gap (the report counts 387 districts below the target, including some whose gap is assigned to local share). Philadelphia's state share is $1,418,543,037, 27.6% of the statewide total, with a 2024-25 recommended increase of $242.7 million. The commission's target year is 2021-22 spending; the 2007 figures are in 2005-06 dollars and are not comparable without adjustment. The estimates are different answers to different definitions of adequate, not versions of one number; show each with its author and method.

## Facts (Philadelphia City SD, 2023-24, from the state's reports)

- Total expenditures $4.71 billion; instruction (function 1000) $3.08 billion; approximate current expenditures $4.19 billion (instruction, support, and noninstructional services).
- Revenue by source: local $1.97 billion (current real estate taxes $0.995 billion), state $2.13 billion (Basic Education Funding $1.486 billion), federal $0.74 billion.
- The district paid $1.36 billion in tuition to charter schools: 29% of total expenditures, 45% of the $3.0 billion all Pennsylvania school districts paid to charter schools that year. It was $0.71 billion in 2015-16 (up 91% in nominal dollars). Charter tuition pays for students who live in the district and attend a charter; they are not in the district's own enrollment.
- Actual instruction expense was $1.53 billion in 2008-09 and $2.57 billion in 2023-24 (up 68% in nominal dollars).

These facts are placed side by side so each side's question can be examined; they do not say whether spending is adequate, efficient, or well used. Per-pupil comparisons need enrollment counts that are not loaded yet (see the gaps).

## Checks

The five spending functions add to total expenditures for all 7,422 agency-years. Appendix B sums to the report's printed statewide totals within $8. The state-reported Basic Education Funding matches the commission's 2023-24 funding base within 1% for 99.4% of districts (Philadelphia: $1,485,989,116 against $1,486,042,268). See `docs/VALIDATION.md`.

## Limits

- Total expenditures include facilities and debt service/refunding (functions 4000 and 5000) and can jump from year to year; `current_expenditures_approx` is closer to the commission's definition but does not net out tuition-for-patrons revenue, so it runs slightly high.
- The current year (2024-25) is the state's unaudited data.
- Charter school finances come from each charter's own report; charter tuition paid by districts and charter revenue are different views of the same money, and they are not netted.
- Not yet loaded: enrollment (average daily membership and weighted student counts), actual state funding distributions since 2023-24 (including the adequacy investment), the 2007 and 2023 studies, school-level budgets, debt, and years before 2014-15 (older AFR files are on the state's FTP site).
