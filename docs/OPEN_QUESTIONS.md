# Open questions for journalists and researchers

Questions this data cannot answer yet, with what we have and how someone could pursue them. Generated from [sources/open_questions.csv](../sources/open_questions.csv); the questions only the district can answer are in [DISTRICT_QUESTIONS.md](DISTRICT_QUESTIONS.md), and every gap is in [DATA_GAPS.md](DATA_GAPS.md). Tell us if you find an answer, and we will add it with the source.

## Q-001. Where did the students from each of the 23 schools closed in 2013 actually go?

*Who might pursue it:* journalists; researchers

- **Why it matters:** The district never published (or we cannot find) the final school-by-school reassignments; the press lists we hold are the December 2012 proposal, which offered several choices per school and included schools later kept open.
- **What we have:** The December 2012 proposal (school_closure_plan) and observed enrollment change near each closed school (school_closure_flow). Neither shows where individual students went.
- **How to pursue it:** Right-to-Know request to the district for the March 7, 2013 SRC resolution and the final reassignment lists; compare with student-level enrollment by residence if the district will share it; reporting from receiving-school staff and families.
- **Related gaps:** GAP-038; GAP-078; GAP-031

## Q-002. How much did each school actually spend, as opposed to being budgeted?

*Who might pursue it:* journalists; district

- **Why it matters:** The district publishes school budgets (allotments, purchases, positions) but not actual spending by school. Principals decide purchases within school-managed allotments, so budgets can differ from what was spent.
- **What we have:** School budgets for FY16 to FY27 (school_budget, school_budget_purchase, school_budget_position), all reconciled to the district's printed totals.
- **How to pursue it:** Right-to-Know request for actual expenditures by school and fiscal year, with the same line structure as the budget reports.
- **Related gaps:** GAP-070

## Q-003. Why is the district's weighted-student count for Philadelphia about 303,000 under the state formula but about 384,000 in the commission's and Kelly's analyses?

*Who might pursue it:* journalists; researchers

- **Why it matters:** Per-weighted-student figures cannot be compared across them, and the size of Philadelphia's adequacy gap depends on which count is used.
- **What we have:** Both counts and the three adequacy studies side by side (adequacy_compare, finance_district_enrollment).
- **How to pursue it:** Ask the Basic Education Funding Commission and PDE how each count is built; ask the study authors for their weights.
- **Related gaps:** GAP-071; GAP-072

## Q-004. Why did enacted adequacy and tax equity money reach 60% of the commission's first-year recommendation statewide (67% for Philadelphia), and what was the plan for the rest?

*Who might pursue it:* journalists; state

- **Why it matters:** The adequacy supplements are paid through the Ready to Learn grant, not the Basic Education Funding line, so the amount is easy to miss when looking only at the funding formula.
- **What we have:** Allocations by district for 2024-25 and 2025-26 (finance_rtl_allocation) against the commission's recommended amounts.
- **How to pursue it:** Reporting on the budget negotiations; ask PDE and the commission's members for the intended phase-in and whether later years are scheduled.
- **Related gaps:** GAP-073

## Q-005. How many students attend each charter school, so per-pupil funding can be computed for charters as well as for district schools?

*Who might pursue it:* researchers; journalists

- **Why it matters:** Charter tuition paid by Philadelphia was $1.36 billion in 2023-24 (29% of its spending), but per-pupil comparisons need enrollment by charter school and its funding.
- **What we have:** Charter tuition by district (finance_lea_tuition) and each charter's own annual financial report as an agency; no average daily membership by charter.
- **How to pursue it:** PDE charter school enrollment and ADM files by school; Right-to-Know request if not posted.
- **Related gaps:** GAP-076

## Q-006. What happened at the schools whose records suggest a reconfiguration rather than a closure: Roosevelt Middle, Washington E. Rhodes, and Penn Treaty Middle?

*Who might pursue it:* journalists; advocates

- **Why it matters:** The lists give each a separate ID before and after, which can break trend lines. Penn Treaty Middle's regrouping into Penn Treaty High is recorded from local knowledge without a published source; Roosevelt and Rhodes are unconfirmed.
- **What we have:** The lists and enrollment for each, and one hand-set lineage link (Penn Treaty).
- **How to pursue it:** Board resolutions or district announcements for 2012 to 2014; reporting from the neighborhoods.
- **Related gaps:** GAP-079

## Q-007. What do the facilities plan recommendations say school by school, and where are the minutes of the April 23 and April 30, 2026 Board meetings where it was voted?

*Who might pursue it:* journalists; district

- **Why it matters:** The plan's closure and consolidation recommendations are in a dashboard with no export, and the minutes were not posted when we archived the Board records.
- **What we have:** The Board packets from 2019 to 2026 (archived, in the Civus zip) and the 2020 facility condition data for 76 sites.
- **How to pursue it:** Ask the district for the dashboard data and the minutes; check later packets, where minutes now appear as attachments.
- **Related gaps:** GAP-022

## Q-008. Why did school-based position FTE in the reported schools rise from about 14,200 in FY16 to about 19,200 in the FY27 plan, and which kinds of positions grew?

*Who might pursue it:* journalists

- **Why it matters:** The reports list each position line by funding source and activity, but nobody has compared growth by position type with enrollment and need.
- **What we have:** Every position line for FY16 to FY27 (school_budget_position), with previous- and current-year FTE.
- **How to pursue it:** Analyze by position name and funding source against enrollment (enrollment table); ask the district what changed in how positions are budgeted (for example staff moved on or off school budgets).
- **Related gaps:** GAP-070

## Q-009. Are school budgets per student related to student need, and does the split between school-managed and centrally managed allotments differ by school type?

*Who might pursue it:* researchers; journalists

- **Why it matters:** The district's weighting of discretionary allotments is not explained in the reports, and central allotments (special education, food, facilities) are large.
- **What we have:** Budget lines by school and year, enrollment and student group counts, and Census context by school catchment.
- **How to pursue it:** Join budgets to enrollment and poverty measures; interview budget office staff about the allotment formulas.
- **Related gaps:** GAP-070

## Q-010. Which school buildings still have outstanding lead paint, water lead, or asbestos damage, and what are the remediation dates?

*Who might pursue it:* journalists; district

- **Why it matters:** The reports we hold are point-in-time and differ by hazard; asbestos item counts reflect building age more than risk, and the damage figure is the actionable one.
- **What we have:** Lead paint (163 schools), water lead (219), AHERA asbestos (317 buildings, 248 linked), and facility condition (76 sites, 2020 cycle).
- **How to pursue it:** Right-to-Know request for current remediation status and the 28 reports that would not download; ask for newer facility condition assessments.
- **Related gaps:** GAP-033; GAP-063; GAP-065

## Q-011. Where did students go from schools closed or merged after 2017?

*Who might pursue it:* researchers

- **Why it matters:** Enrollment by residence is available from 2016-17 on, so later closures can be traced more directly than the 2013 closures.
- **What we have:** catchment_flow (students by catchment and school, 2016-17 on) and the school events table.
- **How to pursue it:** Build the same observed-flow table for later closures with the residence data; confirm receiving schools in Board records.
- **Related gaps:** GAP-031

## Q-012. What is the planned destination for students in the current round of school moves reported by the Inquirer on October 6, 2026?

*Who might pursue it:* journalists; advocates

- **Why it matters:** This analysis could show whether the pattern resembles 2013 (who gains enrollment near a closure) once the numbers are final.
- **What we have:** The 2013 observed flows as a comparison baseline, and current catchments and enrollment.
- **How to pursue it:** Reporting on the district's plan; the district's reassignment lists when published.
- **Related gaps:** GAP-078

## Q-013. Did Philadelphia's teacher retention really fall to 69% in 2024-25, or did the coding of classroom teachers change?

*Who might pursue it:* journalists; researchers

- **Why it matters:** PDE's file shows 17.7% of Philadelphia's classroom teachers staying in the district in a non-teaching role, against 2 to 5% in other years, and the count of starting teachers (8,562) does not match the year before or after (8,083; 6,977).
- **What we have:** Teacher retention by agency for the pairs PDE publishes (staff_lea_retention) and the staff profile by year (staff_lea_profile).
- **How to pursue it:** Ask PDE's Data Quality Office and the district's HR office whether position coding changed; compare with the district's employee extracts and the district's own retention reporting.
- **Related gaps:** GAP-081; GAP-027
